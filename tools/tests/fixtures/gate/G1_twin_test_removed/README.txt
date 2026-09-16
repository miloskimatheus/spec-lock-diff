One column, two tests of the same name whose arguments are identical and whose
config is not. One of the two is removed; the other is untouched.
expect rules G1
expect count 1
expect line BLOCK\tmodels/marts/fct_orders.yml\tfct_orders\ttest 'dbt_utils.expression_is_true' on fct_orders.amount was declared 2 times on main and 1 here\t[G1]
