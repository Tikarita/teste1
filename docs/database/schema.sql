-- Schema `public` do projeto Supabase aktia (tcfbtfqoavcgpkoefaiq)
-- Gerado em 2026-10-06 a partir dos catálogos do Postgres (pg_catalog /
-- information_schema), via Management API em modo somente leitura.
-- NÃO é saída do pg_dump: é uma reconstrução para consulta. Serve de referência,
-- não para restaurar o banco. Em caso de dúvida, consulte o banco ao vivo.

-- ===== Tabelas =====

-- analyses: 11 linha(s) na data do dump; RLS ATIVO
create table public.analyses (
  id uuid default gen_random_uuid() not null,
  radiograph_id uuid not null,
  clinic_id uuid,
  quality_score numeric(5,2),
  status text not null,
  recommendation text,
  model_version text,
  processing_time_ms integer,
  created_at timestamp with time zone default now() not null,
  professional_id uuid,
  is_adequate boolean,
  result jsonb,
  is_current boolean default true not null,
  constraint analyses_quality_score_check CHECK (((quality_score >= (0)::numeric) AND (quality_score <= (100)::numeric))),
  constraint analyses_status_check CHECK ((status = ANY (ARRAY['approved'::text, 'attention'::text, 'rejected'::text, 'processing'::text, 'failed'::text]))),
  constraint analyses_clinic_id_fkey FOREIGN KEY (clinic_id) REFERENCES clinics(id) ON DELETE CASCADE,
  constraint analyses_professional_id_fkey FOREIGN KEY (professional_id) REFERENCES profiles(id) ON DELETE SET NULL,
  constraint analyses_radiograph_id_fkey FOREIGN KEY (radiograph_id) REFERENCES radiographs(id) ON DELETE CASCADE,
  constraint analyses_pkey PRIMARY KEY (id)
);
alter table public.analyses enable row level security;

-- analysis_findings: 41 linha(s) na data do dump; RLS ATIVO
create table public.analysis_findings (
  id uuid default gen_random_uuid() not null,
  analysis_id uuid not null,
  category text not null,
  score numeric(5,2),
  status text not null,
  confidence numeric(5,4),
  description text,
  created_at timestamp with time zone default now() not null,
  constraint analysis_findings_category_check CHECK ((category = ANY (ARRAY['sharpness'::text, 'exposure'::text, 'contrast'::text, 'positioning'::text, 'noise'::text, 'artifacts'::text, 'coverage'::text, 'framing'::text]))),
  constraint analysis_findings_confidence_check CHECK (((confidence >= (0)::numeric) AND (confidence <= (1)::numeric))),
  constraint analysis_findings_score_check CHECK (((score >= (0)::numeric) AND (score <= (100)::numeric))),
  constraint analysis_findings_status_check CHECK ((status = ANY (ARRAY['approved'::text, 'attention'::text, 'rejected'::text]))),
  constraint analysis_findings_analysis_id_fkey FOREIGN KEY (analysis_id) REFERENCES analyses(id) ON DELETE CASCADE,
  constraint analysis_findings_pkey PRIMARY KEY (id)
);
alter table public.analysis_findings enable row level security;

-- clinics: 7 linha(s) na data do dump; RLS ATIVO
create table public.clinics (
  id uuid default gen_random_uuid() not null,
  name text not null,
  cnpj text,
  created_at timestamp with time zone default now() not null,
  updated_at timestamp with time zone default now() not null,
  email text,
  constraint clinics_pkey PRIMARY KEY (id)
);
alter table public.clinics enable row level security;

-- exams: 0 linha(s) na data do dump; RLS ATIVO
create table public.exams (
  id uuid default gen_random_uuid() not null,
  clinic_id uuid not null,
  uploaded_by uuid,
  file_name text not null,
  file_path text not null,
  file_url text,
  status text default 'pending'::text not null,
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now(),
  constraint exams_clinic_id_fkey FOREIGN KEY (clinic_id) REFERENCES clinics(id) ON DELETE CASCADE,
  constraint exams_uploaded_by_fkey FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE SET NULL,
  constraint exams_pkey PRIMARY KEY (id)
);
alter table public.exams enable row level security;

