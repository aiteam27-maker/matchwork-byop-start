-- Gigwise database schema for Supabase (PostgreSQL).
--
-- How to run: Supabase dashboard -> SQL Editor -> New query -> paste this whole file -> Run.
-- Safe to re-run: it drops and recreates the Gigwise tables (this deletes their data).
--
-- Security: Row Level Security is ON for every table with no policies, so the public
-- "anon" key can read or write nothing. Only the backend, using the secret service_role
-- key, can access data. Login-based policies get added when real login is built.

drop table if exists match_events, notifications, saved_freelancers, saved_jobs, reviews,
  milestones, contracts, offers, messages, threads, proposals, projects, freelancers, clients cascade;

-- Short random text ids, e.g. "p_3f9a1c2b7d4e"
create or replace function gw_id(prefix text) returns text
language sql volatile as $$ select prefix || '_' || substr(replace(gen_random_uuid()::text, '-', ''), 1, 12) $$;

create table clients (
  id            text primary key default gw_id('c'),
  name          text not null,
  rating        numeric(2,1) check (rating between 1 and 5),
  hires         int not null default 0,
  is_demo_user  boolean not null default false,  -- the client you act as until real login exists
  created_at    timestamptz not null default now()
);

create table freelancers (
  id              text primary key default gw_id('f'),
  name            text not null,
  title           text not null,
  skills          text[] not null default '{}',
  rate            numeric not null check (rate > 0),          -- hourly rate in USD
  years           int not null default 0 check (years >= 0),
  rating          numeric(2,1) check (rating between 1 and 5), -- null = no ratings yet
  jobs            int not null default 0,
  jss             int check (jss between 0 and 100),          -- Job Success %, display only
  available       boolean not null default true,
  hours_per_week  int not null default 30,
  location        text,                                       -- shown on profile, never scored
  bio             text not null default '',
  portfolio       jsonb not null default '[]',  -- [{title, description}]
  employment      jsonb not null default '[]',  -- [{role, company, from, to}]
  education       jsonb not null default '[]',  -- [{school, degree, year}]
  certifications  jsonb not null default '[]',  -- [{name, issuer, year}]
  languages       jsonb not null default '[]',  -- [{language, level}]
  connects        int not null default 40 check (connects >= 0),
  created_at      timestamptz not null default now()
);

create table projects (
  id                   text primary key default gw_id('p'),
  client_id            text not null references clients(id) on delete cascade,
  title                text not null,
  description          text not null,
  skills               text[] not null default '{}',
  skills_auto          boolean not null default false,  -- true when skills were detected from the description
  type                 text not null default 'fixed' check (type in ('fixed', 'hourly')),
  budget               numeric not null check (budget > 0),  -- fixed: total; hourly: rate_max * hours
  rate_min             numeric,
  rate_max             numeric,
  hours                int not null check (hours > 0),
  level                text check (level in ('Entry', 'Intermediate', 'Expert')),
  duration             text check (duration in ('Less than 1 month', '1 to 3 months', '3 to 6 months', 'More than 6 months')),
  deadline             date,
  questions            text[] not null default '{}',  -- screening questions, up to 3
  category             text,
  status               text not null default 'open' check (status in ('open', 'hired', 'ended')),
  hired_freelancer_id  text references freelancers(id),
  extra_proposals      int not null default 0,  -- demo: proposals from people outside the demo data
  created_at           timestamptz not null default now(),
  check (type = 'fixed' or (rate_min > 0 and rate_max >= rate_min))
);

create table proposals (
  id              text primary key default gw_id('q'),
  project_id      text not null references projects(id) on delete cascade,
  freelancer_id   text not null references freelancers(id) on delete cascade,
  cover_letter    text not null,
  bid             numeric not null check (bid > 0),  -- fixed: total USD; hourly: USD per hour
  days            int not null check (days > 0),
  answers         text[] not null default '{}',
  links           text[] not null default '{}',
  status          text not null default 'submitted'
                  check (status in ('submitted', 'shortlisted', 'accepted', 'declined', 'withdrawn')),
  connects_spent  int not null default 0,
  created_at      timestamptz not null default now(),
  edited_at       timestamptz,
  unique (project_id, freelancer_id)
);

-- One chat thread per project + freelancer pair
create table threads (
  id                  text primary key default gw_id('t'),
  project_id          text not null references projects(id) on delete cascade,
  freelancer_id       text not null references freelancers(id) on delete cascade,
  invited             boolean not null default false,
  client_read_at      timestamptz,
  freelancer_read_at  timestamptz,
  created_at          timestamptz not null default now(),
  unique (project_id, freelancer_id)
);

