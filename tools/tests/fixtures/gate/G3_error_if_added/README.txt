The test now tolerates ten failures before it calls them a failure.
expect count 1
expect line BLOCK\tmodels/marts/fct_orders.yml\tfct_orders\ttest 'unique' on fct_orders.order_id sets error_if, which changes what counts as failing\t[G3]
