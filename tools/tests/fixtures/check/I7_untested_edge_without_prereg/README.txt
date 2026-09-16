A spec with one known edge, no unit test that names it, and no pre-registration: not the model
the agent is changing, so a reading, not a block.
expect exit 0
expect rules I7
expect absent T2
expect count 1
expect line INFO\tmodels/marts/fct_orders.yml\tfct_orders\tno unit test names the edge 'status='cancelled' -> row excluded' in config.meta.edge; each edge becomes a unit test, and the name is what lets a machine tell which; the model carries no pre-registration, so this is a reading: the rule blocks once the agent pre-registers a change (README §3 Stage C Rule 2)\t[I7]
