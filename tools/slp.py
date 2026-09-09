#!/usr/bin/env python3
"""slp - the deterministic gates of Spec-Lock-Diff. One file, no network, no model.

    check    every model in models/marts/ has a complete spec, a valid
             pre-registration when it has one, and a uniqueness test on its PK
    gate     nothing on this branch weakened a test, a unit test, a
             reconciliation, a package pin or a spec
    compare  every number in a diff.json is inside the interval the
             pre-registration declared before the code was written

Exit codes: 0 nothing to report, 1 at least one BLOCK, 2 the tool could not do
its job. 2 is a failure, never a pass: what cannot be read cannot be approved.
"""

import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import sys
from typing import NamedTuple

import jsonschema
import yaml

__version__ = "0.1.0.dev"
SCHEMA_DIR = pathlib.Path(__file__).resolve().parent / "schemas"

# Keys that say how a test runs rather than what it asserts. They are kept apart
# from the test arguments because gate rules read them (G2 where, G3 severity).
CFG_KEYS = ("enabled", "error_if", "fail_calc", "limit", "severity",
            "store_failures", "warn_if", "where")

# Every rule id these tools can print. The README coverage table has one row per
# id and the fixtures one folder per id; meta-test M2 keeps the three in step.
RULE_IDS = ("S1", "S2", "S3", "P1", "P2", "T1",
            "G1", "G2", "G3", "G4", "G5", "G6", "G7", "I1",
            "C0", "C1", "C2", "C3", "C4", "C5", "C6")


class SlpError(Exception):
    """Anything that stops the tool from judging. Always exit 2, never a pass."""


# --- Findings and output (Section 2 of the tools backlog) ---

class Finding(NamedTuple):
    """One line of output: what is wrong, where it is, and which rule says so."""
    severity: str
    file: str
    model: str
    message: str
    rule_id: str

    def line(self):
        return "\t".join(self[:4] + ("[%s]" % self.rule_id,))

def block(file, model, message, rule_id):
    """A finding that fails the command (exit 1)."""
    return Finding("BLOCK", file, model, message, rule_id)

def info(file, model, message, rule_id):
    """A finding the reviewer should see; it never changes the exit code."""
    return Finding("INFO", file, model, message, rule_id)

def _count(n, word):
    return "" if not n else "%d %s%s" % (n, word, "" if n == 1 else "s")

def report(findings, command, ok_note=""):
    """Print the findings sorted, then one summary line. Returns the exit code."""
    for finding in sorted(findings, key=lambda f: (f.file, f.model, f.rule_id, f)):
        print(finding.line())
    blocks = sum(1 for f in findings if f.severity == "BLOCK")
    counts = [c for c in (_count(blocks, "block"),
                          _count(len(findings) - blocks, "info")) if c]
    if counts:
        print("slp %s: %s - %s" % (command, ", ".join(counts),
                                   "BLOCKED" if blocks else "OK"))
    else:
        print("slp %s: OK%s" % (command, " (%s)" % ok_note if ok_note else ""))
    return 1 if blocks else 0


# --- Reading files, and saying what a schema rejected in plain sentences ---

def parse_yaml(text, where):
    """Parse one YAML document. Unparseable is an error; empty is an empty document."""
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise SlpError("cannot parse %s: %s" % (where, " ".join(str(exc).split())))
    return {} if doc is None else doc

def load_yaml(path):
    """Read and parse one YAML file from disk."""
    try:
        return parse_yaml(pathlib.Path(path).read_text(encoding="utf-8"), path)
    except (OSError, UnicodeDecodeError) as exc:
        raise SlpError("cannot read %s: %s" % (path, exc))

def load_json(path):
    """Read and parse one JSON file from disk."""
    try:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        raise SlpError("cannot read %s: %s" % (path, exc))
    except ValueError as exc:
        raise SlpError("cannot parse %s: %s" % (path, exc))

_VALIDATORS = {}

def validator(name):
    """The validator for schemas/<name>.schema.json, loaded once, checked itself first."""
    if name not in _VALIDATORS:
        schema = load_json(SCHEMA_DIR / ("%s.schema.json" % name))
        jsonschema.Draft202012Validator.check_schema(schema)
        _VALIDATORS[name] = jsonschema.Draft202012Validator(schema)
    return _VALIDATORS[name]

