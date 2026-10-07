-- Relatórios de Garantia da Qualidade ------------------------------------------------
-- A tabela `reports` já existia (vazia), só com tipo e data. Para servir de
-- registro rastreável do Programa de Garantia da Qualidade (RDC ANVISA 611/2022,
-- arts. 16 e 17), cada relatório emitido guarda o período e uma cópia congelada
-- dos números: reabrir o relatório anos depois mostra o que foi emitido, não um
-- recálculo. Só adiciona colunas, um índice, uma política de leitura e funções.

alter table public.reports
  add column if not exists title text,
  add column if not exists period_start timestamptz,
  add column if not exists period_end timestamptz,
  add column if not exists notes text,
  add column if not exists data jsonb;

create index if not exists idx_reports_clinic_created
  on public.reports (clinic_id, created_at desc);


-- Mesmo padrão de `analyses`: a clínica lê só os próprios relatórios. Não há
-- política de escrita: quem grava é o backend (service role), e nenhum caminho
-- do sistema altera ou apaga um relatório emitido.
do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'reports'
      and policyname = 'Users can view clinic reports'
  ) then
    create policy "Users can view clinic reports" on public.reports
      for select to authenticated
      using (clinic_id = (select profiles.clinic_id from public.profiles where profiles.id = auth.uid()));
  end if;
end;
$$;


-- Volume do período: radiografias enviadas em [p_start, p_end) e quantas delas
-- têm análise.
create or replace function public.report_volume(
  p_clinic_id uuid,
  p_start timestamptz,
  p_end timestamptz
)
returns table (
  uploaded bigint,
  analyzed bigint
)
language sql
stable
security invoker
set search_path = public
as $$
  select
    count(*),
    count(*) filter (where exists (
      select 1 from public.analyses a
      where a.radiograph_id = r.id and a.is_current
    ))
  from public.radiographs r
  where r.clinic_id = p_clinic_id
    and r.created_at >= p_start
    and r.created_at < p_end;
$$;


-- Versões de modelo que produziram as análises do período, para o relatório
-- declarar com que ferramenta os números foram obtidos.
create or replace function public.report_models(
  p_clinic_id uuid,
  p_start timestamptz,
  p_end timestamptz
)
returns table (
  model_version text,
  total bigint
)
language sql
stable
security invoker
set search_path = public
as $$
  select coalesce(a.model_version, 'não informado'), count(*)
  from public.analyses a
  where a.clinic_id = p_clinic_id
    and a.is_current
    and a.status in ('approved', 'attention', 'rejected')
    and a.created_at >= p_start
    and a.created_at < p_end
  group by 1
  order by 2 desc, 1;
$$;


revoke all on function public.report_volume(uuid, timestamptz, timestamptz) from public, anon, authenticated;
revoke all on function public.report_models(uuid, timestamptz, timestamptz) from public, anon, authenticated;

grant execute on function public.report_volume(uuid, timestamptz, timestamptz) to service_role;
grant execute on function public.report_models(uuid, timestamptz, timestamptz) to service_role;
