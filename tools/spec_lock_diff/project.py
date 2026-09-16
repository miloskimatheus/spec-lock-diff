"""A dbt project as its yml declares it: models, columns, tests and unit tests, read once."""

from __future__ import annotations

import json
import pathlib
import re
from collections.abc import Sequence
from typing import Any, NamedTuple

from .findings import SlpError
from .readers import load_yaml

# Where the models the framework makes mandatory live (README §3 Stage A: "In all
# models within models/marts/**"). A project that keeps them elsewhere says so
# with --marts-path, because a tool pointed at the wrong folder finds nothing
# wrong with anything, and that reads exactly like a pass.
MARTS = ("models/marts",)

# Keys that say how a test runs rather than what it asserts. They are kept apart
# from the test arguments because gate rules read them (G2 where, G3 severity).
CFG_KEYS = (
    "enabled",
    "error_if",
    "fail_calc",
    "limit",
    "severity",
    "store_failures",
    "warn_if",
    "where",
)

# Keys that say neither what a test asserts nor whether it can fail: a label,
# a sentence for the docs, where to keep the failing rows. They are read so
# that adding one is not "changed its arguments", and no rule compares them.
INERT_KEYS = (
    "tags",
    "meta",
    "description",
    "name",
    "store_failures_as",
    "schema",
    "database",
    "alias",
    "group",
    "docs",
)


# One dbt model as its yml declares it. In tests, the column "" means model level.
# One data test as the yml declares it: column ("" at model level), name, arguments, config.
Test = tuple[str, str, str, dict[str, Any]]


class Model(NamedTuple):
    name: str
    file: str
    entry: dict[str, Any]
    spec: Any
    prereg: Any
    columns: list[str]
    sensitive: list[str]
    tests: list[Test]
    is_marts: bool


# One entry of unit_tests:, kept whole because G4 compares the whole body.
class UnitTest(NamedTuple):
    name: str
    model: str
    file: str
    body: dict[str, Any]


# Everything the check rules need from a dbt project, read once.
class Project(NamedTuple):
    dir: pathlib.Path
    models: dict[str, Model]
    unit_tests: list[UnitTest]
    files: dict[str, str]


def _entries(value: Any, what: str, where: str) -> list[dict[str, Any]]:
    """A yml list of mappings, or nothing. Anything else cannot be read, so it errors."""
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(v, dict) for v in value):
        raise SlpError("%s in %s must be a list of entries" % (what, where))
    return value


def _one_of(entry: dict[str, Any], key: str, where: str) -> Any:
    """entry.meta.<key> or entry.config.meta.<key>; both present is ambiguous."""
    meta, config = entry.get("meta"), entry.get("config")
    meta = meta if isinstance(meta, dict) else {}
    config = config if isinstance(config, dict) else {}
    nested = config.get("meta")
    nested = nested if isinstance(nested, dict) else {}
    if meta.get(key) is not None and nested.get(key) is not None:
        raise SlpError("ambiguous: %s defined twice (meta and config.meta) in %s" % (key, where))
    return meta.get(key) if meta.get(key) is not None else nested.get(key)


def _test_items(entry: dict[str, Any], where: str) -> list[Any]:
    """The tests: or data_tests: list of a model or column; both keys is ambiguous."""
    classic, modern = entry.get("tests"), entry.get("data_tests")
    if classic is not None and modern is not None:
        raise SlpError("ambiguous: tests defined twice (tests and data_tests) in %s" % where)
    items = classic if classic is not None else modern
    if items is not None and not isinstance(items, list):
        raise SlpError("tests in %s must be a list" % where)
    return items or []


def normalize_test(item: Any, where: str) -> tuple[str, str, dict[str, Any]]:
    """One test as (name, arguments, config): what it asserts apart from how it runs."""
    name: Any = None
    body: Any = None
    if isinstance(item, str):
        name, body = item, {}
    elif isinstance(item, dict) and len(item) == 1:
        name, body = list(item.items())[0]
        body = {} if body is None else body
    if not isinstance(name, str) or not isinstance(body, dict):
        raise SlpError("cannot read a test in %s: %r" % (where, item))
    # dbt 1.10 moved the arguments under `arguments:`; the older form writes them
    # on the test. Both are one test, so moving them is not a change, and both
    # at once is not a preference the tool guesses.
    args: dict[str, Any] = {}
    cfg: dict[str, Any] = {}
    nested = body.get("arguments")
    if nested is not None and not isinstance(nested, dict):
        raise SlpError(
            "cannot read a test in %s: arguments of %s must be a mapping" % (where, name)
        )
    for key, value in body.items():
        if key == "arguments":
            continue
        pairs = value.items() if key == "config" and isinstance(value, dict) else [(key, value)]
        for name_, value_ in pairs:
            holder = cfg if name_ in CFG_KEYS + INERT_KEYS else args
            if name_ in holder:
                raise SlpError(
                    "ambiguous: %s of test %s in %s is given twice (on the test "
                    "and under config)" % (name_, name, where)
                )
            holder[name_] = value_
    if nested and args:
        raise SlpError(
            "ambiguous: test %s in %s gives arguments both on the test and under "
            "arguments" % (name, where)
        )
    args.update(nested or {})
    return name, json.dumps(args, sort_keys=True, default=str), cfg