def _why(err):
    """Turn one schema error into a sentence a non-developer can act on."""
    said = err.schema.get("description", "") if isinstance(err.schema, dict) else ""
    if err.validator == "required":
        found = re.search(r"'([^']*)'", err.message)
        field = found.group(1) if found else "?"
        sub = (err.schema.get("properties") or {}).get(field) or {}
        said = sub.get("description") or said
        return "missing required field '%s'%s" % (field, " - " + said if said else "")
    if err.validator == "additionalProperties":
        unknown = sorted(set(re.findall(r"'([^']*)'", err.message)))
        return "unknown field %s" % ", ".join("'%s'" % f for f in unknown)
    if not said:  # a field the schema does not describe: say what the keyword wanted
        said = {"enum": "must be one of: %s", "const": "must be %s"}.get(
            err.validator, "%s") % json.dumps(err.validator_value)
    if isinstance(err.instance, (dict, list)):
        return said
    return "%s (got %s)" % (said, json.dumps(err.instance, ensure_ascii=False))

def schema_errors(obj, name, prefix):
    """Every violation of obj against one schema, as sorted sentences with their path."""
    out = []
    for err in validator(name).iter_errors(obj):
        path = prefix
        for part in err.absolute_path:
            path += "[%d]" % part if isinstance(part, int) else "." + str(part)
        out.append("%s: %s" % (path, _why(err)))
    return sorted(out)


# --- Reading the dbt project ---

# One dbt model as its yml declares it. In tests, the column "" means model level.
Model = NamedTuple("Model", [("name", str), ("file", str), ("entry", dict),
                             ("spec", object), ("prereg", object), ("columns", list),
                             ("sensitive", list), ("tests", list), ("is_marts", bool)])
# One entry of unit_tests:, kept whole because G4 compares the whole body.
UnitTest = NamedTuple("UnitTest", [("name", str), ("model", str), ("file", str),
                                   ("body", dict)])
# Everything the check rules need from a dbt project, read once.
Project = NamedTuple("Project", [("dir", object), ("models", dict), ("unit_tests", list)])

def _entries(value, what, where):
    """A yml list of mappings, or nothing. Anything else cannot be read, so it errors."""
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(v, dict) for v in value):
        raise SlpError("%s in %s must be a list of entries" % (what, where))
    return value

def _one_of(entry, key, where):
    """entry.meta.<key> or entry.config.meta.<key>; both present is ambiguous."""
    meta = entry.get("meta") if isinstance(entry.get("meta"), dict) else {}
    config = entry.get("config") if isinstance(entry.get("config"), dict) else {}
    nested = config.get("meta") if isinstance(config.get("meta"), dict) else {}
    if meta.get(key) is not None and nested.get(key) is not None:
        raise SlpError("ambiguous: %s defined twice (meta and config.meta) in %s"
                       % (key, where))
    return meta.get(key) if meta.get(key) is not None else nested.get(key)

def _test_items(entry, where):
    """The tests: or data_tests: list of a model or column; both keys is ambiguous."""
    classic, modern = entry.get("tests"), entry.get("data_tests")
    if classic is not None and modern is not None:
        raise SlpError("ambiguous: tests defined twice (tests and data_tests) in %s"
                       % where)
    items = classic if classic is not None else modern
    if items is not None and not isinstance(items, list):
        raise SlpError("tests in %s must be a list" % where)
    return items or []

def normalize_test(item, where):
    """One test as (name, arguments, config): what it asserts apart from how it runs."""
    if isinstance(item, str):
        name, body = item, {}
    elif isinstance(item, dict) and len(item) == 1:
        name, body = list(item.items())[0]
        body = {} if body is None else body
    else:
        name, body = None, None
    if not isinstance(name, str) or not isinstance(body, dict):
        raise SlpError("cannot read a test in %s: %r" % (where, item))
    args, cfg = {}, {}
    for key, value in body.items():
        pairs = value.items() if key == "config" and isinstance(value, dict) else [(key, value)]
        for name_, value_ in pairs:
            if name_ in CFG_KEYS:
                cfg[name_] = value_
            else:
                args[("config." if key == "config" else "") + name_] = value_
    return name, json.dumps(args, sort_keys=True, default=str), cfg

