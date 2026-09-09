-- fails when an order is dated after today
select order_id from {{ ref('fct_orders') }} where order_date > current_date
