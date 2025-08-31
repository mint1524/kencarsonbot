-- расширение для UUID (используем gen_random_uuid)
create extension if not exists pgcrypto;

-- USERS
create table users (
  tg_id      bigint primary key,
  username   varchar(300),
  balance    numeric(12,2) not null default 0,
  created_at timestamptz   not null default now()
);

-- COURSES
create table courses (
  id   bigserial primary key,
  name text not null
);

-- ENUM для статусов работ
do $$ begin
  if not exists (select 1 from pg_type where typname = 'work_status') then
    create type work_status as enum ('not_in_progress','in_progress','ready');
  end if;
end $$;

-- WORKS
create table works (
  id          bigserial primary key,
  course_id   bigint not null references courses(id) on delete restrict,
  name        varchar(100) not null,
  description text,
  status      work_status not null default 'not_in_progress',
  author      bigint not null references users(tg_id) on delete restrict,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

-- VARIANTS (две цены на работу)
create table variants (
  id            bigserial primary key,
  work_id       bigint not null references works(id) on delete cascade,
  price_key     numeric(12,2),      -- «под ключ» (может быть NULL)
  price_regular numeric(12,2)       -- «готовая» (может быть NULL)
);

-- PURCHASES
create table purchases (
  id         uuid primary key default gen_random_uuid(),
  buyer_id   bigint not null references users(tg_id) on delete restrict,
  variant_id bigint not null references variants(id) on delete restrict,
  kind       text   check (kind in ('ready','key')), -- что куплено
  price      numeric(12,2),                          -- зафиксированная цена
  status     text not null default 'pending'
             check (status in ('pending','paid','cancelled','refunded')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- ROLES
create table roles (
  id   bigserial primary key,
  name text unique not null check (name in ('user','redactor','admin'))
);

-- USER_ROLES (M2M)
create table user_roles (
  user_id bigint not null references users(tg_id) on delete cascade,
  role_id bigint not null references roles(id)   on delete cascade,
  primary key (user_id, role_id)
);

-- ИНДЕКСЫ
create index idx_works_course_status on works(course_id, status);
create index idx_works_author on works(author);
create index idx_variants_work on variants(work_id);
create index idx_purchases_buyer on purchases(buyer_id);
create index idx_user_roles_user on user_roles(user_id);

-- СИДЫ РОЛЕЙ
insert into roles(name) values ('user'),('redactor'),('admin')
on conflict (name) do nothing;