def read_doc(doc, rel):
    """The models and unit tests declared in one yml document, on disk or at a commit."""
    if not isinstance(doc, dict):
        raise SlpError("%s is not a yml mapping" % rel)
    models, units = [], []
    for entry in _entries(doc.get("models"), "models", rel):
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            raise SlpError("a model without a name in %s" % rel)
        where = "%s (%s)" % (name, rel)
        columns, sensitive, tests = [], [], []
        for item in _test_items(entry, where):
            tests.append(("",) + normalize_test(item, where))
        for column in _entries(entry.get("columns"), "columns", where):
            cname = column.get("name")
            if not isinstance(cname, str) or not cname:
                raise SlpError("a column without a name in %s" % where)
            columns.append(cname)
            if _one_of(column, "sensitive", "%s.%s" % (where, cname)) is True:
                sensitive.append(cname)
            for item in _test_items(column, "%s.%s" % (where, cname)):
                tests.append((cname,) + normalize_test(item, where))
        models.append(Model(name, rel, entry, _one_of(entry, "spec", where),
                            _one_of(entry, "pre_registration", where), columns,
                            sensitive, tests, rel.startswith("models/marts/")))
    for entry in _entries(doc.get("unit_tests"), "unit_tests", rel):
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            raise SlpError("a unit test without a name in %s" % rel)
        units.append(UnitTest(name, entry.get("model") or "", rel, entry))
    return models, units

def read_project(project_dir):
    """Read models/**.yml into models and unit tests. No git, no dbt, no warehouse."""
    root = pathlib.Path(project_dir).resolve()
    if not (root / "models" / "marts").is_dir():
        raise SlpError("models/marts/ not found under %s; nothing to check is not OK"
                       % project_dir)
    models, units = {}, []
    for path in sorted(p for p in (root / "models").rglob("*")
                       if p.suffix in (".yml", ".yaml") and p.is_file()):
        rel = path.relative_to(root).as_posix()
        found, unit_tests = read_doc(load_yaml(path), rel)
        for model in found:
            if model.name in models:
                raise SlpError("model %s is declared twice: %s and %s"
                               % (model.name, models[model.name].file, model.file))
            models[model.name] = model
        units.extend(unit_tests)
    return Project(root, models, units)


# --- check: the spec of every model (README §3 Stage A, Rule 1) ---

def _sorted_models(project):
    """Models by name, so the output never depends on the order the files were read."""
    return [project.models[name] for name in sorted(project.models)]

def _strings(value):
    """A yml list of strings, or None when it is something the schema rule already blocked."""
    return value if isinstance(value, list) and all(isinstance(v, str) for v in value) else None

def check_spec_present(project):
    """README §3 Stage A — "PR cannot advance without a completed spec"; Rule 1: no spec, stop and ask."""
    return [block(m.file, m.name, "model has no meta.spec (README §3 Stage A)", "S1")
            for m in _sorted_models(project) if m.is_marts and m.spec is None]

def check_spec_schema(project):
    """README §3 Stage A — the six mandatory fields and their format, as schemas/spec.schema.json."""
    return [block(m.file, m.name, message, "S2") for m in _sorted_models(project)
            if m.spec is not None
            for message in schema_errors(m.spec, "spec", "spec")]

def check_spec_consistency(project):
    """README §3 Stage A — the spec names columns of this model and a query that exists."""
    out = []
    for model in _sorted_models(project):
        spec = model.spec if isinstance(model.spec, dict) else {}
        keys = _strings(spec.get("primary_key"))
        if keys and not model.columns:
            out.append(block(model.file, model.name,
                             "cannot verify primary_key: model declares no columns", "S3"))
        elif keys:
            out += [block(model.file, model.name, "spec.primary_key names %s, which the "
                          "model does not declare as a column" % column, "S3")
                    for column in keys if column not in model.columns]
        listed = _strings(spec.get("sensitive_columns"))
        if listed is not None:
            for column in sorted(set(listed) - set(model.sensitive)):
                why = ("the model does not declare that column" if column not in model.columns
                       else "that column is not marked meta.sensitive: true")
                out.append(block(model.file, model.name, "spec.sensitive_columns names %s, "
                                 "but %s" % (column, why), "S3"))
            out += [block(model.file, model.name, "column %s is marked meta.sensitive: true "
                          "but is not in spec.sensitive_columns" % column, "S3")
                    for column in sorted(set(model.sensitive) - set(listed))]
        query = spec.get("reconciliation_query")
        if spec.get("tier") == "critical" and isinstance(query, str) \
                and not (project.dir / query).is_file():
            out.append(block(model.file, model.name, "spec.reconciliation_query points at %s, "
                             "which does not exist" % query, "S3"))
    return out

