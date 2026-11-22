-- Hisaab demo setup. Run once in the Supabase SQL Editor.
-- Rohan and Kabir haven't paid November yet, so the SMS simulator has something to match.
delete from payments where invoice_id in (
  select i.id from invoices i join customers c on c.id = i.customer_id
  where c.name in ('Rohan Sharma', 'Kabir Mehta') and i.period = '2026-11'
);
update invoices set status = 'overdue', paid_at = null
where period = '2026-11'
  and customer_id in (select id from customers where name in ('Rohan Sharma', 'Kabir Mehta'));

-- Cash in hand at the start of today (keeps the 1 Dec shortfall visible).
update businesses set opening_balance = 1000;
