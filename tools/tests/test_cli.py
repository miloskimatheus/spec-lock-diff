"""The entry point itself: arguments, loaders, exit codes (SLP-02).

Every case here is about the machinery all three commands share, so it keeps
working no matter which rules are registered.
"""

import pytest

from conftest import FIXTURES, run_slp

CLI = FIXTURES / "cli"


def test_version_is_printed():
    code, out, _ = run_slp(["--version"], CLI)
    assert code == 0
    assert out.strip()[0].isdigit()


def test_unknown_command_is_an_error():
    code, _, err = run_slp(["invent"], CLI)
    assert code == 2
    assert "usage" in err.lower()


def test_no_command_prints_usage():
    code, _, err = run_slp([], CLI)
    assert code == 2
    assert "usage" in err.lower()


def test_valid_project_passes_with_a_model_count():
    code, out, err = run_slp(["check"], CLI / "valid")
    assert (code, err) == (0, "")
    assert out.strip().endswith("slp check: OK (1 model)")


@pytest.mark.parametrize("case,expected", [
    ("tab_indent", "cannot parse"),
    ("no_marts", "models/marts/ not found"),
    ("ambiguous_spec", "ambiguous"),
])
def test_what_cannot_be_read_is_never_a_pass(case, expected):
    """R3, fail closed: an unreadable project is exit 2, not exit 0."""
    code, out, err = run_slp(["check"], CLI / case)
    assert code == 2, out
    assert err.startswith("ERROR ") and expected in err


@pytest.mark.parametrize("case,args", [
    ("valid", ["check"]),
    ("no_marts", ["check"]),
    ("valid", ["--version"]),
])
def test_the_shipped_command_line_agrees_with_the_one_the_tests_call(case, args):
    """The suite runs slp in process for speed; CI runs `python tools/slp.py`."""
    assert run_slp(args, CLI / case) == run_slp(args, CLI / case, as_subprocess=True)
