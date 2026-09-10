-- Invented rows, so the project parses on any adapter without a source to read.
select 1 as order_id, 'shipped' as status, 100.00 as order_total,
       date '2025-01-15' as order_date, 'buyer@example.com' as customer_email
union all
select 2, 'partially_shipped', 250.00, date '2025-01-20', 'other@example.com'
union all
select 3, 'cancelled', 90.00, date '2025-01-22', 'third@example.com'
