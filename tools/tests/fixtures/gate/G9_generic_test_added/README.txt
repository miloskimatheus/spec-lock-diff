tests/generic/unique.sql appears on the branch, redefining `unique` to select
nothing. dbt resolves macros from the project first, so every `unique` in the
project now passes, and not one test file changed.
expect count 1
