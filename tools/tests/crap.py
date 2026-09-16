#!/usr/bin/env python3
"""The tool's own code, held to two numbers nobody negotiates.

Branch coverage of the tool is 100 percent, and the CRAP score of every
function is at most 30, Alberto Savoia's crap4j threshold:

    CRAP(f) = CC(f)^2 * (1 - coverage(f))^3 + CC(f)

CC is the cyclomatic complexity counted here, by one rule written down once:
1 for the function, plus 1 for every if, elif, for, while, except, with,
assert, conditional expression and comprehension, plus 1 for every and/or
operand beyond the first, plus 1 for every if inside a comprehension; nested
definitions count towards the function that holds them. coverage(f) is the
fraction of the function's statements that ran, read from coverage.py's json
report, which this script produces from the data file the suite wrote.

Why both numbers. A fully covered function's CRAP is its complexity, so the
30 is a complexity cap too; an uncovered simple function keeps a low CRAP,
so the 100 percent is what says every branch was looked at. Neither number
moves: one is the extremum, the other a published constant, and M9 in
test_meta.py bans the comments that would exempt a line from either.

    coverage run --branch --source=tools/spec_lock_diff -m pytest tools/tests -q
    python tools/tests/crap.py        # reads the .coverage file the run wrote

Exit 0 when both hold, 1 when either does not, 2 when there is nothing to read.
"""

import ast
import json
import os
import pathlib
import sys
import tempfile

COVERAGE, CRAP = 100.0, 30.0
BRANCHES = (
    ast.If,
    ast.For,
    ast.While,
    ast.IfExp,
    ast.ExceptHandler,
    ast.With,
    ast.Assert,
    ast.AsyncFor,
    ast.AsyncWith,
)


def complexity(node):
    """The cyclomatic complexity of one function, by the rule in the docstring."""
    count = 1
    for sub in ast.walk(node):
        if isinstance(sub, BRANCHES):
            count += 1
        elif isinstance(sub, ast.BoolOp):
            count += len(sub.values) - 1
        elif isinstance(sub, ast.comprehension):
            count += 1 + len(sub.ifs)
    return count


def report():
    """coverage.py's json report for the data file in COVERAGE_FILE or .coverage."""
    try:
        import coverage
    except ImportError:
        raise SystemExit("crap: coverage.py is not installed (pip install -e '.[dev]')") from None
    cov = coverage.Coverage()
    cov.load()
    with tempfile.TemporaryDirectory() as folder:
        out = os.path.join(folder, "coverage.json")
        cov.json_report(outfile=out)
        return json.load(open(out, encoding="utf-8"))


def scores(path, measured):
    """(crap, complexity, coverage fraction, name) for every function of one file."""
    tree = ast.parse(pathlib.Path(path).read_text(encoding="utf-8"))
    ran, missed = set(measured["executed_lines"]), set(measured["missing_lines"])
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        span = set(range(node.lineno, node.end_lineno + 1))
        statements = len(span & ran) + len(span & missed)
        if not statements:
            continue
        covered = len(span & ran) / statements
        cc = complexity(node)
        out.append((cc * cc * (1 - covered) ** 3 + cc, cc, covered, node.name))
    return sorted(out, reverse=True)


def main():
    files = report().get("files", {})
    if not files:
        sys.stderr.write("crap: the data file measured nothing; nothing to judge is not OK\n")
        return 2
    blocks, functions, top = 0, 0, (0.0, "")
    for path in sorted(files):
        percent = files[path]["summary"]["percent_covered"]
        if percent < COVERAGE:
            blocks += 1
            print(
                "BLOCK\t%s\t\tcoverage is %.1f percent of statements and branches, and the "
                "floor is %g\t[COVERAGE]" % (path, percent, COVERAGE)
            )
        for crap, cc, covered, name in scores(path, files[path]):
            functions += 1
            top = max(top, (crap, name))
            if crap > CRAP:
                blocks += 1
                print(
                    "BLOCK\t%s\t%s\tCRAP %.1f: complexity %d at %.0f percent coverage, and "
                    "the cap is %g\t[CRAP]" % (path, name, crap, cc, covered * 100, CRAP)
                )
    if blocks:
        print("crap: %d block%s - BLOCKED" % (blocks, "" if blocks == 1 else "s"))
        return 1
    print(
        "crap: OK (%d functions in %d file%s, the highest CRAP is %.1f in %s)"
        % (functions, len(files), "" if len(files) == 1 else "s", top[0], top[1])
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
