#!/usr/bin/env python3
"""Mutation testing of the tool, with the stdlib: every mutant of the package is killed.

A mutant is the original source with one thing changed the way a bug changes
it: a comparison flipped (< to <=, == to !=, in to not in), an and made an or,
a not removed, an integer moved by one or 0 and 1 swapped, a True made False,
a rule that blocks made to only inform (block( to info(), a rule deleted (its
body replaced by return []), and the sorted() in report() removed. The suite
runs against each; a mutant the suite does not fail on has survived, and a
survivor is a test the suite should have had.

Printed strings are not mutated: a message is wording, not a verdict, and a
score that counts wording measures the wrong thing. sorted() is mutated in
report() only, because every finding is sorted there and the sorts inside the
rules are defence in depth the suite cannot see.

The threshold is zero survivors. tools/tests/equivalent_mutants.txt lists the
mutants a human has read and found equivalent - a change that alters no verdict
- one per line, its id then a reason of at least four words. A line for a mutant
that no longer exists, or that the suite now kills, fails the run, so the list
cannot go stale in silence. A mutant's id is its operator, the function it is
in and its ordinal there (cmp/check_pk_test/2), so a line moving does not
rename it.

How a mutant is run. The working tree is copied (git, .local and caches left
out) and the mutant is spliced into the copy's module by source span, so the
real files are never touched and comments and quotes elsewhere stay byte for
byte. First the fixture-driven test file of the mutated rule's command runs
(test_check.py for a check_ rule, and so on); a mutant it kills is killed.
Every survivor of that pass is re-run under the whole suite, so the verdict
never depends on the shortcut. A run past the timeout counts as killed and is
printed, because a mutant that loops is not one that passed.

    python tools/tests/mutants.py               every mutant, one worker
    python tools/tests/mutants.py --jobs 4      four copies, four workers
    python tools/tests/mutants.py --list        the ids, and nothing runs
    python tools/tests/mutants.py --only check_pk_test --sample 20

Exit 0 when every mutant is killed or listed, 1 when one survived or the list
is stale, 2 when the suite is red before any mutant or nothing can run.
"""

import argparse
import ast
import concurrent.futures
import io
import os
import pathlib
import queue
import shutil
import subprocess
import sys
import tempfile
import time
import tokenize

TOOLS = pathlib.Path(__file__).resolve().parents[1]
ROOT = TOOLS.parent
PACKAGE = TOOLS / "spec_lock_diff"
# Every module of the package, never the shim: its three lines are the subprocess tests'.
TARGETS = sorted(p.relative_to(ROOT).as_posix() for p in PACKAGE.rglob("*.py"))
TESTS = "tools/tests"
EQUIVALENTS = TOOLS / "tests" / "equivalent_mutants.txt"
IGNORED = shutil.ignore_patterns(
    ".git",
    ".local",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    ".coverage",
    ".coverage.*",
    "build",
    "dist",
    "*.egg-info",
)
FLIP = {
    ast.Lt: ast.LtE,
    ast.LtE: ast.Lt,
    ast.Gt: ast.GtE,
    ast.GtE: ast.Gt,
    ast.Eq: ast.NotEq,
    ast.NotEq: ast.Eq,
    ast.In: ast.NotIn,
    ast.NotIn: ast.In,
}
SYMBOL = {
    ast.Lt: "<",
    ast.LtE: "<=",
    ast.Gt: ">",
    ast.GtE: ">=",
    ast.Eq: "==",
    ast.NotEq: "!=",
    ast.In: "in",
    ast.NotIn: "not in",
}
# The fixture-driven test file of each command, by the prefix of its rules.
SELECTION = (
    ("check_", "test_check.py"),
    ("gate_", "test_gate.py"),
    ("compare_", "test_compare.py"),
    ("cmd_", "test_cli.py"),
)


class Mutant:
    """One change to the source: where, what, the mutated text, and later the verdict."""

    def __init__(self, file, op, function, line, what, text):
        self.file, self.op, self.function, self.line = file, op, function, line
        self.what, self.text = what, text
        self.id, self.verdict, self.seconds = "", "", 0.0


def _pos(node):
    return (node.lineno, node.col_offset, node.end_lineno, node.end_col_offset)


def rule_names():
    """The functions registered as rules, read from the tool itself."""
    sys.path.insert(0, str(TOOLS))
    import spec_lock_diff as slp

    return set(
        f.__name__
        for f in slp.CHECK_RULES + slp.GATE_RULES + slp.COMPARE_RULES + slp.COMPARE_RUN_RULES
    )


