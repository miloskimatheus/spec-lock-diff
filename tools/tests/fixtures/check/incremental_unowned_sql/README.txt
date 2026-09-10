A standard model whose sql says materialized='incremental', in a directory
CODEOWNERS does not list. Control 5A asks for incremental models to be listed
explicitly, because a selector cannot tell one from another.
expect rules S5
expect count 2
