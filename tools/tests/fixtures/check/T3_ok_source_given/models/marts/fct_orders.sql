{# ref('a_ghost_in_a_jinja_comment') #}
-- ref('a_ghost_in_a_sql_comment')
/* source('ghost', 'table') */
select o.order_id
from {{ source('raw', 'orders') }} o
join {{ ref(var('upstream')) }} u on u.order_id = o.order_id
left join {{ source(var('events_schema'), 'events') }} e on e.order_id = o.order_id