def _read_columns(entry: dict[str, Any], where: str) -> tuple[list[str], list[str], list[Test]]:
    """The columns of one model entry: their names, the sensitive ones, and the tests on each."""
    columns: list[str] = []
    sensitive: list[str] = []
    tests: list[Test] = []
    for column in _entries(entry.get("columns"), "columns", where):
        cname = column.get("name")
        if not isinstance(cname, str) or not cname:
            raise SlpError("a column without a name in %s" % where)
        columns.append(cname)
        if _one_of(column, "sensitive", "%s.%s" % (where, cname)) is True:
            sensitive.append(cname)
        for item in _test_items(column, "%s.%s" % (where, cname)):
            tests.append((cname,) + normalize_test(item, where))
    return columns, sensitive, tests


def read_doc(
    doc: Any, rel: str, marts: Sequence[str] = MARTS
) -> tuple[list[Model], list[UnitTest]]:
    """The models and unit tests declared in one yml document, on disk or at a commit."""
    if not isinstance(doc, dict):
        raise SlpError("%s is not a yml mapping" % rel)
    models: list[Model] = []
    units: list[UnitTest] = []
    for entry in _entries(doc.get("models"), "models", rel):
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            raise SlpError("a model without a name in %s" % rel)
        where = "%s (%s)" % (name, rel)
        tests = [("",) + normalize_test(item, where) for item in _test_items(entry, where)]
        columns, sensitive, more = _read_columns(entry, where)
        tests += more
        models.append(
            Model(
                name,
                rel,
                entry,
                _one_of(entry, "spec", where),
                _one_of(entry, "pre_registration", where),
                columns,
                sensitive,
                tests,
                rel.startswith(_dirs(marts)),
            )
        )
    for entry in _entries(doc.get("unit_tests"), "unit_tests", rel):
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            raise SlpError("a unit test without a name in %s" % rel)
        units.append(UnitTest(name, entry.get("model") or "", rel, entry))
    return models, units


def _dirs(marts: Sequence[str], top: bool = False) -> tuple[str, ...]:
    """The marts paths as prefixes, or the directories that hold them - where yml is read from.

    A leading ./ is a path to a shell and to pathlib, and nothing at all to git,
    whose paths never start with one. Left in, --marts-path ./models/marts made
    check read the right folder and gate match no file at all: one flag value,
    two verdicts, and the one that printed OK had looked at nothing.
    """
    paths = tuple(re.sub(r"^(?:\./)+", "", p).strip("/") + "/" for p in marts)
    return tuple(sorted(set(p.split("/")[0] + "/" for p in paths))) if top else paths


def read_project(project_dir: str | pathlib.Path, marts: Sequence[str] = MARTS) -> Project:
    """Read the model yml into models and unit tests. No git, no dbt, no warehouse."""
    root = pathlib.Path(project_dir).resolve()
    for folder in _dirs(marts):
        if not (root / folder).is_dir():
            raise SlpError(
                "%s not found under %s; nothing to check is not OK" % (folder, project_dir)
            )
    models: dict[str, Model] = {}
    units: list[UnitTest] = []
    files: dict[str, str] = {}
    for path in sorted(
        p for top in _dirs(marts) for p in (root / top).rglob("*.sql") if p.is_file()
    ):
        files[path.stem] = path.relative_to(root).as_posix()
    for path in sorted(
        p
        for top in _dirs(marts, True)
        for p in (root / top).rglob("*")
        if p.suffix in (".yml", ".yaml") and p.is_file()
    ):
        rel = path.relative_to(root).as_posix()
        found, unit_tests = read_doc(load_yaml(path), rel, marts)
        for model in found:
            if model.name in models:
                raise SlpError(
                    "model %s is declared twice: %s and %s"
                    % (model.name, models[model.name].file, model.file)
                )
            models[model.name] = model
        units.extend(unit_tests)
    # A model is in marts when the sql that makes it is, wherever its yml sits: a
    # project that documents everything in one models/schema.yml is ordinary dbt,
    # and reading only the yml path would exempt every one of those models.
    for name in set(files) & set(models):
        models[name] = models[name]._replace(is_marts=True)
    return Project(root, models, units, files)
