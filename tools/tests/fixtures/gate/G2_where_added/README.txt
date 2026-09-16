The unique test now runs on fewer rows: the rows that were failing.
expect count 1
expect line BLOCK\tmodels/marts/fct_orders.yml\tfct_orders\ttest 'unique' on fct_orders.order_id now skips rows with where: status != 'cancelled'\t[G2]
