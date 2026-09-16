"""The entry point itself: arguments, loaders, exit codes (SLP-02).

Every case here is about the machinery all three commands share, so it keeps
working no matter which rules are registered.
"""

import importlib
import io
import os
import pathlib
import runpy
import subprocess
import sys

import pytest
from conftest import FIXTURES, SLP, TOOLS, run_slp

import spec_lock_diff as slp

CLI = FIXTURES / "cli"


def test_a_console_that_cannot_encode_the_output_still_gets_the_verdict():
    """R3: an ASCII locale turned a block into exit 2, "unexpected UnicodeEncodeError".

    The S1 message carries a section sign, and a model name may carry anything.
    On a console that cannot encode it the character is written escaped and the
    exit code stays the verdict's.
    """
    env = dict(os.environ, PYTHONIOENCODING="ascii", LC_ALL="C")
    done = subprocess.run(
        [sys.executable, str(SLP), "check"],
        cwd=str(FIXTURES / "check" / "marts_no_spec"),
        env=env,
        capture_output=True,
    )
    assert done.returncode == 1, done.stderr
    assert b"model has no meta.spec (README \\xa73 Stage A)" in done.stdout, done.stdout
    assert b"UnicodeEncodeError" not in done.stderr


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
    code, out, _ = run_slp(
        ["check", "--marts-path", "models/core", "--marts-path", "models/staging"], case
    )
    assert code == 1  # stg_orders is now a marts model, and it has no spec
    assert "models/staging/stg_orders.yml" in out and "[S1]" in out


@pytest.mark.parametrize(
    "case,expected",
    [
        ("tab_indent", "cannot parse"),
        ("no_marts", "models/marts/ not found"),
        ("ambiguous_spec", "ambiguous"),
        ("arguments_twice", "ambiguous"),
        ("where_twice", "ambiguous"),
        ("jinja_yml", "contains jinja, which these tools do not render"),
        ("models_not_a_list", "must be a list of entries"),
        ("tests_twice", "ambiguous: tests defined twice"),
        ("tests_not_a_list", "must be a list"),
        ("test_two_keys", "cannot read a test"),
        ("arguments_not_a_mapping", "must be a mapping"),
        ("yml_is_a_list", "is not a yml mapping"),
        ("model_without_name", "a model without a name"),
        ("column_without_name", "a column without a name"),
        ("unit_test_without_name", "a unit test without a name"),
        ("model_declared_twice", "is declared twice"),
        ("models_entry_not_a_mapping", "must be a list of entries"),
        ("test_name_not_a_string", "cannot read a test"),
        ("model_with_empty_name", "a model without a name"),
        ("column_with_empty_name", "a column without a name"),
    ],
)
def test_what_cannot_be_read_is_never_a_pass(case, expected):
    """R3, fail closed: an unreadable project is exit 2, not exit 0."""
    code, out, err = run_slp(["check"], CLI / case)
    assert code == 2, out
    assert err.startswith("ERROR ") and expected in err


@pytest.mark.parametrize(
    "case,args",
    [
        ("valid", ["check"]),
        ("no_marts", ["check"]),
        ("valid", ["--version"]),
    ],
)
def test_the_shipped_command_line_agrees_with_the_one_the_tests_call(case, args):
    """The suite runs slp in process for speed; CI runs `python tools/slp.py`."""
    assert run_slp(args, CLI / case) == run_slp(args, CLI / case, as_subprocess=True)


def test_a_file_the_system_will_not_hand_over_is_an_error(monkeypatch):
    """R3: a yml that exists and cannot be read is exit 2, not a project with one file fewer."""

    def refuse(self, *args, **kwargs):
        raise OSError("permission denied")

    monkeypatch.setattr(pathlib.Path, "read_text", refuse)
    code, _, err = run_slp(["check"], CLI / "valid")
    assert code == 2 and err.startswith("ERROR cannot read") and "permission denied" in err


def test_a_diff_file_that_is_not_there_is_an_error():
    """R3: compare on a missing diff.json cannot have compared anything."""
    code, _, err = run_slp(["compare", "no_such.json"], FIXTURES / "compare" / "C1_inside")
    assert code == 2 and err.startswith("ERROR cannot read no_such.json")


def test_an_unexpected_error_is_exit_2_and_never_a_pass(monkeypatch):
    """R3, the last line of main: a bug in a rule must not read as a run that found nothing."""

    def boom(project):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(slp.rules, "CHECK_RULES", [boom])
    code, out, err = run_slp(["check"], CLI / "valid")
    assert code == 2 and out == ""
    assert err == "ERROR unexpected RuntimeError: kaboom\n"


def test_a_console_that_can_be_reconfigured_is(monkeypatch):
    """The escape for a console that cannot encode a character is set on the real stream."""
    out = io.TextIOWrapper(io.BytesIO(), encoding="ascii")
    monkeypatch.setattr(sys, "stdout", out)
    with pytest.raises(SystemExit) as done:
        slp.main(["--version"])
    assert done.value.code == 0 and out.errors == "backslashreplace"
    out.flush()
    assert out.buffer.getvalue().decode("ascii").strip()[0].isdigit()


def test_the_file_runs_as_a_script(monkeypatch):
    """`python tools/slp.py` reaches main through the shim's last line."""
    monkeypatch.setattr(sys, "argv", ["slp", "--version"])
    with pytest.raises(SystemExit) as done:
        runpy.run_path(str(SLP), run_name="__main__")
    assert done.value.code == 0


def test_the_help_names_the_tool():
    """argparse prints the first line of the docstring; a reader who typed --help should meet it."""
    code, out, _ = run_slp(["--help"], CLI)
    assert code == 0 and "the deterministic gates of Spec-Lock-Diff" in out


def test_gate_without_a_base_is_a_usage_error():
    """--base is required: without it there is nothing to compare against, and argparse says so."""
    code, _, err = run_slp(["gate"], CLI / "valid")
    assert code == 2 and "the following arguments are required: --base" in err


def test_the_package_runs_as_a_module(monkeypatch):
    """Installed, `python -m spec_lock_diff` is the tool; the CI templates point at its __main__."""
    done = subprocess.run(
        [sys.executable, "-m", "spec_lock_diff", "--version"],
        cwd=str(TOOLS),
        capture_output=True,
        text=True,
    )
    assert done.returncode == 0 and done.stdout.strip() == slp.__version__, done.stderr
    # Run in this process once, so that the coverage the suite measures reads it.
    monkeypatch.setattr(sys, "argv", ["spec_lock_diff", "--version"])
    with pytest.raises(SystemExit) as exited:
        runpy.run_module("spec_lock_diff", run_name="__main__", alter_sys=True)
    assert exited.value.code == 0
    # Imported, it runs nothing: the CI templates import it to learn where it is.
    assert importlib.import_module("spec_lock_diff.__main__").__file__.endswith("__main__.py")
