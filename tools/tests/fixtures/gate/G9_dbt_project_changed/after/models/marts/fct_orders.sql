select order_id, gross_revenue
from {{ ref('stg_orders') }}
