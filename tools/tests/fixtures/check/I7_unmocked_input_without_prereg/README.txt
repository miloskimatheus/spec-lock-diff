The model reads two refs, the unit test gives rows for one, and the model carries no
pre-registration: a reading, not a block.
expect exit 0
expect rules I7
expect absent T3
expect count 1
expect line INFO\tmodels/marts/fct_orders.yml\tfct_orders\tunit test 'every_order_finds_its_customer' has no given rows for ref('stg_customers'), which the model reads; dbt has nothing to mock it with, and a unit test that reads a relation is not a unit test; the model carries no pre-registration, so this is a reading: the rule blocks once the agent pre-registers a change (README §3 Stage C Rule 2)\t[I7]
