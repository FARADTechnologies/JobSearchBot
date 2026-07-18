-- JobSearchBot Faz 1: multi-user schema
-- Run once in Supabase SQL Editor (or psql). Idempotent where possible.

create extension if not exists vector with schema extensions;

-- ============ users ============
create table if not exists users (
  id uuid primary key default gen_random_uuid(),
  telegram_chat_id bigint unique not null,
  telegram_username text,
  full_name text,
  email text,
  -- onboarding state machine: new -> awaiting_cv -> active | paused
  state text not null default 'awaiting_cv',
  cv_pool_opt_in boolean not null default false,
  notify_frequency_hours int not null default 3,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- ============ cvs ============
create table if not exists cvs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  file_name text,
  raw_text text,
  -- structured extraction (English), produced once per CV
  profile jsonb,
  profile_source text not null default 'heuristic',  -- heuristic | groq | ...
  embedding extensions.vector(1024),                 -- BGE-M3 (filled later)
  is_active boolean not null default true,
  created_at timestamptz not null default now()
);
create index if not exists cvs_user_idx on cvs(user_id) where is_active;

-- ============ jobs (SHARED corpus - analyzed once for all users) ============
create table if not exists jobs (
  id text primary key,                    -- source job id
  source text not null default 'jobsearch.az',
  url text not null,
  title text,
  company text,
  category text,
  description text,                       -- full text, cached after first enrichment
  deadline_at timestamptz,
  created_at_source text,
  extracted jsonb,                        -- structured extraction (English), once
  embedding extensions.vector(1024),      -- BGE-M3 (filled later)
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  is_open boolean not null default true
);
create index if not exists jobs_open_idx on jobs(is_open, last_seen_at);

-- ============ matches (per-user decisions + feedback = data flywheel) ======
create table if not exists matches (
  id bigint generated always as identity primary key,
  user_id uuid not null references users(id) on delete cascade,
  job_id text not null references jobs(id) on delete cascade,
  label text not null,                    -- HIGH_MATCH | MAYBE_MATCH | NO_MATCH
  confidence int,
  reason text,
  source text,                            -- title_prefilter | heuristic | groq | judge
  notified_at timestamptz,
  -- feedback signals (future moat: labelled data)
  clicked_at timestamptz,
  saved_at timestamptz,
  applied_at timestamptz,
  dismissed_at timestamptz,
  created_at timestamptz not null default now(),
  unique (user_id, job_id)
);
create index if not exists matches_user_idx on matches(user_id);

-- ============ app_state (telegram offset, cursors) ============
create table if not exists app_state (
  key text primary key,
  value jsonb not null,
  updated_at timestamptz not null default now()
);

-- ============ security: lock everything down ============
-- RLS on; NO policies => anon/authenticated see nothing.
-- Backend uses the secret (service_role) key which bypasses RLS.
alter table users     enable row level security;
alter table cvs       enable row level security;
alter table jobs      enable row level security;
alter table matches   enable row level security;
alter table app_state enable row level security;

-- "Automatically expose new tables" is OFF, so grant service_role explicitly.
grant usage on schema public to service_role;
grant all on all tables in schema public to service_role;
grant all on all sequences in schema public to service_role;
