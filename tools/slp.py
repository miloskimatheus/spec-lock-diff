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

__version__ = "0.3.0"
SCHEMA_DIR = pathlib.Path(__file__).resolve().parent / "schemas"

# Where the models the framework makes mandatory live (README §3 Stage A: "In all
# models within models/marts/**"). A project that keeps them elsewhere says so
# with --marts-path, because a tool pointed at the wrong folder finds nothing
# wrong with anything, and that reads exactly like a pass.
MARTS = ("models/marts",)

# Keys that say how a test runs rather than what it asserts. They are kept apart
# from the test arguments because gate rules read them (G2 where, G3 severity).
CFG_KEYS = ("enabled", "error_if", "fail_calc", "limit", "severity",
            "store_failures", "warn_if", "where")

# Every rule id these tools can print. The README coverage table has one row per
# id and the fixtures one folder per id; meta-test M2 keeps the three in step.
RULE_IDS = ("S1", "S2", "S3", "S4", "P1", "P2", "T1",
            "G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "I1", "I3",
            "C0", "C1", "C2", "C3", "C4", "C5", "C6", "C7", "I2")
# Rules that only ever inform. The README asks for what they say to be visible,
# not for it to stop the pull request, so they never raise the exit code.
INFO_RULES = ("I1", "I2", "I3")


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
    """Print the findings sorted, then one summary line. Returns the exit code.

    By file, then by model, then what blocks before what only informs, and ties
    are left in the order the rules produced them - which is itself sorted, so
    two runs still print the same lines in the same order. A rule that has
    several things to say usually has a reading order for them, and I2's is the
    order Stage E asks the reviewer to read the numbers in.
    """
    for finding in sorted(findings,
                          key=lambda f: (f.file, f.model, f.severity != "BLOCK", f.rule_id)):
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
        # dbt renders a yml through jinja before reading it and these tools do
        # not, so say which of the two problems this is: "cannot parse" on its
        # own sends the reader hunting for a typo that is not there.
        why = " - this file contains jinja, which these tools do not render" \
            if re.search(r"{%|{{", text) else ""
        raise SlpError("cannot parse %s: %s%s" % (where, " ".join(str(exc).split()), why))
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
Project = NamedTuple("Project", [("dir", object), ("models", dict), ("unit_tests", list),
                                 ("files", dict)])

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

def read_doc(doc, rel, marts=MARTS):
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
                            sensitive, tests, rel.startswith(_dirs(marts))))
    for entry in _entries(doc.get("unit_tests"), "unit_tests", rel):
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            raise SlpError("a unit test without a name in %s" % rel)
        units.append(UnitTest(name, entry.get("model") or "", rel, entry))
    return models, units

def _dirs(marts, top=False):
    """The marts paths as prefixes, or the directories that hold them - where yml is read from."""
    paths = tuple(p.strip("/") + "/" for p in marts)
    return tuple(sorted(set(p.split("/")[0] + "/" for p in paths))) if top else paths

def read_project(project_dir, marts=MARTS):
    """Read the model yml into models and unit tests. No git, no dbt, no warehouse."""
    root = pathlib.Path(project_dir).resolve()
    for path in _dirs(marts):
        if not (root / path).is_dir():
            raise SlpError("%s not found under %s; nothing to check is not OK"
                           % (path, project_dir))
    models, units, files = {}, [], {}
    for path in sorted(p for top in _dirs(marts) for p in (root / top).rglob("*.sql")
                       if p.is_file()):
        files[path.stem] = path.relative_to(root).as_posix()
    for path in sorted(p for top in _dirs(marts, True) for p in (root / top).rglob("*")
                       if p.suffix in (".yml", ".yaml") and p.is_file()):
        rel = path.relative_to(root).as_posix()
        found, unit_tests = read_doc(load_yaml(path), rel, marts)
        for model in found:
            if model.name in models:
                raise SlpError("model %s is declared twice: %s and %s"
                               % (model.name, models[model.name].file, model.file))
            models[model.name] = model
        units.extend(unit_tests)
    # A model is in marts when the sql that makes it is, wherever its yml sits: a
    # project that documents everything in one models/schema.yml is ordinary dbt,
    # and reading only the yml path would exempt every one of those models.
    for name in set(files) & set(models):
        models[name] = models[name]._replace(is_marts=True)
    return Project(root, models, units, files)


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

