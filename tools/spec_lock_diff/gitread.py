"""What the gate compares, as git sees it: the tree at two commits and one inventory per commit
between them.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
from collections.abc import Sequence
from typing import Any, NamedTuple

from .findings import SlpError
from .project import MARTS, _dirs, read_doc
from .readers import parse_yaml

# Files that pin what the project builds with. Any change to one is a G6 finding.
PKG_FILES = ("packages.yml", "package-lock.yml", "dependencies.yml")

# Paths only a human changes (README §2 Control 5A). Any change to one on the
# branch is a G9 finding. The paths with a rule of their own - the package
# files (G6), reconciliations (G5), a test file already there (G1) - are left
# to it, so that one change is one finding.
PROTECTED_DIRS = (".github/", "macros/", "models/semantic/", "docs/profile/", "tools/")

PROTECTED_FILES = (".pre-commit-config.yaml", "CODEOWNERS", "AGENTS.md", "dbt_project.yml")


# What the gate rules read: the tree at the merge-base, the tree at head, and one
# light inventory per commit in between (oldest first, merge-base included).
# What one commit holds, by kind: tests, files, units, specs, preregs, models, sqls, code,
# recons, packages, where, protected, singular. Each kind is a mapping of its own keys.
Inventory = dict[str, dict[Any, Any]]


class Gate(NamedTuple):
    root: pathlib.Path
    before: Inventory
    after: Inventory
    walk: list[Inventory]
    marts: tuple[str, ...]
    commits: list[str]


def _canon(obj: Any) -> str:
    """One text for one value, whatever order the yml file happened to use."""
    return json.dumps(obj, sort_keys=True, default=str)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def git(root: pathlib.Path, *args: str) -> str:
    """Run one read-only git command. git is the only program these tools ever run."""
    done = subprocess.run(["git", "-C", str(root)] + list(args), capture_output=True, text=True)
    if done.returncode != 0:
        raise SlpError("git %s: %s" % (" ".join(args), " ".join(done.stderr.split())))
    return done.stdout


def git_blobs(root: pathlib.Path, commit: str, paths: list[str]) -> dict[str, str]:
    """The content of many files at one commit, read down one pipe.

    `git show` costs a process per file, and the commit walk asks for every yml
    at every commit: a project of 150 models with a 30-commit branch spawned
    close to five thousand of them, twenty seconds of process start-up before a
    rule had looked at anything. `cat-file --batch` answers the lot at once.
    """
    if not paths:
        return {}
    asked = "".join("%s:%s\n" % (commit, path) for path in paths)
    done = subprocess.run(
        ["git", "-C", str(root), "cat-file", "--batch"],
        input=asked.encode("utf-8"),
        capture_output=True,
    )
    if done.returncode != 0:
        raise SlpError(
            "git cat-file: %s" % " ".join(done.stderr.decode("utf-8", "replace").split())
        )
    out: dict[str, str] = {}
    data, at = done.stdout, 0
    for path in paths:
        # One header line - sha, type, size in bytes - then that many bytes, then
        # a newline. Sizes are in bytes, so the split happens before decoding.
        end = data.index(b"\n", at)
        header = data[at:end].split()
        if len(header) != 3:
            raise SlpError(
                "cannot read %s at %s: %s"
                % (path, commit[:8], data[at:end].decode("utf-8", "replace"))
            )
        at = end + 1 + int(header[2]) + 1
        try:
            out[path] = data[end + 1 : at - 1].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SlpError("cannot read %s at %s: %s" % (path, commit[:8], exc)) from exc
    return out


def _without_prereg(entry: dict[str, Any]) -> str:
    """A model's yml entry as the gate compares it: the pre-registration does not count."""
    copy = json.loads(_canon(entry))
    for holder in (copy, copy.get("config")):
        if isinstance(holder, dict) and isinstance(holder.get("meta"), dict):
            holder["meta"].pop("pre_registration", None)
    return _canon(copy)


