Projects that exercise the entry point itself, not a rule:
  valid           a complete, passing project - check must stay OK forever
  tab_indent      a yml indented with a tab - unparseable, exit 2
  no_marts        no models/marts/ - nothing to check is not OK, exit 2
  ambiguous_spec  meta.spec and config.meta.spec on the same model - exit 2
  other_marts     marts kept in models/core/ - invisible until --marts-path
                  says so, and the summary line says how many were checked
  jinja_yml       a schema yml written with jinja, which dbt renders and these
                  tools do not - exit 2, and the message says which of the two
                  problems it is
  arguments_twice a test that gives its arguments on the test and under
                  arguments: - exit 2, the tool does not guess which dbt reads
  where_twice     a where on the test and another under config - exit 2
