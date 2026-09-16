#!/usr/bin/env python3
"""The mutation check of Stage D: every mutant of a changed model is killed by its unit tests.

Copy to .github/mutate_model.py - a protected path, so only a human changes
what mutates the code - and run it from the Stage D job after the sample
build, with the branch the pull request targets and the production artifacts:

    python .github/mutate_model.py --base <sha> --defer-state ./prod-artifacts

For every marts model whose sql changed since the base, the sql is mutated in
a fixed list of ways. Each mutant is written as a temporary model under
<marts>/__mutants__/ with the model's unit tests cloned onto it, and ONE
`dbt test` invocation runs them all, so the cost is one dbt start-up per pull
request rather than one per mutant. A mutant a unit test fails on is killed.
One that every unit test passes has survived, and a survivor blocks, unless
the base branch's tests/mutation_equivalents.yml lists it. A changed model
with no unit test blocks: it has nothing that could tell it from a wrong one.

The operators, tried on every site of the sql, in this order at one site:

    cmp        a comparison flipped: = to !=, != and <> to =, < to <=,
               <= to <, > to >=, >= to >
    where      one predicate of a where clause replaced by true
    agg        sum( to max(, min( to max(, max( to min(, avg( to max(,
               count(distinct to count(
    join       left join to inner join, inner join to left join
    coalesce   coalesce(a, b) to a
    distinct   select distinct to select
    literal    a number moved by one, a string given one more character
    not        a not removed: is not null to is null, not in to in

Comments, jinja blocks and string literals are left alone by every operator
but literal, so a != inside a comment is not a site. Nothing here reads a
table: the unit tests run on their given rows, and check rule T3 has already
refused a unit test that leaves an input unmocked.

The artifact, one file per model under mutation/, is what
schemas/mutation.schema.json describes. An equivalence entry names a mutant
by model, operator, original text and occurrence, never by line:

    - model: fct_orders
      operator: cmp
      original: "<>"
      occurrence: 1
      reason: "<> and != are one operator in every dialect"

`--dry-run` lists the mutants of each changed model and runs nothing. Exit 0
when every mutant is killed or listed, 1 when one survived or a changed model
has no unit test, 2 when git or dbt cannot be run.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import shutil
import subprocess
import sys
from typing import Any

import yaml

MARTS = ("models/marts",)
MUTANTS_DIR = "__mutants__"
TAG = "slp_mutant"
EQUIVALENTS = "tests/mutation_equivalents.yml"
CMP = {"!=": "=", "<>": "=", "<=": "<", ">=": ">", "<": "<=", ">": ">=", "=": "!="}
AGG = {"sum(": "max(", "min(": "max(", "max(": "min(", "avg(": "max("}
NOT = {"is not null": "is null", "not in": "in", "not exists": "exists", "not like": "like"}
CLAUSE_END = re.compile(
    r"\b(group\s+by|order\s+by|having|qualify|window|limit|union|intersect|except)\b|;", re.I
)


class Mutant:
    """One change to a model's sql: where, what, and later the verdict."""

    def __init__(self, op: str, start: int, end: int, replacement: str, sql: str) -> None:
        self.op, self.start, self.end, self.replacement = op, start, end, replacement
        self.original = sql[start:end]
        self.line = sql.count("\n", 0, start) + 1
        self.id, self.occurrence, self.name = "", 0, ""
        self.verdict, self.reason = "", ""

    def text(self, sql: str) -> str:
        """The model's sql with this one change made."""
        return sql[: self.start] + self.replacement + sql[self.end :]

    def key(self, model: str) -> tuple[str, str, str, int]:
        """What an equivalence entry names: model, operator, original text, occurrence."""
        return (model, self.op, self.original, self.occurrence)


# --- finding the sites ---


def _blank(text: str, pattern: str) -> str:
    """The text with every match replaced by spaces, newlines kept, so offsets stay true."""
    return re.sub(pattern, lambda m: re.sub(r"[^\n]", " ", m.group(0)), text, flags=re.S)


def masked(sql: str, strings: bool = True) -> str:
    """The sql with comments and jinja blanked, and the string literals too unless asked not to."""
    out = _blank(sql, r"\{#.*?#\}|\{\{.*?\}\}|\{%.*?%\}|/\*.*?\*/|--[^\n]*")
    return _blank(out, r"'(?:[^'\\]|\\.)*'") if strings else out


def _spans(text: str, pattern: str) -> list[tuple[int, int, str]]:
    return [(m.start(), m.end(), m.group(0)) for m in re.finditer(pattern, text, re.I)]