-- profiles: 4 linha(s) na data do dump; RLS ATIVO
create table public.profiles (
  id uuid not null,
  clinic_id uuid,
  full_name text,
  email text,
  role text default 'user'::text not null,
  created_at timestamp with time zone default now() not null,
  updated_at timestamp with time zone default now() not null,
  constraint profiles_role_check CHECK ((role = ANY (ARRAY['admin'::text, 'manager'::text, 'user'::text]))),
  constraint profiles_clinic_id_fkey FOREIGN KEY (clinic_id) REFERENCES clinics(id) ON DELETE SET NULL,
  constraint profiles_id_fkey FOREIGN KEY (id) REFERENCES auth.users(id) ON DELETE CASCADE,
  constraint profiles_pkey PRIMARY KEY (id)
);
alter table public.profiles enable row level security;

-- radiographs: 10 linha(s) na data do dump; RLS ATIVO
create table public.radiographs (
  id uuid default gen_random_uuid() not null,
  clinic_id uuid,
  uploaded_by uuid,
  file_name text not null,
  file_path text not null,
  file_type text,
  file_size bigint,
  created_at timestamp with time zone default now() not null,
  analysis_result jsonb,
  professional_id uuid,
  constraint radiographs_clinic_id_fkey FOREIGN KEY (clinic_id) REFERENCES clinics(id) ON DELETE CASCADE,
  constraint radiographs_professional_id_fkey FOREIGN KEY (professional_id) REFERENCES profiles(id) ON DELETE SET NULL,
  constraint radiographs_uploaded_by_fkey FOREIGN KEY (uploaded_by) REFERENCES profiles(id) ON DELETE SET NULL,
  constraint radiographs_pkey PRIMARY KEY (id)
);
alter table public.radiographs enable row level security;

-- reports: 0 linha(s) na data do dump; RLS ATIVO
create table public.reports (
  id uuid default gen_random_uuid() not null,
  clinic_id uuid,
  generated_by uuid,
  file_path text,
  report_type text default 'analysis'::text not null,
  created_at timestamp with time zone default now() not null,
  constraint reports_report_type_check CHECK ((report_type = ANY (ARRAY['analysis'::text, 'monthly'::text, 'quality'::text]))),
  constraint reports_clinic_id_fkey FOREIGN KEY (clinic_id) REFERENCES clinics(id) ON DELETE CASCADE,
  constraint reports_generated_by_fkey FOREIGN KEY (generated_by) REFERENCES profiles(id) ON DELETE SET NULL,
  constraint reports_pkey PRIMARY KEY (id)
);
alter table public.reports enable row level security;

-- user_profiles: 0 linha(s) na data do dump; RLS ATIVO
create table public.user_profiles (
  id uuid not null,
  email text not null,
  full_name text,
  clinic_name text,
  created_at timestamp with time zone default now(),
  constraint user_profiles_id_fkey FOREIGN KEY (id) REFERENCES auth.users(id),
  constraint user_profiles_pkey PRIMARY KEY (id),
  constraint user_profiles_email_key UNIQUE (email)
);
alter table public.user_profiles enable row level security;

-- users: 3 linha(s) na data do dump; RLS ATIVO
create table public.users (
  id uuid default gen_random_uuid() not null,
  clinic_id uuid not null,
  name text not null,
  email text not null,
  role text default 'user'::text not null,
  created_at timestamp with time zone default now() not null,
  updated_at timestamp with time zone default now() not null,
  constraint users_role_check CHECK ((role = ANY (ARRAY['admin'::text, 'dentist'::text, 'technician'::text, 'user'::text]))),
  constraint users_clinic_id_fkey FOREIGN KEY (clinic_id) REFERENCES clinics(id) ON DELETE CASCADE,
  constraint users_pkey PRIMARY KEY (id),
  constraint users_email_key UNIQUE (email)
);
alter table public.users enable row level security;

