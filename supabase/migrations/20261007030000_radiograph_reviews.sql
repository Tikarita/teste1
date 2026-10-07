-- Revisão humana das radiografias ----------------------------------------------------
-- A IA só faz triagem. Aqui fica a decisão do profissional sobre cada exame:
-- adequado ou inadequado, por quê, e se o exame precisou ser repetido. É o que
-- permite calcular uma taxa de rejeição real e auditável, independente da IA.
--
-- Só cria objetos novos: uma tabela, índices, uma política de leitura e funções.

create table if not exists public.radiograph_reviews (
  id uuid primary key default gen_random_uuid(),
  radiograph_id uuid not null references public.radiographs (id) on delete cascade,
  clinic_id uuid not null references public.clinics (id) on delete cascade,
  -- Análise da IA vigente quando a revisão foi feita (nulo se não havia).
  analysis_id uuid references public.analyses (id) on delete set null,
  reviewed_by uuid references public.profiles (id) on delete set null,
  -- Nome de quem revisou, como estava na hora: o registro continua legível
  -- mesmo que o perfil seja renomeado ou removido depois.
  reviewed_by_name text,
  verdict text not null check (verdict in ('adequate', 'inadequate')),
  repeated boolean not null default false,
  reasons text[] not null default '{}',
  notes text,
  -- Corrigir uma revisão cria outra linha; a anterior fica como histórico.
  is_current boolean not null default true,
  created_at timestamptz not null default now(),

  constraint radiograph_reviews_reasons_check check (
    reasons <@ array[
      'sharpness', 'exposure', 'contrast', 'positioning',
      'noise', 'artifacts', 'coverage', 'framing', 'other'
    ]::text[]
  ),
  -- Exame adequado não tem motivo de rejeição nem repetição; inadequado
  -- precisa de pelo menos um motivo.
  constraint radiograph_reviews_verdict_consistency_check check (
    (verdict = 'adequate' and reasons = '{}' and not repeated)
    or (verdict = 'inadequate' and cardinality(reasons) > 0)
  )
);

create index if not exists idx_radiograph_reviews_clinic_created
  on public.radiograph_reviews (clinic_id, created_at);

create index if not exists idx_radiograph_reviews_radiograph
  on public.radiograph_reviews (radiograph_id);

create unique index if not exists idx_radiograph_reviews_one_current
  on public.radiograph_reviews (radiograph_id) where is_current;


-- Mesmo padrão de `analyses`: a clínica lê só as próprias revisões, e não há
-- política de escrita — quem grava é o backend (service role).
alter table public.radiograph_reviews enable row level security;

do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'radiograph_reviews'
      and policyname = 'Users can view clinic radiograph reviews'
  ) then
    create policy "Users can view clinic radiograph reviews" on public.radiograph_reviews
      for select to authenticated
      using (clinic_id = (select profiles.clinic_id from public.profiles where profiles.id = auth.uid()));
  end if;
end;
$$;


-- Grava uma revisão numa transação: rebaixa a anterior e insere a nova,
-- ligada à análise da IA vigente (se houver). A radiografia precisa ser da
-- clínica informada, e o revisor também.
create or replace function public.record_review(
  p_radiograph_id uuid,
  p_clinic_id uuid,
  p_reviewed_by uuid,
  p_verdict text,
  p_repeated boolean,
  p_reasons text[],
  p_notes text default null
)
returns public.radiograph_reviews
language plpgsql
security invoker
set search_path = public
as $$
declare
  v_reviewer_name text;
  v_analysis_id uuid;
  v_review public.radiograph_reviews;