def _depth_end(text: str, start: int, stop: Any) -> int:
    """The offset where a clause starting at `start` ends: a closing paren of the level above,
    or a match of `stop` at the clause's own depth, or the end of the text."""
    depth = 0
    for at in range(start, len(text)):
        char = text[at]
        if char == "(":
            depth += 1
        elif char == ")":
            if depth == 0:
                return at
            depth -= 1
        elif depth == 0 and stop.match(text, at):
            return at
    return len(text)


def _predicates(m: str, sql: str, start: int, end: int) -> list[tuple[int, int]]:
    """The spans of the predicates joined by and/or at the top level of one clause.

    The cuts are found on the fully masked text; the trimming reads the text
    with only comments and jinja blanked, so a string literal at either end of
    a predicate stays inside it and a comment after it stays out.
    """
    cuts, depth = [start], 0
    for t in re.finditer(r"\(|\)|\b(?:and|or)\b", m[start:end], re.I):
        token = t.group(0)
        if token == "(":
            depth += 1
        elif token == ")":
            depth -= 1
        elif depth == 0:
            cuts += [start + t.start(), start + t.end()]
    cuts.append(end)
    spans = []
    for a, b in zip(cuts[0::2], cuts[1::2], strict=True):  # start, pairs of cuts, end
        piece = sql[a:b]
        left, right = len(piece) - len(piece.lstrip()), len(piece) - len(piece.rstrip())
        if piece.strip():
            spans.append((a + left, b - right))
    return spans


def _where_sites(m: str, sql: str) -> list[tuple[str, int, int, str]]:
    """Each predicate of each where clause, replaced by true."""
    found = []
    for w in re.finditer(r"\bwhere\b", m, re.I):
        end = _depth_end(m, w.end(), CLAUSE_END)
        found += [("where", a, b, "true") for a, b in _predicates(m, sql, w.end(), end)]
    return found


def _coalesce_sites(m: str, sql: str) -> list[tuple[str, int, int, str]]:
    """Each coalesce(a, b, ...) replaced by its first argument, read with the strings visible."""
    found = []
    for c in re.finditer(r"\bcoalesce\s*\(", m, re.I):
        close = _depth_end(m, c.end(), re.compile(r"(?!)"))
        comma = _depth_end(m, c.end(), re.compile(","))
        first = sql[c.end() : comma].strip()
        if comma < close and first:
            found.append(("coalesce", c.start(), close + 1, first))
    return found


def _bumped(number: str) -> str:
    return str(float(number) + 1) if "." in number else str(int(number) + 1)


def sites(sql: str) -> list[Mutant]:
    """Every mutant of one model's sql, in source order, with ids and occurrences."""
    m, lit = masked(sql), masked(sql, strings=False)
    found: list[tuple[str, int, int, str]] = []
    found += [("cmp", a, b, CMP[t]) for a, b, t in _spans(m, r"!=|<>|<=|>=|<|>|=")]
    found += _where_sites(m, lit)
    found += [
        ("agg", a, b, AGG[t.lower().replace(" ", "")])
        for a, b, t in _spans(m, r"\b(?:sum|min|max|avg)\s*\(")
    ]
    found += [("agg", a, b, "count(") for a, b, _ in _spans(m, r"\bcount\s*\(\s*distinct\b")]
    found += [
        ("join", a, b, "inner join") for a, b, _ in _spans(m, r"\bleft\s+(?:outer\s+)?join\b")
    ]
    found += [("join", a, b, "left join") for a, b, _ in _spans(m, r"\binner\s+join\b")]
    found += _coalesce_sites(m, lit)
    found += [("distinct", a, b, "select") for a, b, _ in _spans(m, r"\bselect\s+distinct\b")]
    found += [
        ("literal", a, b, _bumped(t)) for a, b, t in _spans(m, r"(?<![\w.])\d+(?:\.\d+)?(?![\w.])")
    ]
    found += [("literal", a, b, "'%s_'" % t[1:-1]) for a, b, t in _spans(lit, r"'(?:[^'\\]|\\.)*'")]
    found += [
        ("not", a, b, NOT[re.sub(r"\s+", " ", t.lower())])
        for a, b, t in _spans(
            m, r"\bis\s+not\s+null\b|\bnot\s+in\b|\bnot\s+exists\b|\bnot\s+like\b"
        )
    ]
    ordinal: dict[str, int] = {}
    occurrence: dict[tuple[str, str], int] = {}
    out = []
    for op, a, b, replacement in sorted(found, key=lambda s: (s[1], s[0], s[2])):
        mutant = Mutant(op, a, b, replacement, sql)
        ordinal[op] = ordinal.get(op, 0) + 1
        occurrence[(op, mutant.original)] = occurrence.get((op, mutant.original), 0) + 1
        mutant.id = "%s/%d" % (op, ordinal[op])
        mutant.occurrence = occurrence[(op, mutant.original)]
        out.append(mutant)
    return out


# --- the project ---