def check_model_declared(project):
    """README §3 Stage A — "PR cannot advance without a completed spec": a model no yml declares has no spec, and nothing here can ask it for one."""
    return [block(project.files[name], name, "no yml declares this model; an undeclared "
                  "model has no spec, no primary key and no test, and every other rule "
                  "here would pass it in silence", "S4")
            for name in sorted(set(project.files) - set(project.models))]

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

# Config keys that stop a test from failing even while it is enabled and severe:
# a threshold it never reaches, or rows it never looks at. dbt runs the test
# either way and reports a pass. DEAD_KEYS are the ones that can only ever mute;
# a `where` is the one that might instead be honest scoping, so it is held apart
# - T1 refuses it on the one test the framework makes mandatory, and I3 shows it
# to the human on every test a branch adds.
DEAD_KEYS = ("error_if", "warn_if", "fail_calc", "limit")
MUTE_KEYS = ("where",) + DEAD_KEYS

def _muted(cfg, keys=MUTE_KEYS):
    """Why a test cannot fail the build, in one clause, or "" when it can."""
    if cfg.get("enabled", True) is not True:
        return "it is disabled"
    if str(cfg.get("severity", "error")).lower() != "error":
        return "its severity is %s" % cfg.get("severity")
    narrowed = [key for key in keys if key in cfg]
    return "it sets %s" % ", ".join(narrowed) if narrowed else ""

def _blocks(cfg):
    """A test only counts when it can fail the build."""
    return not _muted(cfg)

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
        covered, muted = False, ""
        for column, name, args, cfg in model.tests:
            if name not in ACCEPTED_PK_TESTS:
                continue
            combination = json.loads(args).get("combination_of_columns")
            if not ([column] == keys if name == "unique"
                    else set(_strings(combination) or []) == set(keys)):
                continue
            covered, muted = covered or _blocks(cfg), muted or _muted(cfg)
        if covered:
            continue
        out.append(block(model.file, model.name,
                         "the uniqueness test on primary key [%s] cannot fail the build: %s"
                         % (", ".join(keys), muted) if muted else
                         "no uniqueness test on primary key [%s]; accepted forms: %s"
                         % (", ".join(keys), ", ".join(ACCEPTED_PK_TESTS)), "T1"))
    return out

# --- gate: the two states it compares, as git sees them (README §2 Control 5B) ---

# Files that pin what the project builds with. Any change to one is a G6 finding.
PKG_FILES = ("packages.yml", "package-lock.yml", "dependencies.yml")

# What the gate rules read: the tree at the merge-base, the tree at head, and one
# light inventory per commit in between (oldest first, merge-base included).
Gate = NamedTuple("Gate", [("root", object), ("before", dict), ("after", dict),
                           ("walk", list), ("marts", tuple)])

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

def git_blobs(root, commit, paths):
    """The content of many files at one commit, read down one pipe.

    `git show` costs a process per file, and the commit walk asks for every yml
    at every commit: a project of 150 models with a 30-commit branch spawned
    close to five thousand of them, twenty seconds of process start-up before a
    rule had looked at anything. `cat-file --batch` answers the lot at once.
    """
    if not paths:
        return {}
    asked = "".join("%s:%s\n" % (commit, path) for path in paths)
    done = subprocess.run(["git", "-C", str(root), "cat-file", "--batch"],
                          input=asked.encode("utf-8"), capture_output=True)
    if done.returncode != 0:
        raise SlpError("git cat-file: %s"
                       % " ".join(done.stderr.decode("utf-8", "replace").split()))
    out, data, at = {}, done.stdout, 0
    for path in paths:
        # One header line - sha, type, size in bytes - then that many bytes, then
        # a newline. Sizes are in bytes, so the split happens before decoding.
        end = data.index(b"\n", at)
        header = data[at:end].split()
        if len(header) != 3:
            raise SlpError("cannot read %s at %s: %s"
                           % (path, commit[:8], data[at:end].decode("utf-8", "replace")))
        at = end + 1 + int(header[2]) + 1
        try:
            out[path] = data[end + 1:at - 1].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SlpError("cannot read %s at %s: %s" % (path, commit[:8], exc))
    return out