def _plan(listing: str, full: bool, marts: Sequence[str]) -> list[tuple[str, str]]:
    """What to read at one commit, and as what, decided before anything is read."""
    plan: list[tuple[str, str]] = []
    for path in sorted(p for p in listing.split("\0") if p):
        if path.startswith(_dirs(marts, True)) and path.endswith((".yml", ".yaml")):
            plan.append(("yml", path))
        if not full:
            continue
        if path.startswith(PROTECTED_DIRS) or path in PROTECTED_FILES:
            plan.append(("protected", path))  # a yml under models/semantic/ is read both ways
        elif path.startswith(_dirs(marts, True)) and path.endswith(".sql"):
            plan.append(("sql", path))
        elif path.startswith("tests/"):
            plan.append(("files", path))
        elif path.startswith("analyses/reconciliation_"):
            plan.append(("recons", path))
        elif path in PKG_FILES:
            plan.append(("packages", path))
    return plan


def _read_models(inv: Inventory, path: str, text: str, commit: str, marts: Sequence[str]) -> None:
    """One yml at one commit into the inventory: its models, their tests, its unit tests."""
    models, units = read_doc(parse_yaml(text, "%s at %s" % (path, commit[:8])), path, marts)
    for model in models:
        inv["where"][model.name] = path
        inv["specs"][model.name] = model.spec
        inv["preregs"][model.name] = model.prereg
        inv["models"][model.name] = _sha(_without_prereg(model.entry))
        # A list, not one config: two declarations of one test on one column
        # can differ only in their config - two `expression_is_true` with the
        # same expression and a `where` each - and one config per key made
        # the second overwrite the first, a whole test removed in silence.
        for column, name, args, cfg in model.tests:
            inv["tests"].setdefault((model.name, column, name, args), []).append(cfg)
    for unit in units:
        body = dict((k, v) for k, v in unit.body.items() if k != "description")
        # By model and name, never by name alone: dbt makes a unit test
        # unique inside its model, so two models may each hold one called
        # `cancelled_orders_are_excluded` and neither is a duplicate.
        inv["units"][(unit.model, unit.name)] = (unit.file, unit.model, _canon(body))


def inventory(
    root: pathlib.Path, commit: str, full: bool = True, marts: Sequence[str] = MARTS
) -> Inventory:
    """Everything the gate compares, as it was at one commit.

    A pure function of the commit: same commit in, same inventory out, whichever
    machine runs it. With full=False only the yml files are read, which is all
    the commit walk of G7 and I1 needs.
    """
    inv: Inventory = {
        "tests": {},
        "files": {},
        "units": {},
        "specs": {},
        "preregs": {},
        "models": {},
        "sqls": {},
        "code": {},
        "recons": {},
        "packages": {},
        "where": {},
        "protected": {},
        "singular": {},
    }
    listing = git(
        root,
        "ls-tree",
        "-r",
        "-z",
        "--name-only",
        commit,
        "--",
        *(
            _dirs(marts, True)
            + ("tests", "analyses")
            + PKG_FILES
            + tuple(p.rstrip("/") for p in PROTECTED_DIRS)
            + PROTECTED_FILES
        ),
    )
    # What to read is decided first and read in one go, so that the cost of the
    # commit walk is one git process per commit rather than one per file.
    plan = _plan(listing, full, marts)
    blobs = git_blobs(root, commit, [path for _, path in plan])
    for kind, path in plan:
        if kind == "yml":
            _read_models(inv, path, blobs[path], commit, marts)
        elif kind == "sql":
            name = path.rsplit("/", 1)[-1][:-4]
            inv["sqls"][name] = path
            inv["code"][name] = _sha(blobs[path])
        else:
            inv[kind][path] = _sha(blobs[path])
            if kind == "files" and path.endswith(".sql") and not path.startswith("tests/generic/"):
                inv["singular"][path] = blobs[path]  # G10 reads the config() it carries
    for name in inv["models"]:  # a model is its yml entry and its sql, together
        inv["models"][name] += inv["code"].get(name, "")
    return inv
