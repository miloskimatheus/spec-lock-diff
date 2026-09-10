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
    assert out.strip().endswith("slp check: OK (1 model in models/marts/, of 1 model read)")


def test_the_summary_counts_what_was_checked_apart_from_what_was_read():
    """A count of every model read reads like coverage. Only the marts ones are."""
    code, out, _ = run_slp(["check", "--marts-path", "models/core"], CLI / "other_marts")
    assert code == 0
    assert out.strip().endswith("slp check: OK (1 model in models/core/, of 2 models read)")


def test_marts_somewhere_else_is_an_error_until_the_flag_says_where():
    """R3: a tool pointed at a folder that is not there has checked nothing."""
    code, _, err = run_slp(["check"], CLI / "other_marts")
    assert code == 2
    assert "models/marts/ not found" in err


def test_more_than_one_marts_path_is_read_as_one_set():
    case = CLI / "other_marts"
    code, out, _ = run_slp(["check", "--marts-path", "models/core",
                            "--marts-path", "models/staging"], case)
    assert code == 1  # stg_orders is now a marts model, and it has no spec
    assert "models/staging/stg_orders.yml" in out and "[S1]" in out


@pytest.mark.parametrize("case,expected", [
    ("tab_indent", "cannot parse"),
    ("no_marts", "models/marts/ not found"),
    ("ambiguous_spec", "ambiguous"),
    ("arguments_twice", "ambiguous"),
    ("where_twice", "ambiguous"),
    ("jinja_yml", "contains jinja, which these tools do not render"),
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
