-- O pré-laudo passa a seguir a estrutura padrão de laudo radiológico, que tem
-- uma seção de técnica. Para preenchê-la, a leitura única usada na emissão
-- passa a devolver também os dados técnicos do exame (radiographs.exam_metadata,
-- que só existe quando o exame chegou em DICOM).
--
-- Só redefine a função pre_report_source, acrescentando um campo ao que ela
-- devolve; tabelas e dados não mudam.

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
      'exam_metadata', r.exam_metadata,
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
        'reasons', v.reasons,
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