def _without_prereg(entry):
    """A model's yml entry as the gate compares it: the pre-registration does not count."""
    copy = json.loads(_canon(entry))
    for holder in (copy, copy.get("config")):
        if isinstance(holder, dict) and isinstance(holder.get("meta"), dict):
            holder["meta"].pop("pre_registration", None)
    return _canon(copy)

def inventory(root, commit, full=True, marts=MARTS):
    """Everything the gate compares, as it was at one commit.

    A pure function of the commit: same commit in, same inventory out, whichever
    machine runs it. With full=False only the yml files are read, which is all
    the commit walk of G7 and I1 needs.
    """
    inv = {"tests": {}, "files": {}, "units": {}, "specs": {}, "preregs": {},
           "models": {}, "sqls": {}, "code": {}, "recons": {}, "packages": {},
           "where": {}}
    listing = git(root, "ls-tree", "-r", "-z", "--name-only", commit, "--",
                  *(_dirs(marts, True) + ("tests", "analyses") + PKG_FILES))
    # What to read is decided first and read in one go, so that the cost of the
    # commit walk is one git process per commit rather than one per file.
    plan = []
    for path in sorted(p for p in listing.split("\0") if p):
        if path.startswith(_dirs(marts, True)) and path.endswith((".yml", ".yaml")):
            plan.append(("yml", path))
        elif not full:
            continue
        elif path.startswith(_dirs(marts, True)) and path.endswith(".sql"):
            plan.append(("sql", path))
        elif path.startswith("tests/"):
            plan.append(("files", path))
        elif path.startswith("analyses/reconciliation_"):
            plan.append(("recons", path))
        elif path in PKG_FILES:
            plan.append(("packages", path))
    blobs = git_blobs(root, commit, [path for _, path in plan])
    for kind, path in plan:
        if kind == "sql":
            name = path.rsplit("/", 1)[-1][:-4]
            inv["sqls"][name] = path
            inv["code"][name] = _sha(blobs[path])
            continue
        if kind != "yml":
            inv[kind][path] = _sha(blobs[path])
            continue
        models, units = read_doc(parse_yaml(blobs[path], "%s at %s" % (path, commit[:8])),
                                 path, marts)
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
    for name in inv["models"]:  # a model is its yml entry and its sql, together
        inv["models"][name] += inv["code"].get(name, "")
    return inv

# --- gate rules: what this branch did to the tests (README §2 Control 5B) ---

def _by3(inv):
    """Data tests grouped by (model, column, test name), each keeping its own config.

    A column often carries two tests of the same name - two `relationships`, two
    `accepted_values`, several `dbt_utils.expression_is_true` - and each of them
    is declared with a config of its own. Grouping them under one config would
    keep whichever sorted first and drop the rest, so every other one could be
    given a `where`, a `severity: warn` or an `enabled: false` unseen.

    Two declarations whose arguments are identical too are held as a list under
    the one key and compared as a bag: how many there were, how many there are,
    and which configs are in the second bag and not the first. Numbering them
    instead would be wrong in the case that matters - remove the first of two
    and the second inherits its number, which reads as a config edit rather
    than as a removal.
    """
    out = {}
    for (model, column, name, args), cfgs in sorted(inv["tests"].items()):
        out.setdefault((model, column, name), {})[args] = cfgs
    return out

def _which(group, args):
    """Which of several same-named tests on the same column this one is."""
    if len(group) < 2:
        return ""
    return " (%s)" % ", ".join("%s=%s" % pair for pair in sorted(json.loads(args).items()))

def _on(cfg):
    """A test that is switched off asserts nothing."""
    return cfg.get("enabled", True) is True

def _named(model, column):
    return "%s.%s" % (model, column) if column else model

def _file(ctx, model):
    """The yml that declares the model now, or the one that declared it before."""
    return ctx.after["where"].get(model) or ctx.before["where"].get(model) or ""

