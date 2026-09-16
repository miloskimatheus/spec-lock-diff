A test the agent wrote that cannot fail the build. In an agent PR every test
must be able to block; this goes beyond the README wording and is listed as a
framework issue in SLP-27.
expect count 1
expect line BLOCK\tmodels/marts/fct_orders.yml\tfct_orders\ttest 'not_null' on fct_orders.order_id is new and cannot fail the build: its severity is warn\t[G3]
