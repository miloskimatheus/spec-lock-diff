The uniqueness test the framework makes mandatory exists, is enabled and has
severity error - and a where that leaves it no rows to look at. It runs, it
passes, and it asserts nothing.
expect rules T1
expect count 1
expect line BLOCK\tmodels/marts/fct_orders.yml\tfct_orders\tthe uniqueness test on primary key [order_id] cannot fail the build: it sets where\t[T1]
