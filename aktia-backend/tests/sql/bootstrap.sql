-- Réplica, só para os testes, do que já existe no Supabase antes da migration:
-- papéis, auth.uid() e as tabelas, constraints e políticas RLS copiadas de
-- docs/database/schema.sql (o schema real). Se o schema real mudar, atualize
-- este arquivo junto.

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'anon') then
    create role anon nologin;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'authenticated') then
    create role authenticated nologin;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'service_role') then
    create role service_role nologin bypassrls;
  end if;
end;
$$;

drop schema if exists public cascade;
drop schema if exists auth cascade;
drop schema if exists storage cascade;
create schema public;
create schema auth;
create schema storage;

grant usage on schema public, auth, storage to anon, authenticated, service_role;

-- No Supabase, toda tabela e função nova em public já nasce liberada para
-- esses papéis; quem restringe o acesso são as políticas RLS.
alter default privileges in schema public grant all on tables to anon, authenticated, service_role;
alter default privileges in schema public grant execute on functions to anon, authenticated, service_role;

create table auth.users (
  id uuid primary key default gen_random_uuid()
);

create function auth.uid() returns uuid
language sql stable
as $$
  select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid;
$$;

grant execute on function auth.uid() to anon, authenticated, service_role;


create table public.clinics (
  id uuid default gen_random_uuid() not null,
  name text not null,
  cnpj text,
  created_at timestamp with time zone default now() not null,
  updated_at timestamp with time zone default now() not null,
  email text,
  constraint clinics_pkey primary key (id)
);

create table public.profiles (
  id uuid not null,
  clinic_id uuid,
  full_name text,
  email text,
  role text default 'user'::text not null,
  created_at timestamp with time zone default now() not null,
  updated_at timestamp with time zone default now() not null,
  constraint profiles_pkey primary key (id),
  constraint profiles_role_check check (role = any (array['admin'::text, 'manager'::text, 'user'::text])),
  constraint profiles_clinic_id_fkey foreign key (clinic_id) references public.clinics (id) on delete set null,
  constraint profiles_id_fkey foreign key (id) references auth.users (id) on delete cascade
);

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
  constraint radiographs_pkey primary key (id),
  constraint radiographs_clinic_id_fkey foreign key (clinic_id) references public.clinics (id) on delete cascade,
  constraint radiographs_uploaded_by_fkey foreign key (uploaded_by) references public.profiles (id) on delete set null
);

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
  constraint analyses_pkey primary key (id),
  constraint analyses_quality_score_check check (quality_score >= 0 and quality_score <= 100),
  constraint analyses_status_check check (status = any (array['approved'::text, 'attention'::text, 'rejected'::text, 'processing'::text, 'failed'::text])),
  constraint analyses_clinic_id_fkey foreign key (clinic_id) references public.clinics (id) on delete cascade,
  constraint analyses_radiograph_id_fkey foreign key (radiograph_id) references public.radiographs (id) on delete cascade
);

create table public.analysis_findings (
  id uuid default gen_random_uuid() not null,
  analysis_id uuid not null,
  category text not null,
  score numeric(5,2),
  status text not null,
  confidence numeric(5,4),
  description text,
  created_at timestamp with time zone default now() not null,
  constraint analysis_findings_pkey primary key (id),
  constraint analysis_findings_category_check check (category = any (array['sharpness'::text, 'exposure'::text, 'contrast'::text, 'positioning'::text, 'noise'::text, 'artifacts'::text, 'coverage'::text, 'framing'::text])),
  constraint analysis_findings_confidence_check check (confidence >= 0 and confidence <= 1),
  constraint analysis_findings_score_check check (score >= 0 and score <= 100),
  constraint analysis_findings_status_check check (status = any (array['approved'::text, 'attention'::text, 'rejected'::text])),
  constraint analysis_findings_analysis_id_fkey foreign key (analysis_id) references public.analyses (id) on delete cascade
);

create index idx_analyses_clinic_id on public.analyses using btree (clinic_id);
create index idx_analyses_radiograph_id on public.analyses using btree (radiograph_id);
create index idx_analyses_status on public.analyses using btree (status);
create index idx_analysis_findings_analysis_id on public.analysis_findings using btree (analysis_id);
create index idx_analysis_findings_category on public.analysis_findings using btree (category);
create index idx_profiles_clinic_id on public.profiles using btree (clinic_id);
create index idx_radiographs_clinic_id on public.radiographs using btree (clinic_id);
create index idx_radiographs_uploaded_by on public.radiographs using btree (uploaded_by);

alter table public.clinics enable row level security;
alter table public.profiles enable row level security;
alter table public.radiographs enable row level security;
alter table public.analyses enable row level security;
alter table public.analysis_findings enable row level security;

create policy "Users can view clinic analyses" on public.analyses
  for select to authenticated
  using (clinic_id = (select profiles.clinic_id from public.profiles where profiles.id = auth.uid()));

create policy "Users can view analysis findings" on public.analysis_findings
  for select to authenticated
  using (exists (
    select 1 from public.analyses
    where analyses.id = analysis_findings.analysis_id
      and analyses.clinic_id = (select profiles.clinic_id from public.profiles where profiles.id = auth.uid())
  ));

create policy "Users can view their own clinic" on public.clinics
  for select to authenticated
  using (id = (select profiles.clinic_id from public.profiles where profiles.id = auth.uid()));

create policy "Users can view their own profile" on public.profiles
  for select to authenticated
  using (id = auth.uid());

create policy "Users can update their own profile" on public.profiles
  for update to authenticated
  using (id = auth.uid())
  with check (id = auth.uid());

create policy "Users can create clinic radiographs" on public.radiographs
  for insert to authenticated
  with check (clinic_id = (select profiles.clinic_id from public.profiles where profiles.id = auth.uid()));

create policy "Users can view clinic radiographs" on public.radiographs
  for select to authenticated
  using (clinic_id = (select profiles.clinic_id from public.profiles where profiles.id = auth.uid()));


-- Storage: só o necessário para reproduzir as políticas reais do bucket.
create table storage.objects (
  id uuid primary key default gen_random_uuid(),
  bucket_id text,
  name text
);

grant all on storage.objects to anon, authenticated, service_role;

create function storage.foldername(name text) returns text[]
language sql immutable
as $$
  select (string_to_array(name, '/'))[1:array_length(string_to_array(name, '/'), 1) - 1];
$$;

alter table storage.objects enable row level security;

create policy "AktIA - Delete radiographs" on storage.objects
  for delete to public
  using (bucket_id = 'radiographs'::text);

create policy "AktIA - Read radiographs" on storage.objects
  for select to public
  using (bucket_id = 'radiographs'::text);

create policy "AktIA - Upload radiographs" on storage.objects
  for insert to public
  with check (bucket_id = 'radiographs'::text);

create policy "Users can delete their clinic radiographs" on storage.objects
  for delete to authenticated
  using (bucket_id = 'radiographs'::text and (storage.foldername(name))[1] = (
    select profiles.clinic_id::text from public.profiles where profiles.id = auth.uid()
  ));

create policy "Users can upload to their clinic folder" on storage.objects
  for insert to authenticated
  with check (bucket_id = 'radiographs'::text and (storage.foldername(name))[1] = (
    select profiles.clinic_id::text from public.profiles where profiles.id = auth.uid()
  ));

create policy "Users can view their clinic radiographs" on storage.objects
  for select to authenticated
  using (bucket_id = 'radiographs'::text and (storage.foldername(name))[1] = (
    select profiles.clinic_id::text from public.profiles where profiles.id = auth.uid()
  ));
