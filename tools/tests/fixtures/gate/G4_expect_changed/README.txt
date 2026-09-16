The expected rows now include the cancelled order the edge says to exclude.
expect count 1
expect line BLOCK\tmodels/marts/fct_orders.yml\tfct_orders\tunit test 'cancelled_orders_are_excluded' was changed; the rows it is given and the rows it expects are the question and the answer, and this PR wrote both\t[G4]
