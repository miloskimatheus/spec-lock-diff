-- Invented rows, as in stg_orders. customer_document is a label, never a real one.
select 1 as invoice_id, 'DOC-0001' as customer_document, 400.00 as invoice_total,
       date '2025-01-31' as invoice_date
union all
select 2, 'DOC-0002', 600.00, date '2025-01-31'