def _in_marts(ctx, model):
    """In marts when the yml that declares the model is, or the sql that makes it is."""
    return any((inv[kind].get(model) or "").startswith(_dirs(ctx.marts))
               for inv in (ctx.before, ctx.after) for kind in ("where", "sqls"))

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
        old, new = before[key], after.get(key, {})
        gone = sorted(set(old) - set(new))
        if not new:
            out.append(block(file, model, said + "exists on main but not in this PR", "G1"))
        elif gone:
            out.append(block(file, model, said + "changed its arguments%s; if that is intended, "
                             "a human changes it before the agent starts, or in a separate PR"
                             % _which(old, gone[0]), "G1"))
        else:
            for args in sorted(old):
                live = lambda bag: sum(1 for cfg in bag if _on(cfg))
                if len(new[args]) < len(old[args]):
                    out.append(block(file, model, said + "was declared %d times on main and %d "
                                     "here%s" % (len(old[args]), len(new[args]),
                                                 _which(old, args)), "G1"))
                elif live(new[args]) < live(old[args]):
                    out.append(block(file, model, said + "was disabled" + _which(old, args), "G1"))
    for path in _changed(ctx, "files", set(ctx.before["files"])):
        out.append(block(path, "", "singular or generic test %s was removed or changed" % path, "G1"))
    for key in sorted(set(ctx.before["units"]) - set(ctx.after["units"])):
        file, model, _ = ctx.before["units"][key]
        out.append(block(file, model, "unit test '%s' was removed" % key[1], "G1"))
    return out

def gate_test_filter(ctx):
    """README §2 Control 5B — "WHERE or exclusion clause added to a test": a way to make a test pass without fixing the problem."""
    out = []
    before, after = _by3(ctx.before), _by3(ctx.after)
    for key in sorted(set(before) & set(after)):
        for args in sorted(set(before[key]) & set(after[key])):
            old = [cfg.get("where") for cfg in before[key][args]]
            for new in sorted(set(cfg.get("where") for cfg in after[key][args]) - set(old)):
                if new is not None:
                    out.append(block(_file(ctx, key[0]), key[0], "test '%s' on %s%s now skips "
                                     "rows with where: %s" % (key[2], _named(key[0], key[1]),
                                                              _which(after[key], args), new), "G2"))
    return out

def _sev(cfg):
    """The severity dbt will use: error unless the test says otherwise."""
    return str(cfg.get("severity", "error")).lower()

def gate_test_severity(ctx):
    """README §2 Control 5B — "severity downgraded (e.g., error → warn)" and "a test added that cannot fail": a test that reports a pass whatever the data does is not a test, whether this branch made it that way or wrote it that way."""
    out = []
    before, after = _by3(ctx.before), _by3(ctx.after)
    for key in sorted(after):
        for args in sorted(after[key]):
            was = before.get(key, {}).get(args, [])
            said = "test '%s' on %s%s " % (key[2], _named(key[0], key[1]),
                                           _which(after[key], args))
            file = _file(ctx, key[0])
            # Every declaration this branch did not inherit unchanged, held
            # against the bag of declarations it could have come from.
            for new in [cfg for cfg in after[key][args] if cfg not in was]:
                if not was:  # born this way, and every reason it cannot fail counts
                    why = _muted(new, DEAD_KEYS)
                    if why:
                        out.append(block(file, key[0], said + "is new and cannot fail the "
                                         "build: %s" % why, "G3"))
                    continue
                if _sev(new) == "warn" and not any(_sev(cfg) == "warn" for cfg in was):
                    out.append(block(file, key[0], said + "was downgraded from error to warn, "
                                     "so it cannot block", "G3"))
                for name in DEAD_KEYS:
                    if name in new and not any(cfg.get(name) == new[name] for cfg in was):
                        out.append(block(file, key[0], said + "sets %s, which changes what "
                                         "counts as failing" % name, "G3"))
    return out

def gate_test_narrowed(ctx):
    """README §2 Control 5B — "WHERE or exclusion clause added to a test": a test this branch adds has no earlier self to be weaker than, and still asserts nothing about the rows its filter removes. Whether those are rows that cannot fail or rows that would have is a reading, so this one is shown and not blocked."""
    out = []
    before, after = _by3(ctx.before), _by3(ctx.after)
    for key in sorted(after):
        for args in sorted(after[key]):
            if before.get(key, {}).get(args):
                continue
            out += [info(_file(ctx, key[0]), key[0], "test '%s' on %s is new and skips rows "
                         "with where: %s" % (key[2], _named(key[0], key[1]), cfg["where"]), "I3")
                    for cfg in after[key][args] if cfg.get("where") is not None]
    return out

def gate_unit_test_changed(ctx):
    """README §2 Control 5B — "expect value changed in an existing test": if the agent changes the expected result, any result becomes correct."""
    out = []
    for key in sorted(set(ctx.before["units"]) & set(ctx.after["units"])):
        file, model, body = ctx.after["units"][key]
        if ctx.before["units"][key][2] != body:
            out.append(block(file, model, "unit test '%s' was changed; the rows it is "
                             "given and the rows it expects are the question and the answer, "
                             "and this PR wrote both" % key[1], "G4"))
    return out