create table messages (
  id          bigint generated always as identity primary key,
  thread_id   text not null references threads(id) on delete cascade,
  sender      text not null check (sender in ('client', 'freelancer', 'system')),
  body        text not null,
  created_at  timestamptz not null default now()
);

create table offers (
  id             text primary key default gw_id('o'),
  project_id     text not null references projects(id) on delete cascade,
  freelancer_id  text not null references freelancers(id) on delete cascade,
  proposal_id    text references proposals(id) on delete set null,
  type           text not null check (type in ('fixed', 'hourly')),
  milestones     jsonb not null default '[]',  -- fixed: [{title, amount, due_date}]
  rate           numeric,                      -- hourly
  weekly_limit   int,                          -- hourly
  message        text,
  status         text not null default 'pending' check (status in ('pending', 'accepted', 'declined', 'withdrawn')),
  created_at     timestamptz not null default now()
);
-- Only one pending offer per project at a time
create unique index offers_one_pending on offers(project_id) where status = 'pending';

create table contracts (
  id             text primary key default gw_id('k'),
  project_id     text not null references projects(id) on delete cascade,
  freelancer_id  text not null references freelancers(id) on delete cascade,
  offer_id       text references offers(id) on delete set null,
  type           text not null check (type in ('fixed', 'hourly')),
  rate           numeric,
  weekly_limit   int,
  status         text not null default 'active' check (status in ('active', 'ended')),
  started_at     timestamptz not null default now(),
  ended_at       timestamptz
);

-- Amounts track the work only. No payments happen in Gigwise.
create table milestones (
  id                 bigint generated always as identity primary key,
  contract_id        text not null references contracts(id) on delete cascade,
  position           int not null,
  title              text not null,
  amount             numeric not null check (amount > 0),
  due_date           date,
  status             text not null default 'pending' check (status in ('pending', 'active', 'submitted', 'approved')),
  note               text,
  link               text,
  changes_requested  text,
  unique (contract_id, position)
);

create table reviews (
  id           bigint generated always as identity primary key,
  contract_id  text not null references contracts(id) on delete cascade,
  direction    text not null check (direction in ('client_to_freelancer', 'freelancer_to_client')),
  rating       int not null check (rating between 1 and 5),
  body         text not null,
  created_at   timestamptz not null default now(),
  unique (contract_id, direction)
);

create table notifications (
  id              bigint generated always as identity primary key,
  recipient_type  text not null check (recipient_type in ('client', 'freelancer')),
  recipient_id    text not null,
  body            text not null,
  link            text,
  read            boolean not null default false,
  created_at      timestamptz not null default now()
);

create table saved_jobs (
  freelancer_id  text not null references freelancers(id) on delete cascade,
  project_id     text not null references projects(id) on delete cascade,
  created_at     timestamptz not null default now(),
  primary key (freelancer_id, project_id)
);

create table saved_freelancers (
  client_id      text not null references clients(id) on delete cascade,
  freelancer_id  text not null references freelancers(id) on delete cascade,
  created_at     timestamptz not null default now(),
  primary key (client_id, freelancer_id)
);

-- Feedback loop (PRD section 7): invites, shortlists, offers, hires, declines and reviews,
-- with the match score at the time, so the weights can be tuned later.
create table match_events (
  id             bigint generated always as identity primary key,
  event          text not null,
  project_id     text references projects(id) on delete set null,
  freelancer_id  text references freelancers(id) on delete set null,
  score          int,
  created_at     timestamptz not null default now()
);

create index on projects(client_id);
create index on projects(status);
create index on proposals(project_id);
create index on proposals(freelancer_id);
create index on threads(freelancer_id);
create index on messages(thread_id, created_at);
create index on offers(freelancer_id);
create index on contracts(project_id);
create index on contracts(freelancer_id);
create index on notifications(recipient_type, recipient_id, read);

-- Lock everything down: no access with the public anon key until login policies exist.
alter table clients            enable row level security;
alter table freelancers        enable row level security;
alter table projects           enable row level security;
alter table proposals          enable row level security;
alter table threads            enable row level security;
alter table messages           enable row level security;
alter table offers             enable row level security;
alter table contracts          enable row level security;
alter table milestones         enable row level security;
alter table reviews            enable row level security;
alter table notifications      enable row level security;
alter table saved_jobs         enable row level security;
alter table saved_freelancers  enable row level security;
alter table match_events       enable row level security;
