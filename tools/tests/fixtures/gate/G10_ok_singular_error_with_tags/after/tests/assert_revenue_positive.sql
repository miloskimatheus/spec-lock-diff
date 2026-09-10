{{ config(severity="error", tags=["finance", "daily"], store_failures=true) }}
select * from {{ ref('fct_orders') }} where gross_revenue < 0
