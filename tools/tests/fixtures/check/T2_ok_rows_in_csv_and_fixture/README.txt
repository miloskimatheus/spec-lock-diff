Three unit tests name the one edge: one with csv rows, which I5 counts without the header, and
one from fixture files the yml does not carry, which I5 counts as ?, and one whose
csv expect is a header alone, which is 0 rows.
expect rules I5
expect count 3
expect line INFO\tmodels/marts/fct_orders.yml\tfct_orders\tedge 'status='cancelled' -> row excluded' is proven by unit test 'cancelled_orders_are_excluded_csv', given 2 rows and expecting 1; the third reading of Stage E asks whether the expect says what the edge says\t[I5]
expect line INFO\tmodels/marts/fct_orders.yml\tfct_orders\tedge 'status='cancelled' -> row excluded' is proven by unit test 'cancelled_orders_are_excluded_from_a_file', given ? rows and expecting ?; the third reading of Stage E asks whether the expect says what the edge says\t[I5]
expect line INFO\tmodels/marts/fct_orders.yml\tfct_orders\tedge 'status='cancelled' -> row excluded' is proven by unit test 'cancelled_orders_are_excluded_to_nothing', given 1 rows and expecting 0; the third reading of Stage E asks whether the expect says what the edge says\t[I5]
