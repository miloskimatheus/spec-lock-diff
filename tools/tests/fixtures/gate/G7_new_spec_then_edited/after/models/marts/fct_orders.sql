select order_id, date_day from {{ ref('stg_orders') }}
