Projects that exercise the entry point itself, not a rule:
  valid           a complete, passing project - check must stay OK forever
  tab_indent      a yml indented with a tab - unparseable, exit 2
  no_marts        no models/marts/ - nothing to check is not OK, exit 2
  ambiguous_spec  meta.spec and config.meta.spec on the same model - exit 2
  other_marts     marts kept in models/core/ - invisible until --marts-path
                  says so, and the summary line says how many were checked
