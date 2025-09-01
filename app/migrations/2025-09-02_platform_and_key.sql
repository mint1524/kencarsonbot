-- Active role per user
alter table users add column if not exists active_role text check (active_role in ('user','redactor','admin'));

-- Global settings
create table if not exists settings (
  key text primary key,
  value text not null
);
insert into settings(key, value) values ('platform_commission_percent','30')
on conflict (key) do nothing;

-- Top-ups (balance deposits)
create table if not exists topups (
  id bigserial primary key,
  user_id bigint not null references users(tg_id) on delete cascade,
  provider text not null,
  invoice_id bigint,
  status text not null default 'pending',
  currency text,
  amount numeric(12,2),
  created_at timestamptz default now() not null,
  updated_at timestamptz default now() not null
);
create index if not exists idx_topups_user_status on topups(user_id, status);

-- Purchases extra fields for "key" orders
alter table purchases add column if not exists deadline_at timestamptz;
alter table purchases add column if not exists client_comment text;
create index if not exists idx_purchases_key_queue on purchases(kind, status, assigned_to, deadline_at);

-- Withdrawals
create table if not exists withdrawals (
  id bigserial primary key,
  user_id bigint not null references users(tg_id) on delete cascade,
  amount numeric(12,2) not null check (amount > 0),
  method text not null,
  requisites jsonb not null,
  status text not null default 'requested' check (status in ('requested','approved','paid','rejected')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  processed_by bigint
);
create index if not exists idx_withdrawals_status on withdrawals(status, created_at desc);
