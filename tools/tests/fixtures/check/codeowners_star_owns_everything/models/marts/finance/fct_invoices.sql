select invoice_id, invoice_total from {{ ref('stg_invoices') }}
