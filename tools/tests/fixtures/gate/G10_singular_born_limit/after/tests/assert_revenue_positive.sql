{{ config(severity="error", limit=0) }}
select * from {{ ref('fct_orders') }} where gross_revenue < 0
