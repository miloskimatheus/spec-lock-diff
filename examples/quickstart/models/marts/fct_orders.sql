select
    order_id,
    customer_email,
    order_date,
    order_total as gross_revenue
from {{ ref('stg_orders') }}
where status != 'cancelled'
