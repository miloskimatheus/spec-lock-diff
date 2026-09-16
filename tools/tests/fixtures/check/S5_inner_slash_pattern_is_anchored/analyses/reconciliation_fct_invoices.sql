select 'invoiced_amount' as metric, sum(invoice_total) as model_value, 1000000.00 as external_value
from {{ ref('fct_invoices') }}
