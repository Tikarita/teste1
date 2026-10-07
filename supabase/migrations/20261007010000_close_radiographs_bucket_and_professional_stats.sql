-- 1. Fecha o bucket de radiografias ----------------------------------------------
-- Estas três políticas valiam para o papel `public` e só conferiam o bucket:
-- qualquer pessoa com a chave anônima do projeto podia ler, enviar e apagar
-- radiografias de todas as clínicas. O backend usa a service role, que ignora
-- RLS, então não depende delas. As políticas por pasta de clínica ("Users can
-- ... their clinic ...") continuam valendo para `authenticated`.
--
-- É a única remoção deste projeto; foi aprovada explicitamente por ser uma
-- correção de segurança (a regra geral continua sendo só migrations aditivas).

drop policy if exists "AktIA - Read radiographs" on storage.objects;
drop policy if exists "AktIA - Upload radiographs" on storage.objects;
drop policy if exists "AktIA - Delete radiographs" on storage.objects;


-- 2. Qualidade por profissional ---------------------------------------------------
-- Uma linha por profissional responsável (professional_id nulo = radiografias
-- sem profissional informado). Mesmos filtros e mesmo período [p_start, p_end)
-- das outras agregações.

create or replace function public.quality_by_professional(
  p_clinic_id uuid,
  p_start timestamptz,
  p_end timestamptz,
  p_status text default null
)
returns table (
  professional_id uuid,
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
    a.professional_id,
    count(*),
    round(avg(a.quality_score), 1),
    count(*) filter (where a.status = 'approved'),
    count(*) filter (where a.status = 'attention'),
    count(*) filter (where a.status = 'rejected')
  from public.analyses a
  where a.clinic_id = p_clinic_id
    and a.is_current
    and a.status in ('approved', 'attention', 'rejected')
    and a.created_at >= p_start
    and a.created_at < p_end
    and (p_status is null or a.status = p_status)
  group by a.professional_id;
$$;


-- 3. Achados clínicos mais frequentes ----------------------------------------------
-- Conta os achados do detector (YOLO) guardados em analyses.result. Só entram
-- análises em que o detector rodou de verdade (yolo.available = true): as
-- antigas traziam achados de um placeholder. `analyses_evaluated` é quantas
-- análises do período passaram pelo detector, com ou sem achado.

create or replace function public.clinical_findings(
  p_clinic_id uuid,
  p_start timestamptz,
  p_end timestamptz,
  p_professional_id uuid default null
)
returns table (
  class_code text,
  occurrences bigint,
  analyses_with_finding bigint,
  analyses_evaluated bigint
)
language sql
stable
security invoker
set search_path = public
as $$
  with evaluated as (
    select a.id, a.result -> 'yolo' -> 'findings' as findings
    from public.analyses a
    where a.clinic_id = p_clinic_id
      and a.is_current
      and a.created_at >= p_start
      and a.created_at < p_end
      and (p_professional_id is null or a.professional_id = p_professional_id)
      and (a.result -> 'yolo' ->> 'available')::boolean is true
  ),
  totals as (
    select count(*) as analyses_evaluated from evaluated
  ),
  per_class as (
    select
      f ->> 'class_code' as class_code,
      count(*) as occurrences,
      count(distinct e.id) as analyses_with_finding
    from evaluated e
    cross join lateral jsonb_array_elements(
      case when jsonb_typeof(e.findings) = 'array' then e.findings else '[]'::jsonb end
    ) as f
    group by 1
  )
  -- O left join garante uma linha (com class_code nulo) quando houve análises
  -- avaliadas mas nenhum achado, para o backend distinguir "nada encontrado"
  -- de "nada avaliado".
  select p.class_code, p.occurrences, p.analyses_with_finding, t.analyses_evaluated
  from totals t
  left join per_class p on true
  order by p.occurrences desc nulls last, p.class_code;
$$;


revoke all on function public.quality_by_professional(uuid, timestamptz, timestamptz, text) from public, anon, authenticated;
revoke all on function public.clinical_findings(uuid, timestamptz, timestamptz, uuid) from public, anon, authenticated;

grant execute on function public.quality_by_professional(uuid, timestamptz, timestamptz, text) to service_role;
grant execute on function public.clinical_findings(uuid, timestamptz, timestamptz, uuid) to service_role;