-- ===== Índices =====
CREATE UNIQUE INDEX analyses_pkey ON public.analyses USING btree (id);
CREATE INDEX idx_analyses_clinic_created ON public.analyses USING btree (clinic_id, created_at);
CREATE INDEX idx_analyses_clinic_id ON public.analyses USING btree (clinic_id);
CREATE INDEX idx_analyses_clinic_professional_created ON public.analyses USING btree (clinic_id, professional_id, created_at);
CREATE INDEX idx_analyses_clinic_status ON public.analyses USING btree (clinic_id, status);
CREATE UNIQUE INDEX idx_analyses_one_current_per_radiograph ON public.analyses USING btree (radiograph_id) WHERE is_current;
CREATE INDEX idx_analyses_radiograph_id ON public.analyses USING btree (radiograph_id);
CREATE INDEX idx_analyses_status ON public.analyses USING btree (status);
CREATE UNIQUE INDEX analysis_findings_pkey ON public.analysis_findings USING btree (id);
CREATE INDEX idx_analysis_findings_analysis_id ON public.analysis_findings USING btree (analysis_id);
CREATE INDEX idx_analysis_findings_category ON public.analysis_findings USING btree (category);
CREATE UNIQUE INDEX clinics_pkey ON public.clinics USING btree (id);
CREATE UNIQUE INDEX exams_pkey ON public.exams USING btree (id);
CREATE INDEX idx_profiles_clinic_id ON public.profiles USING btree (clinic_id);
CREATE UNIQUE INDEX profiles_pkey ON public.profiles USING btree (id);
CREATE INDEX idx_radiographs_clinic_id ON public.radiographs USING btree (clinic_id);
CREATE INDEX idx_radiographs_clinic_professional ON public.radiographs USING btree (clinic_id, professional_id);
CREATE INDEX idx_radiographs_uploaded_by ON public.radiographs USING btree (uploaded_by);
CREATE UNIQUE INDEX radiographs_pkey ON public.radiographs USING btree (id);
CREATE INDEX idx_reports_clinic_id ON public.reports USING btree (clinic_id);
CREATE UNIQUE INDEX reports_pkey ON public.reports USING btree (id);
CREATE UNIQUE INDEX user_profiles_email_key ON public.user_profiles USING btree (email);
CREATE UNIQUE INDEX user_profiles_pkey ON public.user_profiles USING btree (id);
CREATE UNIQUE INDEX users_email_key ON public.users USING btree (email);
CREATE UNIQUE INDEX users_pkey ON public.users USING btree (id);

-- ===== Políticas RLS (public e storage) =====
create policy "Users can view clinic analyses" on public.analyses as permissive for select to authenticated
  using ((clinic_id = ( SELECT profiles.clinic_id
   FROM profiles
  WHERE (profiles.id = auth.uid()))));
create policy "Users can view analysis findings" on public.analysis_findings as permissive for select to authenticated
  using ((EXISTS ( SELECT 1
   FROM analyses
  WHERE ((analyses.id = analysis_findings.analysis_id) AND (analyses.clinic_id = ( SELECT profiles.clinic_id
           FROM profiles
          WHERE (profiles.id = auth.uid())))))));
create policy "Authenticated users can create clinics" on public.clinics as permissive for insert to authenticated
  with check (true);
create policy "Users can view their own clinic" on public.clinics as permissive for select to authenticated
  using ((id = ( SELECT profiles.clinic_id
   FROM profiles
  WHERE (profiles.id = auth.uid()))));
create policy "Users can update their own profile" on public.profiles as permissive for update to authenticated
  using ((id = auth.uid()))
  with check ((id = auth.uid()));
create policy "Users can view their own profile" on public.profiles as permissive for select to authenticated
  using ((id = auth.uid()));
create policy "Users can view their own profile v2" on public.profiles as permissive for select to authenticated
  using ((id = auth.uid()));
create policy "Users can create clinic radiographs" on public.radiographs as permissive for insert to authenticated
  with check ((clinic_id = ( SELECT profiles.clinic_id
   FROM profiles
  WHERE (profiles.id = auth.uid()))));
create policy "Users can view clinic radiographs" on public.radiographs as permissive for select to authenticated
  using ((clinic_id = ( SELECT profiles.clinic_id
   FROM profiles
  WHERE (profiles.id = auth.uid()))));
create policy "AktIA - Delete radiographs" on storage.objects as permissive for delete to public
  using ((bucket_id = 'radiographs'::text));
create policy "AktIA - Read radiographs" on storage.objects as permissive for select to public
  using ((bucket_id = 'radiographs'::text));
create policy "AktIA - Upload radiographs" on storage.objects as permissive for insert to public
  with check ((bucket_id = 'radiographs'::text));
create policy "Users can delete their clinic radiographs" on storage.objects as permissive for delete to authenticated
  using (((bucket_id = 'radiographs'::text) AND ((storage.foldername(name))[1] = ( SELECT (profiles.clinic_id)::text AS clinic_id
   FROM profiles
  WHERE (profiles.id = auth.uid())))));
create policy "Users can upload to their clinic folder" on storage.objects as permissive for insert to authenticated
  with check (((bucket_id = 'radiographs'::text) AND ((storage.foldername(name))[1] = ( SELECT (profiles.clinic_id)::text AS clinic_id
   FROM profiles
  WHERE (profiles.id = auth.uid())))));