def git(root: pathlib.Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(root)] + list(args), capture_output=True, text=True)
    if done.returncode != 0:
        raise SystemExit("mutate: git %s: %s" % (" ".join(args), " ".join(done.stderr.split())))
    return done.stdout


def changed_models(root: pathlib.Path, base: str, marts: list[str]) -> dict[str, pathlib.Path]:
    """The marts models whose sql changed since the base, by name."""
    listed = git(root, "diff", "--name-only", base, "HEAD", "--", *marts)
    return {
        pathlib.Path(p).stem: root / p
        for p in sorted(listed.split())
        if p.endswith(".sql") and (root / p).is_file()
    }


def unit_tests_of(root: pathlib.Path, model: str) -> list[dict[str, Any]]:
    """The unit tests declared for one model, wherever under models/ the yml keeps them."""
    found = []
    for path in sorted(p for p in (root / "models").rglob("*.yml") if MUTANTS_DIR not in p.parts):
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for unit in doc.get("unit_tests") or []:
            if isinstance(unit, dict) and unit.get("model") == model:
                found.append(unit)
    return found


def equivalents(root: pathlib.Path, base: str) -> dict[tuple[str, str, str, int], str]:
    """The base branch's equivalence list, keyed as a mutant is: model, op, text, occurrence."""
    done = subprocess.run(
        ["git", "-C", str(root), "show", "%s:%s" % (base, EQUIVALENTS)],
        capture_output=True,
        text=True,
    )
    if done.returncode != 0:  # no such file on the base branch: nothing is equivalent
        return {}
    listed = {}
    for entry in yaml.safe_load(done.stdout) or []:
        key = (entry["model"], entry["operator"], str(entry["original"]), int(entry["occurrence"]))
        listed[key] = str(entry.get("reason", ""))
    return listed


# --- the batch, one dbt invocation ---


def layout(
    model: str, sql: str, units: list[dict[str, Any]], mutants: list[Mutant], marts: str
) -> dict[str, str]:
    """The temporary files: one model per mutant, and one yml with the unit tests cloned on."""
    files, cloned = {}, []
    for mutant in mutants:
        mutant.name = "%s__%s" % (model, mutant.id.replace("/", "_"))
        files["%s/%s/%s.sql" % (marts, MUTANTS_DIR, mutant.name)] = mutant.text(sql)
        for unit in units:
            copy = json.loads(json.dumps(unit, default=str))
            copy["name"] = "%s__%s" % (unit["name"], mutant.name)
            copy["model"] = mutant.name
            config = copy.setdefault("config", {})
            tags = config.get("tags") or []
            config["tags"] = ([tags] if isinstance(tags, str) else list(tags)) + [TAG]
            cloned.append(copy)
    files["%s/%s/schema.yml" % (marts, MUTANTS_DIR)] = yaml.safe_dump(
        {"version": 2, "unit_tests": cloned}, sort_keys=False
    )
    return files


def verdicts(results: dict[str, Any], mutants: list[Mutant]) -> None:
    """Killed when any unit test on the mutant's model failed or errored; survived otherwise."""
    failed = set()
    for result in results.get("results", []):
        parts = str(result.get("unique_id", "")).split(".")
        if (
            len(parts) >= 4
            and parts[0] == "unit_test"
            and result.get("status") in ("fail", "error")
        ):
            failed.add(parts[2])
    for mutant in mutants:
        mutant.verdict = "killed" if mutant.name in failed else "survived"


def run_dbt(root: pathlib.Path, state: str | None) -> dict[str, Any]:
    """One `dbt test` over every cloned unit test, and the run_results.json it wrote."""
    command = ["dbt", "test", "--select", "tag:" + TAG]
    if state:
        command += ["--defer", "--state", state]
    try:
        subprocess.run(command, cwd=str(root), capture_output=True, text=True)
    except OSError as exc:
        raise SystemExit("mutate: cannot run dbt: %s" % exc) from exc
    results = root / "target" / "run_results.json"
    if not results.is_file():
        raise SystemExit("mutate: dbt wrote no target/run_results.json; nothing was judged")
    return dict(json.loads(results.read_text(encoding="utf-8")))


# --- the check ---


