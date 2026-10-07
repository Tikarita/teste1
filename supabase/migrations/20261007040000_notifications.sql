-- Avisos em tempo real ao profissional --------------------------------------------
-- Quando a IA classifica um exame como inadequado, o profissional responsável
-- pela captura (e quem enviou, se for outra pessoa) recebe um aviso para
-- conferir a imagem e refazer o exame enquanto o paciente está na clínica.
-- `read_at` registra quando o profissional marcou o aviso como "ciente".
--
-- Só cria objetos novos: uma tabela, índices e uma política de leitura.

create table if not exists public.notifications (
  id uuid primary key default gen_random_uuid(),
  clinic_id uuid not null references public.clinics (id) on delete cascade,
  recipient_id uuid not null references public.profiles (id) on delete cascade,
  radiograph_id uuid references public.radiographs (id) on delete cascade,
  kind text not null check (kind in ('inadequate_exam')),
  title text not null,
  message text not null,
  created_at timestamptz not null default now(),
  read_at timestamptz
);

-- Um aviso por exame e por pessoa: reanalisar o mesmo exame não repete o aviso.
create unique index if not exists idx_notifications_one_per_exam
  on public.notifications (radiograph_id, recipient_id, kind);

create index if not exists idx_notifications_recipient
  on public.notifications (recipient_id, created_at desc);

create index if not exists idx_notifications_clinic_created
  on public.notifications (clinic_id, created_at);


-- Cada pessoa lê só os próprios avisos. Não há política de escrita: quem cria
-- e marca como lido é o backend (service role).
alter table public.notifications enable row level security;

do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'notifications'
      and policyname = 'Users can view their own notifications'
  ) then
    create policy "Users can view their own notifications" on public.notifications
      for select to authenticated
      using (recipient_id = auth.uid());
  end if;
end;
$$;