# --- check: the pre-registration of every model (README §3 Stage B, Rule 6) ---

def _interval(value):
    """(min, max) when both ends are numbers, else None: the schema rule already blocked it."""
    if isinstance(value, dict) and isinstance(value.get("min"), (int, float)) \
            and isinstance(value.get("max"), (int, float)):
        return value["min"], value["max"]
    return None

def check_prereg_schema(project):
    """README §3 Stage B — the pre-registration format, as schemas/pre_registration.schema.json."""
    return [block(m.file, m.name, message, "P1") for m in _sorted_models(project)
            if m.prereg is not None
            for message in schema_errors(m.prereg, "pre_registration", "pre_registration")]

def check_prereg_consistency(project):
    """README §3 Stage B — Rule 6: the intervals are closed, and the metrics are the spec's."""
    out = []
    for model in _sorted_models(project):
        prereg = model.prereg if isinstance(model.prereg, dict) else None
        if prereg is None:
            continue
        if not isinstance(model.spec, dict):
            out.append(block(model.file, model.name, "pre-registration without a spec: the "
                             "spec is what the diff compares against", "P2"))
            continue
        declared = prereg.get("metrics") if isinstance(prereg.get("metrics"), dict) else {}
        wanted = model.spec.get("metrics") if isinstance(model.spec.get("metrics"), dict) else {}
        intervals = [("row_delta", _interval(prereg.get("row_delta")))]
        intervals += [("metrics.%s.delta_pct" % name, _interval(body.get("delta_pct")))
                      for name, body in sorted(declared.items()) if isinstance(body, dict)]
        for name, ends in intervals:
            if ends and ends[0] > ends[1]:
                out.append(block(model.file, model.name, "pre_registration.%s has min %s, "
                                 "which is above max %s" % (name, ends[0], ends[1]), "P2"))
        out += [block(model.file, model.name, "pre_registration.metrics declares %s, which "
                      "spec.metrics does not define" % name, "P2")
                for name in sorted(set(declared) - set(wanted))]
        out += [block(model.file, model.name, "spec.metrics defines %s, which "
                      "pre_registration.metrics declares no interval for" % name, "P2")
                for name in sorted(set(wanted) - set(declared))]
        out += [block(model.file, model.name, "pre_registration.altered_columns names %s, "
                      "which the model does not declare as a column" % column, "P2")
                for column in _strings(prereg.get("altered_columns")) or []
                if column not in model.columns]
    return out

# --- check: the uniqueness test the primary key must have (README §2 Rule 2) ---

def _blocks(cfg):
    """A test only counts when it can fail the build: enabled, and severity error."""
    return (cfg.get("enabled", True) is True
            and str(cfg.get("severity", "error")).lower() == "error")

def check_pk_test(project):
    """README §2 Rule 2 — "The agent creates a uniqueness test on the spec's primary_key"."""
    # The forms of uniqueness test this rule accepts. To accept another one, add
    # its name here and add a passing fixture under tests/fixtures/check/.
    ACCEPTED_PK_TESTS = ("unique", "unique_combination_of_columns",
                         "dbt_utils.unique_combination_of_columns")
    out = []
    for model in _sorted_models(project):
        spec = model.spec if isinstance(model.spec, dict) else {}
        keys = _strings(spec.get("primary_key")) if model.is_marts else None
        if not keys:
            continue
        covered = False
        for column, name, args, cfg in model.tests:
            if name not in ACCEPTED_PK_TESTS or not _blocks(cfg):
                continue
            combination = json.loads(args).get("combination_of_columns")
            covered = covered or ([column] == keys if name == "unique"
                                  else set(_strings(combination) or []) == set(keys))
        if not covered:
            out.append(block(model.file, model.name, "no uniqueness test on primary key "
                             "[%s]; accepted forms: %s"
                             % (", ".join(keys), ", ".join(ACCEPTED_PK_TESTS)), "T1"))
    return out

