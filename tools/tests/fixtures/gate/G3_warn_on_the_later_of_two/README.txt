severity: warn on whichever of two same-named tests sorts later by arguments.
Same blind spot as G2_where_on_the_later_of_two: the verdict used to depend on
alphabetical order of the test arguments, not on what changed.
expect count 1
expect line BLOCK\tmodels/marts/fct_orders.yml\tfct_orders\ttest 'relationships' on fct_orders.customer_id (field=customer_id, to=ref('dim_customers')) was downgraded from error to warn, so it cannot block\t[G3]
