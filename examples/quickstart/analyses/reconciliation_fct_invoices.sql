-- Stage E step 4: the model against something that is not the model. Run on full
-- data, its two numbers go into diff/fct_invoices.json as `reconciliation`.
-- One row out: metric, model_value, external_value.
select
    'invoiced_amount'            as metric,
    sum(invoice_total)           as model_value,
    1000200.00                   as external_value
from {{ ref('fct_invoices') }}
where invoice_date >= date '2025-01-01' and invoice_date < date '2025-02-01'