create policy "Users can view their clinic radiographs" on storage.objects as permissive for select to authenticated
  using (((bucket_id = 'radiographs'::text) AND ((storage.foldername(name))[1] = ( SELECT (profiles.clinic_id)::text AS clinic_id
   FROM profiles
  WHERE (profiles.id = auth.uid())))));

-- ===== Privilégios de anon/authenticated nas tabelas =====
-- Os papéis anon e authenticated têm SELECT/INSERT em todas as tabelas acima
-- (padrão do Supabase, conferido com has_table_privilege). Quem restringe o
-- acesso são só as políticas RLS: tabela com RLS ativo e sem política para um
-- papel fica inacessível para ele.

-- ===== Funções =====
CREATE OR REPLACE FUNCTION public.create_clinic(clinic_name text, clinic_cnpj text DEFAULT NULL::text)
 RETURNS uuid
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
    new_clinic_id UUID;
BEGIN

    INSERT INTO public.clinics (
        name,
        cnpj
    )
    VALUES (
        clinic_name,
        clinic_cnpj
    )
    RETURNING id INTO new_clinic_id;


    UPDATE public.profiles
    SET
        clinic_id = new_clinic_id,
        role = 'admin',
        updated_at = NOW()
    WHERE id = auth.uid();


    RETURN new_clinic_id;

END;
$function$;

CREATE OR REPLACE FUNCTION public.enforce_radiograph_professional_clinic()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO 'public'
AS $function$
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
$function$;

CREATE OR REPLACE FUNCTION public.handle_new_user()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
BEGIN
    INSERT INTO public.profiles (
        id,
        full_name,
        email,
        role
    )
    VALUES (
        NEW.id,
        COALESCE(
            NEW.raw_user_meta_data ->> 'full_name',
            NEW.raw_user_meta_data ->> 'name'
        ),
        NEW.email,
        'user'
    );

    RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION public.quality_findings(p_clinic_id uuid, p_start timestamp with time zone, p_end timestamp with time zone, p_professional_id uuid DEFAULT NULL::uuid, p_status text DEFAULT NULL::text)
 RETURNS TABLE(category text, occurrences bigint)
 LANGUAGE sql
 STABLE
 SET search_path TO 'public'
AS $function$
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
$function$;

CREATE OR REPLACE FUNCTION public.quality_history(p_clinic_id uuid, p_start timestamp with time zone, p_end timestamp with time zone, p_professional_id uuid DEFAULT NULL::uuid, p_status text DEFAULT NULL::text, p_granularity text DEFAULT 'day'::text, p_timezone text DEFAULT 'UTC'::text)
 RETURNS TABLE(bucket date, avg_score numeric, total bigint)
 LANGUAGE sql
 STABLE
 SET search_path TO 'public'
AS $function$
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
$function$;

CREATE OR REPLACE FUNCTION public.quality_summary(p_clinic_id uuid, p_start timestamp with time zone, p_end timestamp with time zone, p_professional_id uuid DEFAULT NULL::uuid, p_status text DEFAULT NULL::text)
 RETURNS TABLE(total bigint, avg_score numeric, approved bigint, attention bigint, rejected bigint)
 LANGUAGE sql
 STABLE
 SET search_path TO 'public'
AS $function$
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
$function$;

CREATE OR REPLACE FUNCTION public.record_analysis(p_radiograph_id uuid, p_clinic_id uuid, p_status text, p_quality_score numeric, p_is_adequate boolean, p_model_version text, p_recommendation text, p_result jsonb, p_findings jsonb DEFAULT '[]'::jsonb)
 RETURNS uuid
 LANGUAGE plpgsql
 SET search_path TO 'public'
AS $function$
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
$function$;

-- ===== Gatilhos (em tabelas public ou que chamam funções public) =====
CREATE TRIGGER on_auth_user_created AFTER INSERT ON auth.users FOR EACH ROW EXECUTE FUNCTION handle_new_user();
CREATE TRIGGER radiographs_professional_same_clinic BEFORE INSERT OR UPDATE OF professional_id, clinic_id ON public.radiographs FOR EACH ROW EXECUTE FUNCTION enforce_radiograph_professional_clinic();

-- ===== Views =====
-- (nenhuma view)

-- ===== Buckets de storage =====
-- radiographs: public=False, limite=None, mime=None
