{{
    config(
        enabled = false,
        tags = ["finance"]
    )
}}
select * from {{ ref('fct_orders') }} where gross_revenue < 0
