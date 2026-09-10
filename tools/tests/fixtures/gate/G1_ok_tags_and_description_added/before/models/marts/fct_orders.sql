select order_id, date_day, status
from {{ ref('stg_orders') }}