def gate_recon_with_model(ctx):
    """README §2 Control 5B — "analyses/reconciliation_* changed in the same PR as the model": like a student writing the exam and the answer key."""
    out = []
    moved = set(_changed(ctx, "recons"))
    for model in sorted(ctx.after["specs"]):
        spec = ctx.after["specs"][model]
        query = spec.get("reconciliation_query") if isinstance(spec, dict) else None
        if query in moved and ctx.before["models"].get(model) != ctx.after["models"].get(model):
            out.append(block(query, model, "%s changed in the same PR as the model it checks; "
                             "a human changes the reconciliation, in its own PR" % query, "G5"))
    return out

def gate_packages(ctx):
    """README §2 Control 5B — "Package pin changed": changing dependency versions can introduce different behaviors."""
    return [block(path, "", "%s changed on this branch; the versions the project builds with "
                  "are a human decision" % path, "G6")
            for path in _changed(ctx, "packages")]

def gate_spec_changed(ctx):
    """README §1 Principle 1 — "The human decides before, by writing the spec"; README §3 Stage A — the six fields are read and approved before any line of code is written."""
    out = []
    for model in sorted(ctx.after["specs"]):
        spec = ctx.after["specs"][model]
        if spec is None or not _in_marts(ctx, model):
            continue
        first = next((inv["specs"][model] for inv in ctx.walk
                      if inv["specs"].get(model) is not None), None)
        if first is not None and _canon(first) != _canon(spec):
            out.append(block(_file(ctx, model), model, "meta.spec changed after it was first "
                             "written on this branch; the spec is the human's decision, and a "
                             "human changes it in a separate PR", "G7"))
    return out

def gate_prereg_present(ctx):
    """README §3 Stage C — "Cannot start without a valid pre-registration"; Stage B — the agent declares the numerical changes it expects "before writing any code"."""
    out = []
    for model in sorted(ctx.after["code"]):
        if ctx.before["code"].get(model) == ctx.after["code"][model]:
            continue
        if ctx.after["preregs"].get(model) is not None \
                or model not in ctx.after["where"] or not _in_marts(ctx, model):
            continue
        out.append(block(_file(ctx, model), model, "the sql of this model changed on this "
                         "branch and it carries no meta.pre_registration; nothing downstream "
                         "has an interval to hold its numbers against, and compare will not "
                         "so much as look at it", "G8"))
    return out

def gate_prereg_counter(ctx):
    """README §3 Stage B — "a change counter is incremented in the PR (visible to the Author in review)"."""
    out = []
    for model in sorted(ctx.after["preregs"]):
        if ctx.after["preregs"][model] is None:
            continue
        seen, edits = None, 0
        for inv in ctx.walk:  # the commit it first appears in is not an edit
            current = inv["preregs"].get(model)
            if current is None:
                continue
            if seen is not None and _canon(current) != seen:
                edits += 1
            seen = _canon(current)
        if edits:
            out.append(info(_file(ctx, model), model, "pre-registration was modified %s after "
                            "it was first written" % _count(edits, "time"), "I1"))
    return out

# --- compare: the diff against the pre-registration (README §3 Stage E) ---

# One measured model: the file that carries the numbers, the model they claim to
# be about, and whether the pair is sound enough for C1 to C6 to say anything.
Diff = NamedTuple("Diff", [("file", str), ("name", str), ("data", dict),
                           ("project", object), ("model", object), ("ok", bool)])

def compare_contract(ctx):
    """README §3 Stage E step 3 — "Each diff number is automatically compared with the intervals declared in the pre-registration": both sides have to be readable first."""
    out = [block(ctx.file, ctx.name, message, "C0")
           for message in schema_errors(ctx.data, "diff", "diff")]
    if ctx.model is None:
        out.append(block(ctx.file, ctx.name, "models/ declares no model named %s in this "
                         "project" % (ctx.name or "?"), "C0"))
    elif not isinstance(ctx.model.prereg, dict):
        out.append(block(ctx.file, ctx.name, "the model has no meta.pre_registration; a number "
                         "nobody committed to in advance is not evidence", "C0"))
    else:
        one = Project(ctx.project.dir, {ctx.name: ctx.model}, [], {})
        out += [f._replace(file=ctx.file, rule_id="C0")
                for f in apply_rules([check_prereg_schema, check_prereg_consistency], one)]
    window = ctx.data.get("window")
    if isinstance(window, dict) and not out:
        out.append(info(ctx.file, ctx.name, "measured over %s from %s to %s"
                        % (window.get("column"), window.get("start"), window.get("end")), "C0"))
    return out

