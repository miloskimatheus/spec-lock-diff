"""Installed, this directory is the package `spec_lock_diff`; vendored, it is `tools/`.

The mapping is in pyproject.toml, and it exists so that slp.py needs no edit to
work either way: SCHEMA_DIR resolves from __file__, and the schemas sit beside
the module in both worlds. Nothing imports this file.
"""
