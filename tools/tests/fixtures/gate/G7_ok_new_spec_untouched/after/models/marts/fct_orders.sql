select order_id, order_total from {{ ref('stg_orders') }}