def compare_rows(ctx):
    """README §3 Stage E step 3 — "A number is outside the declared interval (e.g., row delta is 15,000, but the pre-registration said max: 12000)"."""
    if not ctx.ok:
        return []
    low, high = _interval(ctx.model.prereg["row_delta"])
    value = ctx.data["row_delta"]
    if low <= value <= high:
        return []
    return [block(ctx.file, ctx.name, "row_delta is %s, pre-registration allows %s..%s"
                  % (value, low, high), "C1")]

def compare_removed_pks(ctx):
    """README §3 Stage E step 3 — the rows that exist in production and not in the new version are a number the pre-registration has to allow."""
    if not ctx.ok:
        return []
    most, value = ctx.model.prereg["removed_pks"]["max"], ctx.data["removed_pks"]
    if value <= most:
        return []
    return [block(ctx.file, ctx.name, "removed_pks is %s, pre-registration allows at most %s"
                  % (value, most), "C2")]

def compare_columns(ctx):
    """README §3 Stage E step 3 — "A column shows a difference but is not in the pre-registration's altered_columns list"."""
    if not ctx.ok:
        return []
    declared = set(ctx.model.prereg["altered_columns"])
    measured = set(ctx.data["altered_columns"])
    out = [block(ctx.file, ctx.name, "column %s changed and is not in "
                 "pre_registration.altered_columns" % column, "C3")
           for column in sorted(measured - declared)]
    out += [info(ctx.file, ctx.name, "column %s was pre-registered as altered and did not "
                 "change" % column, "C3") for column in sorted(declared - measured)]
    return out

def compare_metrics(ctx):
    """README §3 Stage E step 3 — each metric of the spec is compared with the percentage interval the pre-registration declared for it."""
    if not ctx.ok:
        return []
    out = []
    declared, measured = ctx.model.prereg["metrics"], ctx.data["metrics"]
    for name in sorted(declared):
        low, high = _interval(declared[name]["delta_pct"])
        if name not in measured:
            out.append(block(ctx.file, ctx.name, "metric %s was pre-registered and the diff "
                             "does not measure it" % name, "C4"))
            continue
        value = measured[name]["delta_pct"]
        if value is None:
            out.append(block(ctx.file, ctx.name, "metric %s cannot be evaluated: the "
                             "production value is 0" % name, "C4"))
        elif not low <= value <= high:
            out.append(block(ctx.file, ctx.name, "metric %s moved %s percent, pre-registration "
                             "allows %s..%s" % (name, value, low, high), "C4"))
    out += [block(ctx.file, ctx.name, "metric %s moved %s percent and was not pre-registered"
                  % (name, measured[name]["delta_pct"], ), "C4")
            for name in sorted(set(measured) - set(declared))
            if measured[name]["delta_pct"] != 0]
    return out

def compare_refactoring(ctx):
    """README §3 Stage E step 3 — "The type is refactoring but some delta is not zero"."""
    if not ctx.ok or ctx.model.prereg.get("type") != "refactoring":
        return []
    moved = ["row_delta %s" % ctx.data["row_delta"] if ctx.data["row_delta"] else "",
             "removed_pks %s" % ctx.data["removed_pks"] if ctx.data["removed_pks"] else "",
             "altered columns %s" % ", ".join(sorted(ctx.data["altered_columns"]))
             if ctx.data["altered_columns"] else ""]
    moved += ["metric %s %s percent" % (name, body["delta_pct"])
              for name, body in sorted(ctx.data["metrics"].items()) if body["delta_pct"]]
    moved = [m for m in moved if m]
    if not moved:
        return []
    return [block(ctx.file, ctx.name, "pre-registered as a refactoring, which may not change "
                  "any number, and the diff moved: %s" % "; ".join(moved), "C5")]

