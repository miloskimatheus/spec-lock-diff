select
    invoice_id,
    customer_document,
    invoice_date,
    invoice_total
from {{ ref('stg_invoices') }}