begin
  perform 1
  from public.radiographs r
  where r.id = p_radiograph_id
    and r.clinic_id = p_clinic_id
  for update;

  if not found then
    raise exception 'Radiografia % não encontrada na clínica %', p_radiograph_id, p_clinic_id
      using errcode = 'no_data_found';
  end if;

  select p.full_name
    into v_reviewer_name
  from public.profiles p
  where p.id = p_reviewed_by
    and p.clinic_id = p_clinic_id;

  if not found then
    raise exception 'Revisor % não pertence à clínica %', p_reviewed_by, p_clinic_id
      using errcode = 'check_violation';
  end if;

  select a.id
    into v_analysis_id
  from public.analyses a
  where a.radiograph_id = p_radiograph_id
    and a.is_current;

  update public.radiograph_reviews
     set is_current = false
   where radiograph_id = p_radiograph_id
     and is_current;

  insert into public.radiograph_reviews (
    radiograph_id, clinic_id, analysis_id, reviewed_by, reviewed_by_name,
    verdict, repeated, reasons, notes
  )
  values (
    p_radiograph_id, p_clinic_id, v_analysis_id, p_reviewed_by, v_reviewer_name,
    p_verdict, p_repeated, coalesce(p_reasons, '{}'), p_notes
  )
  returning * into v_review;

  return v_review;
end;
$$;


-- Indicadores da revisão humana para as radiografias enviadas em
-- [p_start, p_end). A comparação com a IA usa a análise atual de cada
-- radiografia; exames sem análise entram na taxa de rejeição, mas não na
-- concordância.
create or replace function public.review_summary(
  p_clinic_id uuid,
  p_start timestamptz,
  p_end timestamptz,
  p_professional_id uuid default null
)
returns table (
  uploaded bigint,
  reviewed bigint,
  human_adequate bigint,
  human_inadequate bigint,
  repeated bigint,
  compared_with_ai bigint,
  agreed_with_ai bigint,
  ai_missed bigint,
  ai_false_alarm bigint
)
language sql
stable
security invoker
set search_path = public
as $$
  select
    count(*),
    count(v.id),
    count(*) filter (where v.verdict = 'adequate'),
    count(*) filter (where v.verdict = 'inadequate'),
    count(*) filter (where v.repeated),
    count(*) filter (where v.id is not null and a.is_adequate is not null),
    count(*) filter (where a.is_adequate = (v.verdict = 'adequate')),
    count(*) filter (where a.is_adequate and v.verdict = 'inadequate'),
    count(*) filter (where not a.is_adequate and v.verdict = 'adequate')
  from public.radiographs r
  left join public.radiograph_reviews v on v.radiograph_id = r.id and v.is_current
  left join public.analyses a on a.radiograph_id = r.id and a.is_current
  where r.clinic_id = p_clinic_id
    and r.created_at >= p_start
    and r.created_at < p_end
    and (p_professional_id is null or r.professional_id = p_professional_id);
$$;


-- Motivos de rejeição apontados nas revisões do período. Um exame pode ter
-- mais de um motivo.
create or replace function public.review_reasons(
  p_clinic_id uuid,
  p_start timestamptz,
  p_end timestamptz,
  p_professional_id uuid default null
)
returns table (
  reason text,
  occurrences bigint
)
language sql
stable
security invoker
set search_path = public
as $$
  select reason, count(*)
  from public.radiographs r
  join public.radiograph_reviews v on v.radiograph_id = r.id and v.is_current
  cross join lateral unnest(v.reasons) as reason
  where r.clinic_id = p_clinic_id
    and r.created_at >= p_start
    and r.created_at < p_end
    and (p_professional_id is null or r.professional_id = p_professional_id)
    and v.verdict = 'inadequate'
  group by reason
  order by count(*) desc, reason;
$$;


revoke all on function public.record_review(uuid, uuid, uuid, text, boolean, text[], text) from public, anon, authenticated;
revoke all on function public.review_summary(uuid, timestamptz, timestamptz, uuid) from public, anon, authenticated;
revoke all on function public.review_reasons(uuid, timestamptz, timestamptz, uuid) from public, anon, authenticated;

grant execute on function public.record_review(uuid, uuid, uuid, text, boolean, text[], text) to service_role;
grant execute on function public.review_summary(uuid, timestamptz, timestamptz, uuid) to service_role;
grant execute on function public.review_reasons(uuid, timestamptz, timestamptz, uuid) to service_role;