def _drift(numbers):
    """How far the model is from the source of truth, in percent; None when there is no percentage."""
    outside = numbers["external_value"]
    return None if outside == 0 else abs(numbers["model_value"] - outside) / abs(outside) * 100

def _band(interval):
    """The band declared for a number and how wide it is: what Stage E asks the reviewer to judge."""
    low, high = _interval(interval)
    return "declared %s..%s (a band %s)" % (low, high, "%g wide" % (high - low)
                                            if high != low else "that pins it to one value")

def compare_reconciliation(ctx):
    """README §3 Stage E step 4 — "If the difference is greater than the tolerance, the PR is blocked"."""
    if not ctx.ok:
        return []
    spec = ctx.model.spec if isinstance(ctx.model.spec, dict) else {}
    numbers = ctx.data.get("reconciliation")
    if numbers is None:
        if spec.get("tier") != "critical":
            return []
        return [block(ctx.file, ctx.name, "critical model without reconciliation numbers; the "
                      "query in the spec runs on full data and its two numbers belong in the "
                      "diff", "C6")]
    allowed = spec.get("reconciliation_tolerance")
    if not (isinstance(allowed, str) and re.match(r"^[0-9]+(\.[0-9]+)?%$", allowed)):
        return [block(ctx.file, ctx.name, "reconciliation numbers given, and the spec declares "
                      "no reconciliation_tolerance to read them against", "C6")]
    drift = _drift(numbers)
    said = "the model says %s and the source of truth says %s" \
        % (numbers["model_value"], numbers["external_value"])
    if drift is None:  # nothing to take a percentage of; only an exact match passes
        if numbers["model_value"] == 0:
            return []
        return [block(ctx.file, ctx.name, "reconciliation: %s; no percentage makes that "
                      "difference small" % said, "C6")]
    if drift <= float(allowed[:-1]):
        return []
    return [block(ctx.file, ctx.name, "reconciliation: %s, a difference of %.4g percent, and "
                  "the spec allows %s" % (said, drift, allowed), "C6")]

def compare_summary(ctx):
    """README §3 Stage E step 5 — "Is the pre-registration narrow enough to be able to fail? Does the reason justify the interval?": the human is asked to judge the interval, so the interval, the reason and the number that landed in it are printed whether or not anything blocked."""
    if not ctx.ok:
        return []
    pre, data, out = ctx.model.prereg, ctx.data, []
    say = lambda text: out.append(info(ctx.file, ctx.name, text, "I2"))
    say("declared as a %s, because: %s" % (pre["type"], pre["reason"]))
    say("row_delta %s, %s" % (data["row_delta"], _band(pre["row_delta"])))
    say("removed_pks %s, declared at most %s" % (data["removed_pks"], pre["removed_pks"]["max"]))
    for name in sorted(pre["metrics"]):
        say("metric %s moved %s percent, %s"
            % (name, (data["metrics"].get(name) or {}).get("delta_pct"),
               _band(pre["metrics"][name]["delta_pct"])))
    say("altered columns measured [%s], declared [%s]"
        % (", ".join(sorted(data["altered_columns"])), ", ".join(sorted(pre["altered_columns"]))))
    numbers = data.get("reconciliation")
    if numbers is not None:
        drift = _drift(numbers)
        say("reconciliation: model %s against source of truth %s, a difference of %s, and the "
            "spec allows %s" % (numbers["model_value"], numbers["external_value"],
                                "no percentage" if drift is None else "%.4g percent" % drift,
                                (ctx.model.spec or {}).get("reconciliation_tolerance")))
    if not isinstance(data.get("window"), dict):
        say("this diff declares no window; README §3 Stage E step 2 asks for a closed "
            "event_time window identical on both sides, and nothing here can check that")
    return out


# What compare has to say about the run as a whole rather than about one file.
Run = NamedTuple("Run", [("project", object), ("measured", set), ("files", int)])

def compare_coverage(ctx):
    """README §3 Stage E step 3 — "Each diff number is automatically compared with the intervals declared in the pre-registration": every pre-registered model, not only the ones whose numbers turned up."""
    return [block(ctx.project.models[name].file, name, "this model has a pre-registration "
                  "and no diff.json among the %s read; a number that never arrived was "
                  "never compared with anything, and a gate that did not look is not a "
                  "gate that passed" % _count(ctx.files, "file"), "C7")
            for name in sorted(ctx.project.models)
            if isinstance(ctx.project.models[name].prereg, dict) and name not in ctx.measured]


