limit: 0 on a test that was already there. dbt runs it, the query returns
nothing, and the test reports a pass whatever the data does.
expect rules G3
expect count 1
