-- Gigwise: real login (v2.2). Run once on an existing database, after schema.sql.
--
-- How to run: Supabase dashboard -> SQL Editor -> New query -> paste this whole file -> Run.
-- Safe: it only ADDS columns and indexes. It deletes nothing and is safe to run twice.
--
-- What it does
-- - world: every client, freelancer and project belongs to the investor demo ('demo') or to
--   real signed-up users ('real'). The two never see each other. Existing rows become 'demo'.
-- - user_id: links a client or freelancer profile to a Supabase login (auth.users).
--   One login can have one client profile and one freelancer profile.

alter table clients     add column if not exists world text not null default 'demo';
alter table freelancers add column if not exists world text not null default 'demo';
alter table projects    add column if not exists world text not null default 'demo';

alter table clients     add column if not exists user_id uuid unique references auth.users(id) on delete cascade;
alter table freelancers add column if not exists user_id uuid unique references auth.users(id) on delete cascade;

do $$ begin
  alter table clients add constraint clients_world_check check (world in ('demo', 'real'));
exception when duplicate_object then null;
end $$;
do $$ begin
  alter table freelancers add constraint freelancers_world_check check (world in ('demo', 'real'));
exception when duplicate_object then null;
end $$;
do $$ begin
  alter table projects add constraint projects_world_check check (world in ('demo', 'real'));
exception when duplicate_object then null;
end $$;

create index if not exists clients_world_idx     on clients(world);
create index if not exists freelancers_world_idx on freelancers(world);
create index if not exists projects_world_idx    on projects(world);
