"""Tests about the tools themselves (Section 3 of the backlog: adherence mechanisms)."""

from conftest import TOOLS


def test_folder_layout():
    """The folder every other ticket plugs into exists."""
    for path in ("slp.py", "schemas", "templates", "tests/fixtures"):
        assert (TOOLS / path).exists(), "missing tools/" + path
