Severity error and limit 0: the failing rows are never returned, so the count
is 0 and dbt reports a pass.
expect count 1