# --- Rule registries. A rule is one function: context in, findings out. ---

CHECK_RULES = [check_spec_present, check_model_declared, check_spec_schema,
               check_spec_consistency,
               check_prereg_schema, check_prereg_consistency, check_pk_test]
GATE_RULES = [gate_test_removed, gate_test_filter, gate_test_severity,
              gate_test_narrowed, gate_unit_test_changed, gate_recon_with_model,
              gate_packages, gate_spec_changed, gate_prereg_present,
              gate_prereg_counter]
COMPARE_RULES = [compare_contract, compare_rows, compare_removed_pks,
                 compare_columns, compare_metrics, compare_refactoring,
                 compare_reconciliation, compare_summary]
# Rules about the whole run. They see every file at once, so they cannot live in
# the loop above; everything else about them - docstring, rule id, fixtures - is
# the same, and the meta-tests hold them to it.
COMPARE_RUN_RULES = [compare_coverage]

def apply_rules(rules, context):
    """Run every rule in order and collect what they found."""
    return [finding for rule in rules for finding in rule(context)]


# --- Command line ---

def cmd_check(args):
    """check: read the project, run the check rules, print what they found.

    The note says how many models were held to the framework and how many were
    read at all. Only the first is coverage, and a count of everything reads
    like one.
    """
    project = read_project(args.project_dir, args.marts_path)
    inside = sum(1 for m in project.models.values() if m.is_marts)
    return report(apply_rules(CHECK_RULES, project), "check", "%s in %s, of %s read"
                  % (_count(inside, "model") or "no model",
                     ", ".join(_dirs(args.marts_path)),
                     _count(len(project.models), "model") or "none"))

def cmd_gate(args):
    """gate: compare the merge-base with head, and walk the commits between them."""
    root = pathlib.Path(args.project_dir).resolve()
    # The merge-base, not the branch tip: a main that moved on is not this PR's doing.
    base = git(root, "merge-base", args.base, args.head).strip()
    commits = git(root, "rev-list", "--first-parent", "--reverse",
                  "%s..%s" % (base, args.head)).split()
    if not commits:
        return report([], "gate", "no commits")
    marts = tuple(args.marts_path)
    before, after = inventory(root, base, marts=marts), inventory(root, args.head, marts=marts)
    # The walk starts at the merge-base and ends at head, both already read.
    walk = [before] + [inventory(root, ref, False, marts) for ref in commits[:-1]] + [after]
    return report(apply_rules(GATE_RULES, Gate(root, before, after, walk, marts)), "gate",
                  "no changes" if before == after else _count(len(commits), "commit"))

def cmd_compare(args):
    """compare: hold every diff.json against the pre-registration of its model."""
    project = read_project(args.project_dir, args.marts_path)
    out, measured = [], set()
    for path in args.diffs:
        data = load_json(path)
        data = data if isinstance(data, dict) else {}
        name = data.get("model") if isinstance(data.get("model"), str) else ""
        ctx = Diff(str(path), name, data, project, project.models.get(name), False)
        blocked = any(f.severity == "BLOCK" for f in compare_contract(ctx))
        out += apply_rules(COMPARE_RULES, ctx._replace(ok=not blocked))
        measured.add(name)
    out += apply_rules(COMPARE_RUN_RULES, Run(project, measured, len(args.diffs)))
    return report(out, "compare", _count(len(args.diffs), "file"))

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
        sub.add_argument("--marts-path", action="append", metavar="PATH",
                         help="directory the framework makes mandatory; repeat for "
                              "more than one (default: %s)" % ", ".join(MARTS))
    return parser

def main(argv=None):
    """Parse, run, and turn anything unexpected into exit code 2."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "marts_path", None) is None:
        args.marts_path = list(MARTS)
    if not args.command:
        parser.print_usage(sys.stderr)
        return 2
    try:
        return {"check": cmd_check, "gate": cmd_gate,
            "compare": cmd_compare}[args.command](args)
    except SlpError as exc:
        sys.stderr.write("ERROR %s\n" % exc)
        return 2
    except Exception as exc:  # fail closed: an unexpected error is never a pass
        sys.stderr.write("ERROR unexpected %s: %s\n" % (type(exc).__name__, exc))
        return 2

if __name__ == "__main__":
    sys.exit(main())
