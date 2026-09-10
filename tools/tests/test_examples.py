"""The example against the tools, so the page a reader tries first cannot lie.

An example that no longer runs is worse than no example: it is the first thing
anyone tries and the last thing anyone remembers to update. So every command its
READMEs print is run here, and the output compared line for line. A change to
the wording of a summary line reds a test in `examples/` - which is the point.
"""

import re

import pytest

from conftest import EXAMPLES, TOOLS, findings, make_repo, run_slp

ROOT = TOOLS.parent
QUICKSTART = EXAMPLES / "quickstart"
WALKTHROUGH = EXAMPLES / "gate-walkthrough"

# A vendored tools/ has no examples/ beside it, and its owner still runs this
# suite as the install page tells them to. Skipping is right there; a silent skip
# in *this* repository would not be, which is what the last test in the file is for.
needs_examples = pytest.mark.skipif(not EXAMPLES.is_dir(),
                                    reason="no examples/ beside this tools/")


def _pinned(readme):
    """Every fenced block that opens with a command: (argv, the output it promises)."""
    blocks = re.findall(r"^```\n(.*?)^```$", readme.read_text(encoding="utf-8"), re.S | re.M)
    out = []
    for block in blocks:
        lines = block.rstrip("\n").split("\n")
        if lines[0].startswith("$ python tools/slp.py"):
            argv = lines[0][len("$ python tools/slp.py"):].split()
            out.append((argv, "\n".join(lines[1:])))
    return out


def _expand(argv):
    """The command line as a shell would hand it over, globs and all."""
    args = []
    for token in argv:
        if "*" in token:
            args.extend(sorted(p.relative_to(ROOT).as_posix() for p in ROOT.glob(token)))
        else:
            args.append(token)
    return args


def _cases():
    if not EXAMPLES.is_dir():
        return []
    return [(readme.parent.name, argv, want)
            for readme in sorted(EXAMPLES.glob("*/README.md"))
            for argv, want in _pinned(readme)]


CASES = _cases()


@needs_examples
@pytest.mark.parametrize("folder,argv,want", CASES,
                         ids=["%s-%s" % (folder, argv[0]) for folder, argv, _ in CASES])
def test_the_readme_prints_what_the_command_prints(folder, argv, want):
    """The output in the example's README is the output, not a paraphrase of it."""
    code, stdout, stderr = run_slp(_expand(argv), ROOT)
    assert stdout.rstrip("\n") == want, "%s: %s\n%s%s" % (folder, argv, stdout, stderr)
    assert code == 0, "%s: exit %d" % (folder, code)


@needs_examples
def test_the_quickstart_has_something_to_check():
    """A pass on nothing reads exactly like a pass. Both numbers are asserted."""
    code, stdout, _ = run_slp(["check", "--project-dir", str(QUICKSTART)], ROOT)
    assert code == 0, stdout
    assert stdout.strip() == "slp check: OK (2 models in models/marts/, of 4 models read)"


@needs_examples
def test_the_quickstart_diffs_are_inside_what_was_pre_registered():
    """Stage E on numbers that pass: every I2 line printed, and no C7 missing diff."""
    diffs = sorted(str(p) for p in (QUICKSTART / "diff").glob("*.json"))
    code, stdout, stderr = run_slp(["compare", "--project-dir", str(QUICKSTART)] + diffs, ROOT)
    assert code == 0, stdout + stderr
    printed = [f[4] for f in findings(stdout)]
    assert "C7" not in printed and not [f for f in findings(stdout) if f[0] == "BLOCK"]
    for model in ("fct_orders", "fct_invoices"):
        assert [f for f in findings(stdout) if f[2] == model and f[4] == "I2"], model


@needs_examples
def test_the_walkthrough_blocks_on_the_test_the_agent_deleted(tmp_path):
    """G1, from two commits the harness builds the way the README tells a human to."""
    repo = make_repo(tmp_path, WALKTHROUGH / "before", WALKTHROUGH / "after")
    code, stdout, stderr = run_slp(["gate", "--base", "base"], repo)
    assert code == 1, stdout + stderr
    assert [f[4] for f in findings(stdout)] == ["G1"]
    assert "exists on main but not in this PR" in stdout
    # Its README cannot print a command a reader can run here - the walkthrough is
    # two commits somebody makes by hand - so the output block is pinned instead.
    printed = re.findall(r"^```\n(BLOCK.*?)^```$",
                         (WALKTHROUGH / "README.md").read_text(encoding="utf-8"), re.S | re.M)
    assert printed == [stdout.rstrip("\n") + "\n"], stdout


@needs_examples
def test_the_example_has_nothing_left_to_fill_in():
    """A placeholder in an example means it was never run. Neither marker survives."""
    for path in sorted(p for p in EXAMPLES.rglob("*") if p.is_file()):
        text = path.read_text(encoding="utf-8", errors="replace")
        where = path.relative_to(EXAMPLES).as_posix()
        assert "YOU:" not in text, where
        assert "@your-org" not in text, where


@needs_examples
def test_the_examples_agents_md_keeps_the_templates_eight_rules():
    """The example is the template with its three blanks filled, not a rewrite of it."""
    template = (TOOLS / "templates" / "AGENTS.md").read_text(encoding="utf-8")
    rules = template.split("## The 8 rules")[1].split("## Before you commit")[0]
    assert rules in (QUICKSTART / "AGENTS.md").read_text(encoding="utf-8")


def test_the_example_is_here_when_the_repository_is():
    """The one test above that never skips, so the skip cannot hide a deletion.

    Either this is the spec-lock-diff repository, and examples/ is in it, or it is
    a tools/ somebody copied, and it is not. Anything else is a mistake.
    """
    assert EXAMPLES.is_dir() == (ROOT / ".github" / "workflows" / "tools-tests.yml").is_file()
