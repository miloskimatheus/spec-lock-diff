select invoice_id, invoice_total, invoice_total * 0.9 as invoice_net
from {{ ref('stg_invoices') }}
