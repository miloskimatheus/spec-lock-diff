"""slp - the deterministic gates of Spec-Lock-Diff. No network, no model, no warehouse.

    check    every model in models/marts/ has a complete spec, a valid
             pre-registration when it has one, and a uniqueness test on its PK
    gate     nothing on this branch weakened a test, a unit test, a
             reconciliation, a package pin or a spec, and no model changed
             without a pre-registration to hold its numbers against
    compare  every number in a diff.json is inside the interval the
             pre-registration declared before the code was written

Exit codes: 0 nothing to report, 1 at least one BLOCK, 2 the tool could not do
its job. 2 is a failure, never a pass: what cannot be read cannot be approved.
"""

from __future__ import annotations

import argparse
import pathlib
import sys
from collections.abc import Sequence

from . import rules
from .findings import Finding, SlpError, _count, report
from .gitread import Gate, git, inventory
from .project import MARTS, _dirs, read_project
from .readers import load_json
from .rules.common import apply_rules
from .rules.compare import Diff, Run, compare_contract, stale_preregs
from .version import __version__


def cmd_check(args: argparse.Namespace) -> int:
    """check: read the project, run the check rules, print what they found.

    The note says how many models were held to the framework and how many were
    read at all. Only the first is coverage, and a count of everything reads
    like one.
    """
    project = read_project(args.project_dir, args.marts_path)
    inside = sum(1 for m in project.models.values() if m.is_marts)
    return report(
        apply_rules(rules.CHECK_RULES, project),
        "check",
        "%s in %s, of %s read"
        % (
            _count(inside, "model") or "no model",
            ", ".join(_dirs(args.marts_path)),
            _count(len(project.models), "model") or "none",
        ),
    )


def cmd_gate(args: argparse.Namespace) -> int:
    """gate: compare the merge-base with head, and walk the commits between them."""
    root = pathlib.Path(args.project_dir).resolve()
    # The merge-base, not the branch tip: a main that moved on is not this PR's doing.
    base = git(root, "merge-base", args.base, args.head).strip()
    commits = git(
        root, "rev-list", "--first-parent", "--reverse", "%s..%s" % (base, args.head)
    ).split()
    if not commits:
        return report([], "gate", "no commits")
    marts = tuple(args.marts_path)
    # read_project refuses a marts path that is not a directory, and gate never
    # saw that refusal: it reads git, where a path that is not there is not a
    # missing folder but a prefix matching nothing, and every marts rule then
    # passes over the empty set. Same refusal, from the side that reads git.
    listed = git(root, "ls-tree", "-r", "--name-only", args.head, "--", *_dirs(marts))
    for path in _dirs(marts):
        if not any(line.startswith(path) for line in listed.splitlines()):
            raise SlpError("%s holds no file at %s; nothing to check is not OK" % (path, args.head))
    before, after = inventory(root, base, marts=marts), inventory(root, args.head, marts=marts)
    # The walk starts at the merge-base and ends at head, both already read.
    walk = [before] + [inventory(root, ref, False, marts) for ref in commits[:-1]] + [after]
    # Who wrote each commit of the walk, in one git process, for the rules that
    # say where on the branch something first appeared.
    who = ["main"] + git(
        root, "log", "--no-walk=unsorted", "--format=%h by %an", *commits
    ).splitlines()
    return report(
        apply_rules(rules.GATE_RULES, Gate(root, before, after, walk, marts, who)),
        "gate",
        "no changes" if before == after else _count(len(commits), "commit"),
    )


def cmd_compare(args: argparse.Namespace) -> int:
    """compare: hold every diff.json against the pre-registration of its model.

    Without --base every pre-registration in the project counts as this pull
    request's, which is stricter, never looser: C7 asks for a diff of each, and
    an inherited one is compared instead of refused.
    """
    project = read_project(args.project_dir, args.marts_path)
    stale = stale_preregs(project, args.base, args.marts_path) if args.base else set()
    out: list[Finding] = []
    measured: set[str] = set()
    for path in args.diffs:
        data = load_json(path)
        data = data if isinstance(data, dict) else {}
        named = data.get("model")
        name = named if isinstance(named, str) else ""
        ctx = Diff(str(path), name, data, project, project.models.get(name), False, name in stale)
        blocked = any(f.severity == "BLOCK" for f in compare_contract(ctx))
        out += apply_rules(rules.COMPARE_RULES, ctx._replace(ok=not blocked))
        measured.add(name)
    out += apply_rules(rules.COMPARE_RUN_RULES, Run(project, measured, len(args.diffs), stale))
    return report(out, "compare", _count(len(args.diffs), "file"))


def build_parser() -> argparse.ArgumentParser:
    """The command line of Section 2 of the backlog, and nothing else."""
    parser = argparse.ArgumentParser(prog="slp", description=__doc__.splitlines()[0])
    parser.add_argument("--version", action="version", version=__version__)
    subs = parser.add_subparsers(dest="command")
    check = subs.add_parser("check", help="the spec of every model in models/marts/")
    gate = subs.add_parser("gate", help="what this branch did to the tests and the spec")
    compare = subs.add_parser("compare", help="a diff against its pre-registration")
    gate.add_argument("--base", required=True, help="git ref the branch started from")
    gate.add_argument("--head", default="HEAD", help="git ref to judge")
    compare.add_argument("diffs", nargs="+", metavar="diff.json")
    compare.add_argument(
        "--base",
        help="git ref the branch started from; a pre-registration "
        "already there at the merge-base is main's, not this PR's",
    )
    for sub in (check, gate, compare):
        sub.add_argument("--project-dir", default=".", help="root of the dbt project")
        sub.add_argument(
            "--marts-path",
            action="append",
            metavar="PATH",
            help="directory the framework makes mandatory; repeat for "
            "more than one (default: %s)" % ", ".join(MARTS),
        )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse, run, and turn anything unexpected into exit code 2."""
    # A console that cannot encode a character - an ASCII locale in a bare
    # container, a model name in a script the code page lacks - must not turn a
    # verdict into "unexpected UnicodeEncodeError", exit 2. The character is
    # written escaped instead, and the exit code stays the verdict's.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "marts_path", None) is None:
        args.marts_path = list(MARTS)
    if not args.command:
        parser.print_usage(sys.stderr)
        return 2
    try:
        return {"check": cmd_check, "gate": cmd_gate, "compare": cmd_compare}[args.command](args)
    except SlpError as exc:
        sys.stderr.write("ERROR %s\n" % exc)
        return 2
    except Exception as exc:  # fail closed: an unexpected error is never a pass
        sys.stderr.write("ERROR unexpected %s: %s\n" % (type(exc).__name__, exc))
        return 2