def enclosing(tree, line):
    """The innermost function holding a line, or <module>."""
    best = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.lineno <= line <= node.end_lineno:
            if best is None or node.end_lineno - node.lineno < best.end_lineno - best.lineno:
                best = node
    return best.name if best else "<module>"


def _constant_sites(node):
    """A bool flips; an int moves by one, and 0 and 1 also swap."""
    if isinstance(node.value, bool):
        return [("true", "Constant", _pos(node), 0)]
    if isinstance(node.value, int):
        found = [("int", "Constant", _pos(node), "plus1")]
        if node.value in (0, 1):
            found.append(("int", "Constant", _pos(node), "swap01"))
        return found
    return []


def _call_sites(node, tree):
    """block( becomes info(; the sorted() of report() goes."""
    if not isinstance(node.func, ast.Name):
        return []
    if node.func.id == "block":
        return [("block", "Call", _pos(node), 0)]
    if node.func.id == "sorted" and node.args and enclosing(tree, node.lineno) == "report":
        return [("sorted", "Call", _pos(node), 0)]
    return []


def _sites_of(node, tree, rules):
    """The sites one node offers: (op, node kind, position, extra), or none."""
    if isinstance(node, ast.Compare):
        return [
            ("cmp", "Compare", _pos(node), i) for i, op in enumerate(node.ops) if type(op) in FLIP
        ]
    if isinstance(node, ast.BoolOp):
        return [("bool", "BoolOp", _pos(node), 0)]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return [("not", "UnaryOp", _pos(node), 0)]
    if isinstance(node, ast.Constant):
        return _constant_sites(node)
    if isinstance(node, ast.Call):
        return _call_sites(node, tree)
    if isinstance(node, ast.FunctionDef) and node.name in rules:
        return [("rule", "FunctionDef", _pos(node), node.name)]
    return []


def sites(tree, rules):
    """Every place one operator applies, in source order."""
    found = [site for node in ast.walk(tree) for site in _sites_of(node, tree, rules)]
    return sorted(found, key=lambda s: (s[2][0], s[2][1], s[0], str(s[3])))


class Apply(ast.NodeTransformer):
    """Apply one site's operator to a fresh tree, and say in words what changed."""

    def __init__(self, site):
        self.op, self.kind, self.pos, self.extra = site
        self.hits, self.result, self.what = 0, None, ""

    def visit(self, node):
        if (
            type(node).__name__ == self.kind
            and hasattr(node, "lineno")
            and _pos(node) == self.pos
            and (self.kind != "FunctionDef" or node.name == self.extra)
        ):
            self.hits += 1
            self.result = self.mutate(node)
            return self.result
        return self.generic_visit(node)

    def mutate(self, node):
        if self.op == "cmp":
            was = type(node.ops[self.extra])
            node.ops[self.extra] = FLIP[was]()
            self.what = "%s -> %s" % (SYMBOL[was], SYMBOL[FLIP[was]])
            return node
        if self.op == "bool":
            self.what = "and -> or" if isinstance(node.op, ast.And) else "or -> and"
            node.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
            return node
        if self.op == "not":
            self.what = "not removed"
            return node.operand
        if self.op == "true":
            self.what = "%s -> %s" % (node.value, not node.value)
            node.value = not node.value
            return node
        if self.op == "int":
            new = 1 - node.value if self.extra == "swap01" else node.value + 1
            self.what = "%s -> %s" % (node.value, new)
            node.value = new
            return node
        if self.op == "block":
            self.what = "block( -> info("
            node.func.id = "info"
            return node
        if self.op == "sorted":
            self.what = "sorted() removed"
            return node.args[0]
        doc = node.body[0] if isinstance(node.body[0], ast.Expr) else None
        node.body = ([doc] if doc else []) + [ast.Return(value=ast.List(elts=[], ctx=ast.Load()))]
        self.what = "body -> return []"
        return node


def requote(snippet):
    """ast.unparse writes single quotes; the tool and two meta-tests use double ones."""
    tokens = list(tokenize.generate_tokens(io.StringIO(snippet).readline))
    starts = [0]
    for line in snippet.split("\n"):
        starts.append(starts[-1] + len(line) + 1)
    out = snippet
    for token in reversed(tokens):
        text = token.string
        if (
            token.type == tokenize.STRING
            and text.startswith("'")
            and not text.startswith("'''")
            and '"' not in text
            and "\\" not in text
        ):
            a = starts[token.start[0] - 1] + token.start[1]
            b = starts[token.end[0] - 1] + token.end[1]
            out = out[:a] + '"' + text[1:-1] + '"' + out[b:]
    return out


