-- Pré-laudo emitido --------------------------------------------------------------
-- O pré-laudo vira um documento: só com os achados que o profissional
-- confirmou, gravado como foi emitido (tabela `reports`, tipo 'analysis', que
-- o schema já previa). Para o documento identificar o exame sem guardar dado
-- pessoal, a radiografia ganha um código do paciente (o número do prontuário
-- da clínica). Nome, CPF e data de nascimento não são armazenados.
--
-- Só adiciona colunas, um índice e uma função.

alter table public.radiographs
  add column if not exists patient_code text;

alter table public.reports
  add column if not exists radiograph_id uuid references public.radiographs (id) on delete set null;

create index if not exists idx_reports_radiograph
  on public.reports (radiograph_id);


-- Tudo o que o backend precisa para montar o pré-laudo de uma radiografia,
-- numa leitura só e consistente: a radiografia, a análise atual, a revisão de
-- qualidade vigente e as decisões vigentes sobre os achados. Nenhuma linha se
-- a radiografia não for da clínica.
create or replace function public.pre_report_source(
  p_radiograph_id uuid,
  p_clinic_id uuid
)
returns table (source jsonb)
language sql
stable
security invoker
set search_path = public
as $$
  select jsonb_build_object(
    'radiograph', jsonb_build_object(
      'id', r.id,
      'file_name', r.file_name,
      'patient_code', r.patient_code,
      'created_at', r.created_at
    ),
    'professional_name', (
      select p.full_name from public.profiles p where p.id = r.professional_id
    ),
    'analysis', (
      select jsonb_build_object(
        'id', a.id,
        'is_adequate', a.is_adequate,
        'quality_score', a.quality_score,
        'model_version', a.model_version,
        'yolo', a.result -> 'yolo',
        'created_at', a.created_at
      )
      from public.analyses a
      where a.radiograph_id = r.id and a.is_current
    ),
    'review', (
      select jsonb_build_object(
        'verdict', v.verdict,
        'reviewed_by_name', v.reviewed_by_name,
        'created_at', v.created_at
      )
      from public.radiograph_reviews v
      where v.radiograph_id = r.id and v.is_current
    ),
    'validations', coalesce((
      select jsonb_agg(
        jsonb_build_object(
          'finding_index', f.finding_index,
          'decision', f.decision,
          'validated_by_name', f.validated_by_name
        )
        order by f.finding_index
      )
      from public.finding_validations f
      join public.analyses a on a.id = f.analysis_id and a.is_current
      where f.radiograph_id = r.id and f.is_current
    ), '[]'::jsonb)
  )
  from public.radiographs r
  where r.id = p_radiograph_id
    and r.clinic_id = p_clinic_id;
$$;

revoke all on function public.pre_report_source(uuid, uuid) from public, anon, authenticated;
grant execute on function public.pre_report_source(uuid, uuid) to service_role;
