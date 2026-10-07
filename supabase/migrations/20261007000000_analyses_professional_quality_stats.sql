-- Relaciona as análises ao profissional responsável pela captura e cria as
-- agregações de qualidade usadas pelo backend (/api/v1/stats/*).
--
-- Escrito sobre o schema real (docs/database/schema.sql): `analyses` e
-- `analysis_findings` já existem e estão vazias, então aqui só entram colunas,
-- índices e funções novas. Nada existente é removido, renomeado ou tem o tipo
-- alterado, e nenhuma política RLS é mexida. Pode ser rodado mais de uma vez.


-- 1. Profissional responsável pela captura ------------------------------------
-- Nullable: as radiografias que já existem não têm essa informação.

alter table public.radiographs
  add column if not exists professional_id uuid references public.profiles (id) on delete set null;

create index if not exists idx_radiographs_clinic_professional
  on public.radiographs (clinic_id, professional_id);


-- O backend valida isso no upload. O gatilho garante a mesma regra para quem
-- grava direto pela API do Supabase: a política de insert de `radiographs`
-- confere a clínica da linha, mas não a do profissional apontado.
create or replace function public.enforce_radiograph_professional_clinic()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if new.professional_id is not null and not exists (
    select 1
    from public.profiles p
    where p.id = new.professional_id
      and p.clinic_id = new.clinic_id
  ) then
    raise exception 'professional_id % não pertence à clínica %', new.professional_id, new.clinic_id
      using errcode = 'check_violation';
  end if;

  return new;
end;
$$;

do $$
begin
  if not exists (
    select 1 from pg_trigger
    where tgname = 'radiographs_professional_same_clinic'
      and tgrelid = 'public.radiographs'::regclass
  ) then
    create trigger radiographs_professional_same_clinic
      before insert or update of professional_id, clinic_id on public.radiographs
      for each row execute function public.enforce_radiograph_professional_clinic();
  end if;
end;
$$;


-- 2. Colunas novas em analyses -------------------------------------------------
-- professional_id: cópia do profissional da radiografia no momento da análise.
-- is_adequate:     veredito binário do modelo de qualidade.
-- result:          resultado completo devolvido pelo modelo.
-- is_current:      marca a análise mais recente de cada radiografia. Reanalisar
--                  não apaga o histórico, mas as estatísticas contam cada
--                  radiografia uma vez só.
-- As colunas que já existiam (quality_score, status, recommendation,
-- model_version, ...) são usadas como estão.

alter table public.analyses
  add column if not exists professional_id uuid references public.profiles (id) on delete set null,
  add column if not exists is_adequate boolean,
  add column if not exists result jsonb,
  add column if not exists is_current boolean not null default true;

create index if not exists idx_analyses_clinic_created
  on public.analyses (clinic_id, created_at);

create index if not exists idx_analyses_clinic_professional_created
  on public.analyses (clinic_id, professional_id, created_at);

create index if not exists idx_analyses_clinic_status
  on public.analyses (clinic_id, status);

create unique index if not exists idx_analyses_one_current_per_radiograph
  on public.analyses (radiograph_id) where is_current;

-- RLS: as políticas de select que já existem em analyses ("Users can view
-- clinic analyses") e analysis_findings filtram por linha, então cobrem as
-- colunas novas sem alteração. Não há política de escrita para `authenticated`:
-- quem grava é o backend (service role), pela função abaixo.


-- 3. Gravação de uma análise ---------------------------------------------------
-- Tudo numa transação: rebaixa a análise anterior, insere a nova com os
-- critérios e atualiza radiographs.analysis_result (que a tela atual ainda lê).
-- O profissional vem da radiografia, não de quem chama.
--
-- p_findings é um array de {category, status, score}. Só entram critérios
-- avaliados: analysis_findings.status não aceita "pending".

create or replace function public.record_analysis(
  p_radiograph_id uuid,
  p_clinic_id uuid,
  p_status text,
  p_quality_score numeric,
  p_is_adequate boolean,
  p_model_version text,
  p_recommendation text,
  p_result jsonb,
  p_findings jsonb default '[]'::jsonb
)
returns uuid
language plpgsql
security invoker
set search_path = public
as $$
declare
  v_professional_id uuid;
  v_analysis_id uuid;
begin
  select r.professional_id
    into v_professional_id
  from public.radiographs r
  where r.id = p_radiograph_id
    and r.clinic_id = p_clinic_id
  for update;

  if not found then
    raise exception 'Radiografia % não encontrada na clínica %', p_radiograph_id, p_clinic_id
      using errcode = 'no_data_found';
  end if;

  update public.analyses
     set is_current = false
   where radiograph_id = p_radiograph_id
     and is_current;

  insert into public.analyses (
    radiograph_id, clinic_id, professional_id, status, quality_score,
    is_adequate, model_version, recommendation, result
  )
  values (
    p_radiograph_id, p_clinic_id, v_professional_id, p_status, p_quality_score,
    p_is_adequate, p_model_version, p_recommendation, p_result
  )
  returning id into v_analysis_id;

  insert into public.analysis_findings (analysis_id, category, status, score)
  select
    v_analysis_id,
    f ->> 'category',
    f ->> 'status',
    (f ->> 'score')::numeric
  from jsonb_array_elements(coalesce(p_findings, '[]'::jsonb)) as f;

  update public.radiographs
     set analysis_result = p_result
   where id = p_radiograph_id;

  return v_analysis_id;
end;
$$;


-- 4. Agregações ----------------------------------------------------------------
-- Período é [p_start, p_end). p_professional_id / p_status nulos = sem filtro.
-- p_clinic_id é sempre preenchido pelo backend a partir do usuário autenticado.

create or replace function public.quality_summary(
  p_clinic_id uuid,
  p_start timestamptz,
  p_end timestamptz,
  p_professional_id uuid default null,
  p_status text default null
)
returns table (
  total bigint,
  avg_score numeric,
  approved bigint,
  attention bigint,
  rejected bigint
)
language sql
stable
security invoker
set search_path = public
as $$
  select
    count(*),
    round(avg(a.quality_score), 1),
    count(*) filter (where a.status = 'approved'),
    count(*) filter (where a.status = 'attention'),
    count(*) filter (where a.status = 'rejected')
  from public.analyses a
  where a.clinic_id = p_clinic_id
    and a.is_current
    -- "processing" e "failed" não têm resultado para entrar na estatística.
    and a.status in ('approved', 'attention', 'rejected')
    and a.created_at >= p_start
    and a.created_at < p_end
    and (p_professional_id is null or a.professional_id = p_professional_id)
    and (p_status is null or a.status = p_status);
$$;


create or replace function public.quality_history(
  p_clinic_id uuid,
  p_start timestamptz,
  p_end timestamptz,
  p_professional_id uuid default null,
  p_status text default null,
  p_granularity text default 'day',
  p_timezone text default 'UTC'
)
returns table (
  bucket date,
  avg_score numeric,
  total bigint
)
language sql
stable
security invoker
set search_path = public
as $$
  select
    date_trunc(
      case when p_granularity = 'week' then 'week' else 'day' end,
      a.created_at at time zone p_timezone
    )::date as bucket,
    round(avg(a.quality_score), 1),
    count(*)
  from public.analyses a
  where a.clinic_id = p_clinic_id
    and a.is_current
    and a.status in ('approved', 'attention', 'rejected')
    and a.created_at >= p_start
    and a.created_at < p_end
    and (p_professional_id is null or a.professional_id = p_professional_id)
    and (p_status is null or a.status = p_status)
  group by 1
  order by 1;
$$;


-- Critérios com problema (atenção ou reprovado) por categoria.
create or replace function public.quality_findings(
  p_clinic_id uuid,
  p_start timestamptz,
  p_end timestamptz,
  p_professional_id uuid default null,
  p_status text default null
)
returns table (
  category text,
  occurrences bigint
)
language sql
stable
security invoker
set search_path = public
as $$
  select
    f.category,
    count(*)
  from public.analysis_findings f
  join public.analyses a on a.id = f.analysis_id
  where a.clinic_id = p_clinic_id
    and a.is_current
    and a.status in ('approved', 'attention', 'rejected')
    and a.created_at >= p_start
    and a.created_at < p_end
    and (p_professional_id is null or a.professional_id = p_professional_id)
    and (p_status is null or a.status = p_status)
    and f.status in ('attention', 'rejected')
  group by f.category
  order by count(*) desc, f.category;
$$;


-- Essas funções recebem clinic_id por parâmetro, então só o backend
-- (service role) pode chamá-las. No Supabase, função nova em public nasce
-- executável por anon e authenticated; por isso o revoke explícito.
revoke all on function public.record_analysis(uuid, uuid, text, numeric, boolean, text, text, jsonb, jsonb) from public, anon, authenticated;
revoke all on function public.quality_summary(uuid, timestamptz, timestamptz, uuid, text) from public, anon, authenticated;
revoke all on function public.quality_history(uuid, timestamptz, timestamptz, uuid, text, text, text) from public, anon, authenticated;
revoke all on function public.quality_findings(uuid, timestamptz, timestamptz, uuid, text) from public, anon, authenticated;

grant execute on function public.record_analysis(uuid, uuid, text, numeric, boolean, text, text, jsonb, jsonb) to service_role;
grant execute on function public.quality_summary(uuid, timestamptz, timestamptz, uuid, text) to service_role;
grant execute on function public.quality_history(uuid, timestamptz, timestamptz, uuid, text, text, text) to service_role;
grant execute on function public.quality_findings(uuid, timestamptz, timestamptz, uuid, text) to service_role;


-- 5. Dados antigos -------------------------------------------------------------
-- Copia para `analyses` só a parte de controle de qualidade do que já estava
-- em radiographs.analysis_result. Os achados do YOLO não são copiados: eram
-- gerados por um placeholder, não por um modelo. professional_id fica nulo, e
-- created_at usa a data do upload porque a data da análise não era registrada.

with inserted as (
  insert into public.analyses (
    radiograph_id, clinic_id, professional_id, status, quality_score,
    is_adequate, model_version, recommendation, result, created_at
  )
  select
    r.id,
    r.clinic_id,
    r.professional_id,
    case when (r.analysis_result -> 'efficientnet' ->> 'is_adequate')::boolean
      then 'approved' else 'rejected' end,
    (r.analysis_result -> 'efficientnet' ->> 'score')::numeric,
    (r.analysis_result -> 'efficientnet' ->> 'is_adequate')::boolean,
    r.analysis_result -> 'efficientnet' ->> 'model',
    r.analysis_result -> 'efficientnet' ->> 'recommendation',
    jsonb_build_object('efficientnet', r.analysis_result -> 'efficientnet'),
    r.created_at
  from public.radiographs r
  where r.analysis_result -> 'efficientnet' ->> 'is_adequate' is not null
    and not exists (select 1 from public.analyses a where a.radiograph_id = r.id)
  returning id, result
)
insert into public.analysis_findings (analysis_id, category, status, score)
select
  i.id,
  c ->> 'category',
  c ->> 'status',
  (c ->> 'score')::numeric
from inserted i
cross join lateral jsonb_array_elements(
  coalesce(i.result -> 'efficientnet' -> 'criteria', '[]'::jsonb)
) as c
where c ->> 'status' in ('approved', 'attention', 'rejected')
  and c ->> 'category' in (
    'sharpness', 'exposure', 'contrast', 'positioning',
    'noise', 'artifacts', 'coverage', 'framing'
  );