def splice(source, position, rendered):
    """The source with one node's span (byte offsets, as ast gives them) replaced."""
    raw = source.encode("utf-8")
    starts = [0]
    for line in raw.split(b"\n"):
        starts.append(starts[-1] + len(line) + 1)
    a = starts[position[0] - 1] + position[1]
    b = starts[position[2] - 1] + position[3]
    return (raw[:a] + rendered.encode("utf-8") + raw[b:]).decode("utf-8")


def mutants(file, source, rules):
    """Every mutant of one module, each compiling and each different from it, with stable ids."""
    tree, out, ordinal, seen = ast.parse(source), [], {}, set()
    for site in sites(tree, rules):
        apply = Apply(site)
        apply.visit(ast.parse(source))
        if apply.hits != 1:
            raise SystemExit("mutants: site %r matched %d nodes" % (site, apply.hits))
        rendered = requote(ast.unparse(apply.result))
        if site[0] in ("not", "sorted"):
            rendered = "(" + rendered + ")"
        text = splice(source, site[2], rendered)
        if text == source or text in seen:  # 0 plus one and 0 swapped are one mutant
            continue
        seen.add(text)
        try:
            compile(text, file, "exec")
        except SyntaxError:
            continue
        mutant = Mutant(file, site[0], enclosing(tree, site[2][0]), site[2][0], apply.what, text)
        key = (mutant.op, mutant.function)
        ordinal[key] = ordinal.get(key, 0) + 1
        mutant.id = "%s/%s/%d" % (mutant.op, mutant.function, ordinal[key])
        out.append(mutant)
    return out


def equivalents():
    """The listed mutants: id -> reason. A reason under four words is a block of its own."""
    listed, short = {}, []
    if not EQUIVALENTS.is_file():
        return listed, short
    for line in EQUIVALENTS.read_text(encoding="utf-8").splitlines():
        words = line.split()
        if not words or words[0].startswith("#"):
            continue
        listed[words[0]] = " ".join(words[1:])
        if len(words) < 5:
            short.append(words[0])
    return listed, short


def selection(function):
    """The test file to run first for a mutant in this function, or None for the whole suite."""
    for prefix, name in SELECTION:
        if function.startswith(prefix):
            return TESTS + "/" + name
    return None


def run(copy, paths, timeout):
    """One pytest run in one copy. Returns killed, survived or timeout, and the seconds."""
    started = time.time()
    try:
        done = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider"] + paths,
            cwd=str(copy),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=dict(os.environ, PYTHONHASHSEED="0"),
        )
        verdict = "survived" if done.returncode == 0 else "killed"
    except subprocess.TimeoutExpired:
        verdict = "timeout"
    return verdict, time.time() - started


def judge(copy, originals, mutant, timeout):
    """Splice the mutant into the copy, run the first pass and, if it survived, the whole suite."""
    target = copy / mutant.file
    target.write_text(mutant.text, encoding="utf-8")
    try:
        first = selection(mutant.function)
        verdict, seconds = run(copy, [first] if first else [TESTS], timeout)
        if first and verdict == "survived":
            verdict, more = run(copy, [TESTS], timeout)
            seconds += more
    finally:
        target.write_text(originals[mutant.file], encoding="utf-8")
    mutant.verdict, mutant.seconds = verdict, seconds
    return mutant


def campaign(chosen, jobs, log):
    """Run every chosen mutant on `jobs` copies of the working tree, and print each verdict."""
    with tempfile.TemporaryDirectory() as folder:
        copies = queue.Queue()
        for n in range(jobs):
            copy = pathlib.Path(folder) / ("copy%d" % n)
            shutil.copytree(str(ROOT), str(copy), ignore=IGNORED)
            copies.put(copy)
        originals = {file: (ROOT / file).read_text(encoding="utf-8") for file in TARGETS}
        verdict, baseline = run(copies.queue[0], [TESTS], 600)
        if verdict != "survived":
            raise SystemExit(
                "mutants: the suite is %s on the unmutated tool; fix that first"
                % ("red" if verdict == "killed" else "timing out")
            )
        timeout = max(60, 5 * baseline)
        log(
            "mutants: the suite is green in %.0fs; %d mutants, %d worker%s, timeout %.0fs"
            % (baseline, len(chosen), jobs, "" if jobs == 1 else "s", timeout)
        )

        def work(mutant):
            copy = copies.get()
            try:
                return judge(copy, originals, mutant, timeout)
            finally:
                copies.put(copy)

        with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
            for number, done in enumerate(pool.map(work, chosen), start=1):
                log(
                    "%4d/%d %-40s %-9s %5.1fs  %s"
                    % (number, len(chosen), done.id, done.verdict, done.seconds, done.what)
                )