# --- gate: the two states it compares, as git sees them (README §2 Control 5B) ---

# Files that pin what the project builds with. Any change to one is a G6 finding.
PKG_FILES = ("packages.yml", "package-lock.yml", "dependencies.yml")

# What the gate rules read: the tree at the merge-base, the tree at head, and one
# light inventory per commit in between (oldest first, merge-base included).
Gate = NamedTuple("Gate", [("root", object), ("before", dict), ("after", dict),
                           ("walk", list)])

def _canon(obj):
    """One text for one value, whatever order the yml file happened to use."""
    return json.dumps(obj, sort_keys=True, default=str)

def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def git(root, *args):
    """Run one read-only git command. git is the only program these tools ever run."""
    done = subprocess.run(["git", "-C", str(root)] + list(args),
                          capture_output=True, text=True)
    if done.returncode != 0:
        raise SlpError("git %s: %s" % (" ".join(args), " ".join(done.stderr.split())))
    return done.stdout

def _without_prereg(entry):
    """A model's yml entry as the gate compares it: the pre-registration does not count."""
    copy = json.loads(_canon(entry))
    for holder in (copy, copy.get("config")):
        if isinstance(holder, dict) and isinstance(holder.get("meta"), dict):
            holder["meta"].pop("pre_registration", None)
    return _canon(copy)

def inventory(root, commit, full=True):
    """Everything the gate compares, as it was at one commit.

    A pure function of the commit: same commit in, same inventory out, whichever
    machine runs it. With full=False only the yml files are read, which is all
    the commit walk of G7 and I1 needs.
    """
    inv = {"tests": {}, "files": {}, "units": {}, "specs": {}, "preregs": {},
           "models": {}, "recons": {}, "packages": {}, "where": {}}
    listing = git(root, "ls-tree", "-r", "-z", "--name-only", commit, "--",
                  "models", "tests", "analyses", *PKG_FILES)
    sql = {}
    for path in sorted(p for p in listing.split("\0") if p):
        if path.startswith("models/") and path.endswith((".yml", ".yaml")):
            text = git(root, "show", "%s:%s" % (commit, path))
            models, units = read_doc(parse_yaml(text, "%s at %s" % (path, commit[:8])), path)
            for model in models:
                inv["where"][model.name] = path
                inv["specs"][model.name] = model.spec
                inv["preregs"][model.name] = model.prereg
                inv["models"][model.name] = _sha(_without_prereg(model.entry))
                for column, name, args, cfg in model.tests:
                    inv["tests"][(model.name, column, name, args)] = cfg
            for unit in units:
                body = dict((k, v) for k, v in unit.body.items() if k != "description")
                inv["units"][unit.name] = (unit.file, unit.model, _canon(body))
        elif not full:
            continue
        elif path.startswith("models/") and path.endswith(".sql"):
            sql[path.rsplit("/", 1)[-1][:-4]] = _sha(git(root, "show", "%s:%s" % (commit, path)))
        elif path.startswith("tests/"):
            inv["files"][path] = _sha(git(root, "show", "%s:%s" % (commit, path)))
        elif path.startswith("analyses/reconciliation_"):
            inv["recons"][path] = _sha(git(root, "show", "%s:%s" % (commit, path)))
        elif path in PKG_FILES:
            inv["packages"][path] = _sha(git(root, "show", "%s:%s" % (commit, path)))
    for name in inv["models"]:  # a model is its yml entry and its sql, together
        inv["models"][name] += sql.get(name, "")
    return inv

# --- gate rules: what this branch did to the tests (README §2 Control 5B) ---

def _by3(inv):
    """Data tests grouped by (model, column, test name), whatever their arguments."""
    out = {}
    for (model, column, name, args), cfg in sorted(inv["tests"].items()):
        out.setdefault((model, column, name), (set(), cfg))[0].add(args)
    return out

def _on(cfg):
    """A test that is switched off asserts nothing."""
    return cfg.get("enabled", True) is True

def _named(model, column):
    return "%s.%s" % (model, column) if column else model

def _file(ctx, model):
    """The yml that declares the model now, or the one that declared it before."""
    return ctx.after["where"].get(model) or ctx.before["where"].get(model) or ""

