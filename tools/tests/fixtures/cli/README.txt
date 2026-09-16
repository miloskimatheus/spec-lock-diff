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
  models_not_a_list       models: is a mapping, not a list of entries - exit 2
  tests_twice             tests: and data_tests: on the same column - exit 2
  tests_not_a_list        tests: is a string - exit 2
  test_two_keys           one list item that names two tests - exit 2
  arguments_not_a_mapping arguments: is a list - exit 2
  yml_is_a_list           the yml document is a list, not a mapping - exit 2
  model_without_name      a model entry with no name - exit 2
  column_without_name     a column entry with no name - exit 2
  unit_test_without_name  a unit test whose name is empty - exit 2
  model_declared_twice    two yml files declare the same model - exit 2
  models_entry_not_a_mapping  models: is a list of names, not of entries - exit 2
  test_name_not_a_string  a test whose name is a number - exit 2
  model_with_empty_name   a model whose name is "" - exit 2
  column_with_empty_name  a column whose name is "" - exit 2