def judge(
    root: pathlib.Path,
    models: dict[str, pathlib.Path],
    marts: str,
    state: str | None,
    listed: dict[tuple[str, str, str, int], str],
) -> tuple[list[tuple[str, ...]], dict[str, list[Mutant]]]:
    """Mutate every changed model, run the batch once, and say what survived."""
    findings: list[tuple[str, ...]] = []
    per_model: dict[str, list[Mutant]] = {}
    written: dict[str, str] = {}
    for model, path in sorted(models.items()):
        units = unit_tests_of(root, model)
        if not units:
            findings.append(
                (
                    "BLOCK",
                    str(path.relative_to(root)),
                    model,
                    "the sql changed and the model has no unit test; nothing can tell it "
                    "from a wrong one (README §3 Stage D)",
                    "MUTANT",
                )
            )
            continue
        sql = path.read_text(encoding="utf-8")
        per_model[model] = sites(sql)
        written.update(layout(model, sql, units, per_model[model], marts))
    if not per_model:
        return findings, per_model
    for rel, text in written.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    try:
        results = run_dbt(root, state)
    finally:
        shutil.rmtree(root / marts / MUTANTS_DIR, ignore_errors=True)
    for model, mutants in per_model.items():
        verdicts(results, mutants)
        for mutant in mutants:
            if mutant.verdict == "survived" and mutant.key(model) in listed:
                mutant.verdict, mutant.reason = "equivalent", listed[mutant.key(model)]
        findings += _findings(model, str(models[model].relative_to(root)), mutants)
    return findings, per_model


def _findings(model: str, file: str, mutants: list[Mutant]) -> list[tuple[str, ...]]:
    out: list[tuple[str, ...]] = []
    for mutant in mutants:
        what = "%s: %s -> %s at line %d" % (
            mutant.id,
            mutant.original,
            mutant.replacement,
            mutant.line,
        )
        if mutant.verdict == "survived":
            out.append(
                (
                    "BLOCK",
                    file,
                    model,
                    "mutant %s survived every unit test; a unit test "
                    "that cannot tell the code from this is a unit test the model does not "
                    "have yet" % what,
                    "MUTANT",
                )
            )
        elif mutant.verdict == "equivalent":
            out.append(
                (
                    "INFO",
                    file,
                    model,
                    "mutant %s survived and is listed as equivalent: %s" % (what, mutant.reason),
                    "MUTANT",
                )
            )
    return out


def artifact(out: pathlib.Path, model: str, mutants: list[Mutant]) -> None:
    """mutation/<model>.json, in the shape of schemas/mutation.schema.json."""
    entries = []
    for mutant in mutants:
        entry: dict[str, Any] = {
            "id": mutant.id,
            "operator": mutant.op,
            "original": mutant.original,
            "replacement": mutant.replacement,
            "line": mutant.line,
            "occurrence": mutant.occurrence,
            "verdict": mutant.verdict,
        }
        if mutant.reason:
            entry["reason"] = mutant.reason
        entries.append(entry)
    counts = {
        v: sum(1 for m in mutants if m.verdict == v) for v in ("killed", "survived", "equivalent")
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / ("%s.json" % model)).write_text(
        json.dumps(dict({"model": model, "mutants": entries}, **counts), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mutate_model", description=__doc__.splitlines()[0])
    parser.add_argument("--base", required=True, help="git ref the pull request targets")
    parser.add_argument("--project-dir", default=".", help="root of the dbt project")
    parser.add_argument(
        "--marts-path",
        action="append",
        metavar="PATH",
        help="directory the framework makes mandatory; repeat for more than one",
    )
    parser.add_argument(
        "--defer-state", metavar="DIR", help="production artifacts for --defer --state"
    )
    parser.add_argument("--out", default="mutation", help="where the artifacts go")
    parser.add_argument("--dry-run", action="store_true", help="list the mutants and run nothing")
    args = parser.parse_args(argv)
    root = pathlib.Path(args.project_dir).resolve()
    marts = [p.strip("/") for p in (args.marts_path or list(MARTS))]
    models = changed_models(root, args.base, marts)
    if args.dry_run:
        for model, path in sorted(models.items()):
            for mutant in sites(path.read_text(encoding="utf-8")):
                print(
                    "%s\t%-14s line %-4d %s -> %s"
                    % (model, mutant.id, mutant.line, mutant.original, mutant.replacement)
                )
        print(
            "mutate: %d changed model%s listed, nothing run"
            % (len(models), "" if len(models) == 1 else "s")
        )
        return 0
    findings, per_model = judge(
        root, models, marts[0], args.defer_state, equivalents(root, args.base)
    )
    for model, mutants in per_model.items():
        artifact(root / args.out, model, mutants)
    for finding in sorted(findings, key=lambda f: (f[1], f[2], f[0] != "BLOCK", f[3])):
        print("\t".join(finding[:4] + ("[%s]" % finding[4],)))
    blocks = sum(1 for f in findings if f[0] == "BLOCK")
    killed = sum(1 for ms in per_model.values() for m in ms if m.verdict == "killed")
    equal = sum(1 for ms in per_model.values() for m in ms if m.verdict == "equivalent")
    if blocks:
        print("mutate: %d block%s - BLOCKED" % (blocks, "" if blocks == 1 else "s"))
        return 1
    print(
        "mutate: OK (%d killed, %d equivalent, in %d model%s)"
        % (killed, equal, len(per_model), "" if len(per_model) == 1 else "s")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
