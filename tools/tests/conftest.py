"""Helpers every test uses.

The tests run `slp.py` as a subprocess, exactly like CI does, so what is tested
is the real entry point and never an internal shortcut.

Fixture conventions
-------------------
    fixtures/schemas/{spec,pre_registration,diff}/{valid,invalid}/
    fixtures/check/<case>/models/marts/...
    fixtures/gate/<CASE>/{before,after}/...     (before, mid, after when a case
                                                 needs three commits)
    fixtures/compare/<case>/{diff.json, models/marts/...}
    fixtures/compare_base/<case>/{before,after}/... + diff.json
                                                (compare --base needs a history,
                                                 so these are repositories)

A fixture folder is named `<RULE_ID>_<what_happens>` when it must block, and
`<RULE_ID>_ok_<what_happens>` when it must pass. The name is the expectation.
Every folder also holds a `README.txt` of one or two lines saying what changes.
When the name cannot carry the truth - an INFO-only rule, a case named after a
symptom rather than a rule - the README.txt adds machine-readable lines:

    expect exit 0        the exit code the case must produce
    expect rules I1 G1   rule ids that must appear in the output
    expect absent G2     rule ids that must not appear
    expect count 2       the exact number of findings
"""

import contextlib
import io
import os
import pathlib
import re
import shutil
import subprocess
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))  # so a test can import slp and read one schema
SLP = TOOLS / "slp.py"
FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"

# One author, one email, one date: two runs of the suite build the same repository
# and therefore produce the same output (R4). The email is synthetic (R9).
GIT_ENV = {
    "GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.com",
    "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.com",
    "GIT_AUTHOR_DATE": "2025-01-01T00:00:00+00:00",
    "GIT_COMMITTER_DATE": "2025-01-01T00:00:00+00:00",
}


def run_slp(args, cwd, as_subprocess=False):
    """Run slp with args as if typed in cwd. Returns (exit code, stdout, stderr).

    In process by default: `python slp.py` costs a third of a second to start,
    and the suite has to stay under ten seconds. `as_subprocess=True` runs the
    real command line, which is what CI runs; test_cli.py proves the two agree.
    """
    if as_subprocess:
        done = subprocess.run([sys.executable, str(SLP)] + list(args), cwd=str(cwd),
                              capture_output=True, text=True)
        return done.returncode, done.stdout, done.stderr
    import slp
    out, err = io.StringIO(), io.StringIO()
    here = os.getcwd()
    os.chdir(str(cwd))
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = slp.main(list(args))
            except SystemExit as exc:  # argparse exits on a bad command line
                code = exc.code if isinstance(exc.code, int) else 2
    finally:
        os.chdir(here)
    return code, out.getvalue(), err.getvalue()


def git(repo, *args):
    """Run one git command in repo with the fixed identity. Raises if it fails."""
    env = dict(os.environ)
    env.update(GIT_ENV)
    return subprocess.run(["git", "-C", str(repo), "-c", "commit.gpgsign=false",
                           "-c", "core.hooksPath=/dev/null"] + list(args),
                          capture_output=True, text=True, env=env, check=True).stdout


def make_repo(tmp_path, *trees):
    """Build a git repository whose commits are the given fixture trees, in order.

    Each tree is a whole snapshot: what a tree does not contain is deleted, so a
    fixture can express a removed file. The first commit is tagged `base`, which
    is what `gate --base base` compares against.
    """
    repo = pathlib.Path(tmp_path) / "repo"
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", "main", "--template=")  # no sample hooks to copy
    for number, tree in enumerate(trees, start=1):
        for path in sorted(repo.iterdir()):
            if path.name != ".git":
                shutil.rmtree(path) if path.is_dir() else path.unlink()
        shutil.copytree(str(tree), str(repo), dirs_exist_ok=True)
        # Forget the index before adding: git trusts size and mtime, and two fixture
        # trees written in the same second with the same file size look identical
        # to it. Rebuilding the index from the tree hashes the content instead.
        git(repo, "rm", "-r", "--cached", "-q", "--ignore-unmatch", ".")
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "--allow-empty", "-m", "commit %d" % number)
        if number == 1:
            git(repo, "tag", "base")
    return repo


def findings(stdout):
    """The finding lines of an output, as (severity, file, model, message, rule id)."""
    out = []
    for line in stdout.splitlines():
        parts = line.split("\t")
        if len(parts) == 5 and parts[0] in ("BLOCK", "INFO"):
            out.append(tuple(parts[:4]) + (parts[4].strip("[]"),))
    return out


def expectation(folder):
    """What a fixture folder promises: the exit code and the rule ids to look for."""
    name = folder.name
    rule = name.split("_")[0] if re.match(r"^[A-Z]\d+_", name) else ""
    want = {"exit": 0 if "_ok_" in name or name.endswith("_ok") else 1, "count": None}
    readme = folder / "README.txt"
    said = {}
    for line in readme.read_text(encoding="utf-8").splitlines() if readme.exists() else []:
        words = line.split()
        if len(words) >= 3 and words[0] == "expect":
            said[words[1]] = int(words[2]) if words[1] in ("exit", "count") else words[2:]
    want.update(said)
    if "rules" not in said:  # a case that blocks prints its rule; one that passes does not
        want["rules"] = [rule] if rule and want["exit"] == 1 else []
    if "absent" not in said:
        want["absent"] = [rule] if rule and want["exit"] == 0 else []
    want["absent"] = [r for r in want["absent"] if r not in want["rules"]]
    return want


def assert_expected(folder, code, stdout, stderr=""):
    """Check one fixture against what its name and its README.txt promise."""
    want = expectation(folder)
    got = findings(stdout)
    printed = [f[4] for f in got]
    assert code == want["exit"], "%s: exit %d\n%s%s" % (folder.name, code, stdout, stderr)
    for rule in want["rules"]:
        assert rule in printed, "%s: no [%s] in\n%s" % (folder.name, rule, stdout)
    for rule in want["absent"]:
        assert rule not in printed, "%s: unexpected [%s] in\n%s" % (folder.name, rule, stdout)
    if want["count"] is not None:
        assert len(got) == want["count"], "%s: %d findings\n%s" % (folder.name, len(got), stdout)
    return got


def cases(kind):
    """Every fixture folder of one command, in one order on every machine."""
    return sorted(p for p in (FIXTURES / kind).iterdir() if p.is_dir())
