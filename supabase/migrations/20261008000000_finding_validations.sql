-- Validação dos achados do pré-laudo ------------------------------------------------
-- O detector (YOLO) só sugere achados. Aqui fica a decisão do profissional
-- sobre cada um: confirmado ou descartado. Só o que foi confirmado é pré-laudo
-- de fato, e as decisões medem quanto o detector acerta em cada tipo de achado.
--
-- Um achado é identificado pela análise e pela posição dele na lista
-- analyses.result -> 'yolo' -> 'findings'. Reanalisar gera outra análise, com
-- outra lista, então a validação recomeça.
--
-- Só cria objetos novos: uma tabela, índices, uma política de leitura e funções.

create table if not exists public.finding_validations (
  id uuid primary key default gen_random_uuid(),
  clinic_id uuid not null references public.clinics (id) on delete cascade,
  radiograph_id uuid not null references public.radiographs (id) on delete cascade,
  analysis_id uuid not null references public.analyses (id) on delete cascade,
  finding_index integer not null check (finding_index >= 0),
  class_code text not null,
  decision text not null check (decision in ('confirmed', 'discarded')),
  validated_by uuid references public.profiles (id) on delete set null,
  -- Nome de quem validou, como estava na hora.
  validated_by_name text,
  -- Mudar a decisão cria outra linha; a anterior fica como histórico.
  is_current boolean not null default true,
  created_at timestamptz not null default now()
);

create unique index if not exists idx_finding_validations_one_current
  on public.finding_validations (analysis_id, finding_index) where is_current;

create index if not exists idx_finding_validations_clinic_created
  on public.finding_validations (clinic_id, created_at);

create index if not exists idx_finding_validations_radiograph
  on public.finding_validations (radiograph_id);


-- Mesmo padrão das demais tabelas: a clínica lê só as próprias linhas, e quem
-- grava é o backend (service role).
alter table public.finding_validations enable row level security;

do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'finding_validations'
      and policyname = 'Users can view clinic finding validations'
  ) then
    create policy "Users can view clinic finding validations" on public.finding_validations
      for select to authenticated
      using (clinic_id = (select profiles.clinic_id from public.profiles where profiles.id = auth.uid()));
  end if;
end;
$$;


-- Decisões vigentes sobre os achados da análise atual de uma radiografia.
create or replace function public.current_finding_validations(
  p_radiograph_id uuid,
  p_clinic_id uuid
)
returns setof public.finding_validations
language sql
stable
security invoker
set search_path = public
as $$
  select v.*
  from public.finding_validations v
  join public.analyses a on a.id = v.analysis_id and a.is_current
  where v.radiograph_id = p_radiograph_id
    and v.clinic_id = p_clinic_id
    and v.is_current
  order by v.finding_index;
$$;


-- Grava um lote de decisões numa transação. p_decisions é um array de
-- {"finding_index": n, "decision": "confirmed" | "discarded" | "pending"};
-- "pending" desfaz a decisão vigente. O tipo do achado vem da própria análise,
-- não de quem chama. Devolve as decisões vigentes depois da gravação.
create or replace function public.record_finding_validations(
  p_radiograph_id uuid,
  p_clinic_id uuid,
  p_validated_by uuid,
  p_decisions jsonb
)
returns setof public.finding_validations
language plpgsql
security invoker
set search_path = public
as $$
declare
  v_analysis_id uuid;
  v_findings jsonb;
  v_validator_name text;
  v_item jsonb;
  v_index integer;
  v_decision text;
begin
  select a.id, a.result -> 'yolo' -> 'findings'
    into v_analysis_id, v_findings
  from public.analyses a
  join public.radiographs r on r.id = a.radiograph_id
  where a.radiograph_id = p_radiograph_id
    and r.clinic_id = p_clinic_id
    and a.is_current
  for update of a;

  if not found then
    raise exception 'Radiografia % sem análise na clínica %', p_radiograph_id, p_clinic_id
      using errcode = 'no_data_found';
  end if;

  select p.full_name
    into v_validator_name
  from public.profiles p
  where p.id = p_validated_by
    and p.clinic_id = p_clinic_id;

  if not found then
    raise exception 'Profissional % não pertence à clínica %', p_validated_by, p_clinic_id
      using errcode = 'check_violation';
  end if;

  if jsonb_typeof(v_findings) is distinct from 'array' then
    v_findings := '[]'::jsonb;
  end if;

  for v_item in select * from jsonb_array_elements(coalesce(p_decisions, '[]'::jsonb))
  loop
    v_index := (v_item ->> 'finding_index')::integer;
    v_decision := v_item ->> 'decision';

    if v_index is null or v_index < 0 or v_index >= jsonb_array_length(v_findings) then
      raise exception 'Achado % não existe nesta análise', v_item ->> 'finding_index'
        using errcode = 'check_violation';
    end if;

    if v_decision is null or v_decision not in ('confirmed', 'discarded', 'pending') then
      raise exception 'Decisão inválida: %', v_decision
        using errcode = 'check_violation';
    end if;

    update public.finding_validations
       set is_current = false
     where analysis_id = v_analysis_id
       and finding_index = v_index
       and is_current;

    if v_decision <> 'pending' then
      insert into public.finding_validations (
        clinic_id, radiograph_id, analysis_id, finding_index, class_code,
        decision, validated_by, validated_by_name
      )
      values (
        p_clinic_id, p_radiograph_id, v_analysis_id, v_index,
        v_findings -> v_index ->> 'class_code',
        v_decision, p_validated_by, v_validator_name
      );
    end if;
  end loop;

  return query
    select v.*
    from public.finding_validations v
    where v.analysis_id = v_analysis_id
      and v.is_current
    order by v.finding_index;
end;
$$;


-- Quanto o detector acerta por tipo de achado, segundo as validações vigentes
-- das análises atuais criadas em [p_start, p_end).
create or replace function public.finding_validation_stats(
  p_clinic_id uuid,
  p_start timestamptz,
  p_end timestamptz
)
returns table (
  class_code text,
  confirmed bigint,
  discarded bigint
)
language sql
stable
security invoker
set search_path = public
as $$
  select
    v.class_code,
    count(*) filter (where v.decision = 'confirmed'),
    count(*) filter (where v.decision = 'discarded')
  from public.finding_validations v
  join public.analyses a on a.id = v.analysis_id and a.is_current
  where v.clinic_id = p_clinic_id
    and v.is_current
    and a.created_at >= p_start
    and a.created_at < p_end
  group by v.class_code
  order by count(*) desc, v.class_code;
$$;


revoke all on function public.current_finding_validations(uuid, uuid) from public, anon, authenticated;
revoke all on function public.record_finding_validations(uuid, uuid, uuid, jsonb) from public, anon, authenticated;
revoke all on function public.finding_validation_stats(uuid, timestamptz, timestamptz) from public, anon, authenticated;

grant execute on function public.current_finding_validations(uuid, uuid) to service_role;
grant execute on function public.record_finding_validations(uuid, uuid, uuid, jsonb) to service_role;
grant execute on function public.finding_validation_stats(uuid, timestamptz, timestamptz) to service_role;