def _judged(mutant, listed):
    """What one mutant counts as - killed, equivalent or timeout - and the line to print, if any."""
    where = (mutant.file, mutant.function)
    if mutant.verdict == "timeout":
        return "timeout", ("INFO",) + where + (
            "%s timed out, which counts as killed: %s at line %d"
            % (mutant.id, mutant.what, mutant.line),
            "MUTANT",
        )
    if mutant.verdict == "killed" and mutant.id in listed:
        return "killed", ("BLOCK",) + where + (
            "%s is listed as equivalent and the suite kills it now; remove the line" % mutant.id,
            "MUTANT",
        )
    if mutant.verdict == "killed":
        return "killed", None
    if mutant.id in listed:
        return "equivalent", ("INFO",) + where + (
            "%s survived and is listed as equivalent: %s" % (mutant.id, listed[mutant.id]),
            "MUTANT",
        )
    return "survived", ("BLOCK",) + where + (
        "%s survived: %s at line %d, and no test tells the two apart"
        % (mutant.id, mutant.what, mutant.line),
        "MUTANT",
    )


def report(chosen, listed, short):
    """The findings in the house format, the summary line, and the exit code."""
    findings, counts = [], {"killed": 0, "equivalent": 0, "timeout": 0, "survived": 0}
    ids = set(m.id for m in chosen)
    for mutant in chosen:
        kind, finding = _judged(mutant, listed)
        counts[kind] += 1
        if finding:
            findings.append(finding)
    for name in sorted(short):
        findings.append(
            (
                "BLOCK",
                str(EQUIVALENTS.relative_to(ROOT)),
                "",
                "%s needs a reason of at least four words" % name,
                "MUTANT",
            )
        )
    for name in sorted(set(listed) - ids):
        if not any(m.id == name for m in chosen):
            findings.append(
                (
                    "BLOCK",
                    str(EQUIVALENTS.relative_to(ROOT)),
                    "",
                    "%s is listed and no such mutant exists; remove the line" % name,
                    "MUTANT",
                )
            )
    for finding in sorted(findings, key=lambda f: (f[1], f[2], f[0] != "BLOCK", f[3])):
        print("\t".join(finding[:4] + ("[%s]" % finding[4],)))
    blocks = sum(1 for f in findings if f[0] == "BLOCK")
    if blocks:
        print("mutants: %d block%s - BLOCKED" % (blocks, "" if blocks == 1 else "s"))
        return 1
    print(
        "mutants: OK (%d killed, %d equivalent, %d timed out)"
        % (counts["killed"], counts["equivalent"], counts["timeout"])
    )
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="mutants", description=__doc__.splitlines()[0])
    parser.add_argument("--jobs", type=int, default=1, help="copies of the tree run in parallel")
    parser.add_argument("--only", metavar="FUNCTION", help="mutants of one function")
    parser.add_argument("--sample", type=int, metavar="N", help="an evenly spaced subset")
    parser.add_argument("--list", action="store_true", help="print the ids and run nothing")
    args = parser.parse_args(argv)
    rules = rule_names()
    chosen = [
        m
        for file in TARGETS
        for m in mutants(file, (ROOT / file).read_text(encoding="utf-8"), rules)
        if not args.only or m.function == args.only
    ]
    if args.sample and args.sample < len(chosen):
        step = (len(chosen) - 1) / (args.sample - 1) if args.sample > 1 else 1
        chosen = [chosen[round(i * step)] for i in range(args.sample)]
    if not chosen:
        sys.stderr.write("mutants: nothing to mutate; nothing to judge is not OK\n")
        return 2
    if args.list:
        for mutant in chosen:
            print("%-40s %-34s line %-5d %s" % (mutant.id, mutant.file, mutant.line, mutant.what))
        print("%d mutants" % len(chosen))
        return 0
    listed, short = equivalents()
    if not args.only and not args.sample:
        listed_all = listed
    else:  # a partial run cannot say a listed mutant is stale
        listed_all = {k: v for k, v in listed.items() if any(m.id == k for m in chosen)}
    campaign(chosen, max(1, args.jobs), lambda line: print(line, flush=True))
    return report(chosen, listed_all, short)


if __name__ == "__main__":
    sys.exit(main())
