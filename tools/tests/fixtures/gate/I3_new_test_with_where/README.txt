A test the branch adds with a where. Nothing was weakened - it has no earlier
self - and it still asserts nothing about the rows it skips, so this is shown
and not blocked.
expect exit 0
expect rules I3
expect count 1
expect line INFO\tmodels/marts/fct_orders.yml\tfct_orders\ttest 'not_null' on fct_orders.order_id is new and skips rows with where: order_date >= '2025-01-01'\t[I3]
