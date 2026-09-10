dbt_project.yml gains +severity: warn for every test in the project. The gate
does not read what the change does; it blocks that it happened.
expect count 1
