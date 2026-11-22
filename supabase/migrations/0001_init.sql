-- Hisaab: initial schema
-- Every table except businesses reaches its owner through business_id or a parent row.

-- ---------------------------------------------------------------------------
-- Tables
-- ---------------------------------------------------------------------------

create table businesses (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid references auth.users(id) on delete cascade,
  name text not null,
  type text,
  language text default 'hi-IN',
  currency text not null default 'INR',
  opening_balance numeric not null default 0,
  safety_buffer numeric not null default 0,
  created_at timestamptz not null default now()
);

create table customers (
  id uuid primary key default gen_random_uuid(),
  business_id uuid not null references businesses(id) on delete cascade,
  name text not null,
  phone text,
  guardian_name text,
  monthly_fee numeric not null,
  due_day int not null check (due_day between 1 and 28),
  batch text,
  status text not null default 'active' check (status in ('active','paused','left')),
  created_at timestamptz not null default now()
);

create table payer_aliases (
  id uuid primary key default gen_random_uuid(),
  customer_id uuid not null references customers(id) on delete cascade,
  alias_type text not null check (alias_type in ('upi_id','payer_name')),
  alias_value text not null,
  confirmed_at timestamptz,
  created_at timestamptz not null default now(),
  unique (customer_id, alias_type, alias_value)
);

create table invoices (
  id uuid primary key default gen_random_uuid(),
  customer_id uuid not null references customers(id) on delete cascade,
  business_id uuid not null references businesses(id) on delete cascade,
  period text not null check (period ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'),
  amount numeric not null,
  due_date date not null,
  status text not null default 'draft' check (status in ('draft','sent','partially_paid','paid','overdue')),
  payment_link_id text,
  payment_link_url text,
  paid_at timestamptz,
  created_at timestamptz not null default now(),
  unique (customer_id, period)
);

create table payments (
  id uuid primary key default gen_random_uuid(),
  business_id uuid not null references businesses(id) on delete cascade,
  invoice_id uuid references invoices(id) on delete set null,
  amount numeric not null,
  method text not null check (method in ('upi','cash','card','other')),
  source text not null check (source in ('link_webhook','sms','manual','voice')),
  payer_text text,
  upi_id text,
  upi_ref text,
  received_at timestamptz not null default now(),
  match_confidence int check (match_confidence between 0 and 100),
  match_status text not null default 'unmatched' check (match_status in ('matched','needs_review','unmatched')),
  created_at timestamptz not null default now()
);

create table bills (
  id uuid primary key default gen_random_uuid(),
  business_id uuid not null references businesses(id) on delete cascade,
  name text not null,
  amount numeric not null,
  due_day int not null check (due_day between 1 and 28),
  recurrence text not null check (recurrence in ('monthly','once')),
  next_due_date date,
  category text,
  created_at timestamptz not null default now()
);

create table reminders (
  id uuid primary key default gen_random_uuid(),
  invoice_id uuid not null references invoices(id) on delete cascade,
  tone text not null check (tone in ('nudge','polite','firm','formal')),
  language text,
  text text not null,
  status text not null default 'drafted' check (status in ('drafted','opened','sent')),
  sent_at timestamptz,
  created_at timestamptz not null default now()
);

create table agent_events (
  id uuid primary key default gen_random_uuid(),
  business_id uuid not null references businesses(id) on delete cascade,
  transcript text,
  language text,
  intent text,
  tool_name text,
  tool_args jsonb,
  result jsonb,
  confirmed boolean default false,
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------

create index customers_business_id_idx on customers (business_id);
create index invoices_business_id_idx on invoices (business_id);
create index invoices_status_due_date_idx on invoices (status, due_date);
create index payments_business_id_idx on payments (business_id);
create index payments_received_at_idx on payments (received_at);
create index bills_business_id_idx on bills (business_id);
create index agent_events_business_id_idx on agent_events (business_id);

-- ---------------------------------------------------------------------------
-- Row level security: a row is visible/writable only when its business is
-- owned by auth.uid().
-- ---------------------------------------------------------------------------

alter table businesses enable row level security;
alter table customers enable row level security;
alter table payer_aliases enable row level security;
alter table invoices enable row level security;
alter table payments enable row level security;
alter table bills enable row level security;
alter table reminders enable row level security;
alter table agent_events enable row level security;

create policy businesses_owner_all on businesses
  for all
  using (owner_user_id = auth.uid())
  with check (owner_user_id = auth.uid());

create policy customers_owner_all on customers
  for all
  using (business_id in (select id from businesses where owner_user_id = auth.uid()))
  with check (business_id in (select id from businesses where owner_user_id = auth.uid()));

create policy payer_aliases_owner_all on payer_aliases
  for all
  using (customer_id in (
    select id from customers
    where business_id in (select id from businesses where owner_user_id = auth.uid())
  ))
  with check (customer_id in (
    select id from customers
    where business_id in (select id from businesses where owner_user_id = auth.uid())
  ));

create policy invoices_owner_all on invoices
  for all
  using (business_id in (select id from businesses where owner_user_id = auth.uid()))
  with check (business_id in (select id from businesses where owner_user_id = auth.uid()));

create policy payments_owner_all on payments
  for all
  using (business_id in (select id from businesses where owner_user_id = auth.uid()))
  with check (business_id in (select id from businesses where owner_user_id = auth.uid()));

create policy bills_owner_all on bills
  for all
  using (business_id in (select id from businesses where owner_user_id = auth.uid()))
  with check (business_id in (select id from businesses where owner_user_id = auth.uid()));

create policy reminders_owner_all on reminders
  for all
  using (invoice_id in (
    select id from invoices
    where business_id in (select id from businesses where owner_user_id = auth.uid())
  ))
  with check (invoice_id in (
    select id from invoices
    where business_id in (select id from businesses where owner_user_id = auth.uid())
  ));

create policy agent_events_owner_all on agent_events
  for all
  using (business_id in (select id from businesses where owner_user_id = auth.uid()))
  with check (business_id in (select id from businesses where owner_user_id = auth.uid()));
