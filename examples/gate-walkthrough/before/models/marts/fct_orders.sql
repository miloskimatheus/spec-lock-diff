select
    order_id,
    order_total as gross_revenue
from {{ ref('stg_orders') }}
