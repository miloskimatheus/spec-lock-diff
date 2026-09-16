A pre-registration on a model with no spec. S1 blocks the missing spec and P2
blocks the prediction that has nothing to be measured against.
expect rules P2 S1
expect count 2
expect line BLOCK\tmodels/marts/fct_orders.yml\tfct_orders\tpre-registration without a spec: the spec is what the diff compares against\t[P2]
