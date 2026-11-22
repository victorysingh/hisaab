-- ===== EDIT THIS LINE: paste the real Supabase auth user id (uuid) of the demo owner =====
-- RUN ONCE ONLY: this script inserts rows every time it runs (it deletes nothing). Run it on a fresh schema from 0001_init.sql.
-- Plain SQL for the Supabase SQL editor. All data is synthetic (no real phones or UPI IDs).

do $$
declare
  v_owner uuid := '6a5406d8-135e-4e32-a948-9deeb21b2a6d';  -- the placeholder: the ONLY place the owner id appears
  v_biz uuid;
  v_cust uuid;
  v_inv uuid;
  v_names text[] := array[
    'Rohan Sharma', 'Aisha Khan', 'Kabir Mehta', 'Ananya Iyer', 'Vihaan Patil',
    'Meera Joshi', 'Arjun Deshmukh', 'Saanvi Kulkarni', 'Dhruv Rao', 'Ishita Nair',
    'Aarav Gupta', 'Diya Reddy', 'Yash Pawar', 'Tanvi Kapoor', 'Reyansh Singh',
    'Kiara Desai', 'Advait Bhosale', 'Riya Malhotra', 'Pranav Chavan', 'Sara Qureshi',
    'Shaurya Mishra', 'Nidhi Agarwal', 'Krish Thakur', 'Anika Bansal', 'Veer Saxena',
    'Pooja Naidu', 'Om Bhatt', 'Kavya Menon', 'Atharv Jadhav', 'Tara Sinha',
    'Harsh Dubey', 'Myra Pillai', 'Ayaan Shetty', 'Zara Hussain', 'Nikhil More',
    'Sneha Ghosh', 'Parth Kale', 'Lavanya Rajan', 'Siddharth Iyengar', 'Anjali Varma'
  ];
  v_i int;
  v_n int;
  v_fee numeric;
  v_batch text;
  v_chronic boolean;
  v_m date;
  v_due date;
  v_late int;
  v_paid_date date;
  v_paid_at timestamptz;
  v_is_paid boolean;
  v_status text;
  v_period text;
  v_upi_alias text;
  v_payer_alias text;
  v_conf int;
begin
  -- Business
  insert into businesses (owner_user_id, name, type, language, currency, opening_balance)
  values (v_owner, 'Priya''s Classes', 'home_tuition', 'hi-IN', 'INR', 18000)
  returning id into v_biz;

  -- Customers, aliases, invoices, payments
  for v_i in 1..40 loop
    v_chronic := v_i in (3, 7, 11, 14, 19, 22, 27, 31);
    v_fee := case when v_i = 1 then 3000
                  when v_i in (2, 3) then 2500
                  when v_i % 2 = 1 then 3000
                  else 2500 end;
    v_batch := 'Class ' || (8 + v_i % 3);
    v_upi_alias := case v_i
                     when 1 then 'rohan.sharma@okaxis'
                     when 3 then 'kabir.mehta@ybl'
                     when 6 then 'meera.joshi@oksbi'
                     when 33 then 'ayaan.shetty@ibl'
                   end;
    v_payer_alias := case v_i
                       when 1 then 'ROHAN SHARMA'
                       when 2 then 'AISHA KHAN'
                       when 15 then 'REYANSH S SINGH'
                     end;

    insert into customers (business_id, name, phone, guardian_name, monthly_fee, due_day, batch, status)
    values (
      v_biz,
      v_names[v_i],
      '+91 90000 000' || lpad(v_i::text, 2, '0'),
      case when v_i % 2 = 0 then 'Mrs. ' else 'Mr. ' end || split_part(v_names[v_i], ' ', 2),
      v_fee,
      5,
      v_batch,
      case when v_i in (38, 39) then 'left' else 'active' end
    )
    returning id into v_cust;

    if v_upi_alias is not null then
      insert into payer_aliases (customer_id, alias_type, alias_value, confirmed_at)
      values (v_cust, 'upi_id', v_upi_alias, now());
    end if;

    if v_payer_alias is not null then
      insert into payer_aliases (customer_id, alias_type, alias_value, confirmed_at)
      values (v_cust, 'payer_name', v_payer_alias, now());
    end if;

    for v_n in 0..5 loop
      -- Left customers (38, 39) only have invoices for offsets 2..5
      continue when v_i in (38, 39) and v_n < 2;

      -- Period month = current month minus v_n months; due on the 5th
      v_m := (make_date(extract(year from current_date)::int, extract(month from current_date)::int, 1)
              - make_interval(months => v_n))::date;
      v_period := to_char(v_m, 'YYYY-MM');
      v_due := make_date(extract(year from v_m)::int, extract(month from v_m)::int, 5);

      v_late := case when v_chronic then 10 + ((v_i * 7 + v_n * 5) % 16)
                     else (v_i + v_n) % 5 end;
      v_paid_date := v_due + v_late;

      -- Customers 36 and 37 never pay; all others pay unless the payment date is still in the future
      v_is_paid := v_i not in (36, 37) and v_paid_date <= current_date;

      v_paid_at := case when v_is_paid
                        then (v_paid_date::timestamp at time zone 'Asia/Kolkata')
                        else null end;
      v_status := case when v_is_paid then 'paid'
                       when v_due < current_date then 'overdue'
                       else 'sent' end;

      insert into invoices (customer_id, business_id, period, amount, due_date, status, paid_at)
      values (v_cust, v_biz, v_period, v_fee, v_due, v_status, v_paid_at)
      returning id into v_inv;

      if v_is_paid then
        v_conf := 90 + ((v_i * 3 + v_n) % 10);

        if (v_i + v_n) % 6 = 0 then
          -- Cash, roughly 1 in 6
          insert into payments (business_id, invoice_id, amount, method, source,
                                payer_text, upi_id, upi_ref, received_at, match_confidence, match_status)
          values (v_biz, v_inv, v_fee, 'cash', 'manual',
                  null, null, null, v_paid_at, v_conf, 'matched');
        else
          -- UPI via payment-link webhook
          insert into payments (business_id, invoice_id, amount, method, source,
                                payer_text, upi_id, upi_ref, received_at, match_confidence, match_status)
          values (v_biz, v_inv, v_fee, 'upi', 'link_webhook',
                  coalesce(v_payer_alias, upper(v_names[v_i])),
                  v_upi_alias,
                  'UPI' || (100000000000 + v_i * 1000003 + v_n * 7919)::text,
                  v_paid_at, v_conf, 'matched');
        end if;
      end if;
    end loop;
  end loop;

  -- Bills: next_due_date = next occurrence of due_day on or after current_date
  insert into bills (business_id, name, amount, due_day, recurrence, next_due_date, category)
  select v_biz, b.name, b.amount, b.due_day, 'monthly', nd.d, b.category
  from (values
          ('Rent', 12000, 1, 'rent'),
          ('Assistant salary', 8000, 7, 'salary'),
          ('Electricity', 1800, 15, 'utilities'),
          ('Wi-Fi', 900, 10, 'utilities')
       ) as b(name, amount, due_day, category)
  cross join lateral (
    select case when x.mk >= current_date then x.mk
                else (x.mk + interval '1 month')::date end as d
    from (select make_date(extract(year from current_date)::int,
                           extract(month from current_date)::int,
                           b.due_day) as mk) x
  ) nd;
end $$;