def _changed(ctx, kind, keys=None):
    """Keys of one part of the inventory whose value is not the same on both sides."""
    if keys is None:
        keys = set(ctx.before[kind]) | set(ctx.after[kind])
    return sorted(k for k in keys if ctx.before[kind].get(k) != ctx.after[kind].get(k))

def gate_test_removed(ctx):
    """README §2 Control 5B — "Test removed": an agent can remove a failing test instead of fixing the code."""
    before, after = _by3(ctx.before), _by3(ctx.after)
    out = []
    for key in sorted(before):
        model, column, name = key
        said, file = "test '%s' on %s " % (name, _named(model, column)), _file(ctx, model)
        if key not in after:
            out.append(block(file, model, said + "exists on main but not in this PR", "G1"))
        elif before[key][0] - after[key][0]:
            out.append(block(file, model, said + "changed its arguments; if that is intended, a "
                             "human changes it before the agent starts, or in a separate PR", "G1"))
        elif _on(before[key][1]) and not _on(after[key][1]):
            out.append(block(file, model, said + "was disabled", "G1"))
    for path in _changed(ctx, "files", set(ctx.before["files"])):
        out.append(block(path, "", "singular or generic test %s was removed or changed" % path, "G1"))
    for name in sorted(set(ctx.before["units"]) - set(ctx.after["units"])):
        file, model, _ = ctx.before["units"][name]
        out.append(block(file, model, "unit test '%s' was removed" % name, "G1"))
    return out

# --- Rule registries. A rule is one function: context in, findings out. ---

CHECK_RULES = [check_spec_present, check_spec_schema, check_spec_consistency,
               check_prereg_schema, check_prereg_consistency, check_pk_test]
GATE_RULES = [gate_test_removed]
COMPARE_RULES = []

def apply_rules(rules, context):
    """Run every rule in order and collect what they found."""
    return [finding for rule in rules for finding in rule(context)]


# --- Command line ---

def cmd_check(args):
    """check: read the project, run the check rules, print what they found."""
    project = read_project(args.project_dir)
    return report(apply_rules(CHECK_RULES, project), "check",
                  _count(len(project.models), "model"))

def cmd_gate(args):
    """gate: compare the merge-base with head, and walk the commits between them."""
    root = pathlib.Path(args.project_dir).resolve()
    # The merge-base, not the branch tip: a main that moved on is not this PR's doing.
    base = git(root, "merge-base", args.base, args.head).strip()
    commits = git(root, "rev-list", "--first-parent", "--reverse",
                  "%s..%s" % (base, args.head)).split()
    if not commits:
        return report([], "gate", "no commits")
    before, after = inventory(root, base), inventory(root, args.head)
    # The walk starts at the merge-base and ends at head, both already read.
    walk = [before] + [inventory(root, ref, full=False) for ref in commits[:-1]] + [after]
    return report(apply_rules(GATE_RULES, Gate(root, before, after, walk)), "gate",
                  "no changes" if before == after else _count(len(commits), "commit"))

def build_parser():
    """The command line of Section 2 of the backlog, and nothing else."""
    parser = argparse.ArgumentParser(prog="slp", description=__doc__.splitlines()[0])
    parser.add_argument("--version", action="version", version=__version__)
    subs = parser.add_subparsers(dest="command")
    check = subs.add_parser("check", help="the spec of every model in models/marts/")
    gate = subs.add_parser("gate", help="what this branch did to the tests")
    compare = subs.add_parser("compare", help="a diff against its pre-registration")
    gate.add_argument("--base", required=True, help="git ref the branch started from")
    gate.add_argument("--head", default="HEAD", help="git ref to judge")
    compare.add_argument("diffs", nargs="+", metavar="diff.json")
    for sub in (check, gate, compare):
        sub.add_argument("--project-dir", default=".", help="root of the dbt project")
    return parser

def main(argv=None):
    """Parse, run, and turn anything unexpected into exit code 2."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_usage(sys.stderr)
        return 2
    try:
        return {"check": cmd_check, "gate": cmd_gate}[args.command](args)
    except SlpError as exc:
        sys.stderr.write("ERROR %s\n" % exc)
        return 2
    except Exception as exc:  # fail closed: an unexpected error is never a pass
        sys.stderr.write("ERROR unexpected %s: %s\n" % (type(exc).__name__, exc))
        return 2

if __name__ == "__main__":
    sys.exit(main())
