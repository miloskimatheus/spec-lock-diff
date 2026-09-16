"""check: the spec, the pre-registration and the primary key test of every marts model (README
§3 Stage A, B; §2 Rule 2).
"""

from __future__ import annotations

import json
import re
from typing import Any

from ..findings import Finding, block, info
from ..owners import CODEOWNERS_FILES, _incremental, _owner_rules, _owners
from ..project import Model, Project, UnitTest
from ..readers import schema_errors
from .common import _blocks, _by, _interval, _muted, _sorted_models, _strings


def check_spec_present(project: Project) -> list[Finding]:
    """README §3 Stage A — "PR cannot advance without a completed spec"; Rule 1: no spec, stop
    and ask.
    """
    return [
        block(m.file, m.name, "model has no meta.spec (README §3 Stage A)", "S1")
        for m in _sorted_models(project)
        if m.is_marts and m.spec is None
    ]


def check_model_declared(project: Project) -> list[Finding]:
    """README §3 Stage A — "PR cannot advance without a completed spec": a model no yml declares
    has no spec, and nothing here can ask it for one.
    """
    return [
        block(
            project.files[name],
            name,
            "no yml declares this model; an undeclared "
            "model has no spec, no primary key and no test, and every other rule "
            "here would pass it in silence",
            "S4",
        )
        for name in sorted(set(project.files) - set(project.models))
    ]


def check_spec_schema(project: Project) -> list[Finding]:
    """README §3 Stage A — the six mandatory fields and their format, as
    schemas/spec.schema.json.
    """
    return [
        block(m.file, m.name, message, "S2")
        for m in _sorted_models(project)
        if m.spec is not None
        for message in schema_errors(m.spec, "spec", "spec")
    ]


def check_spec_consistency(project: Project) -> list[Finding]:
    """README §3 Stage A — the spec names columns of this model and a query that exists."""
    out: list[Finding] = []
    for model in _sorted_models(project):
        spec = model.spec if isinstance(model.spec, dict) else {}
        keys = _strings(spec.get("primary_key"))
        if keys and not model.columns:
            out.append(
                block(
                    model.file,
                    model.name,
                    "cannot verify primary_key: model declares no columns",
                    "S3",
                )
            )
        elif keys:
            out += [
                block(
                    model.file,
                    model.name,
                    "spec.primary_key names %s, which the "
                    "model does not declare as a column" % column,
                    "S3",
                )
                for column in keys
                if column not in model.columns
            ]
        listed = _strings(spec.get("sensitive_columns"))
        if listed is not None:
            for column in sorted(set(listed) - set(model.sensitive)):
                why = (
                    "the model does not declare that column"
                    if column not in model.columns
                    else "that column is not marked meta.sensitive: true"
                )
                out.append(
                    block(
                        model.file,
                        model.name,
                        "spec.sensitive_columns names %s, but %s" % (column, why),
                        "S3",
                    )
                )
            out += [
                block(
                    model.file,
                    model.name,
                    "column %s is marked meta.sensitive: true "
                    "but is not in spec.sensitive_columns" % column,
                    "S3",
                )
                for column in sorted(set(model.sensitive) - set(listed))
            ]
        query = spec.get("reconciliation_query")
        if (
            spec.get("tier") == "critical"
            and isinstance(query, str)
            and not (project.dir / query).is_file()
        ):
            out.append(
                block(
                    model.file,
                    model.name,
                    "spec.reconciliation_query points at %s, which does not exist" % query,
                    "S3",
                )
            )
    return out


def check_owned(project: Project) -> list[Finding]:
    """README §3 Stage E — "Critical model: a Partner (≠ Author) approves. CODEOWNERS enforces
    this"; §2 Control 5A — "Incremental models (list explicitly)".
    """
    rules, out = _owner_rules(project.dir), []
    for model in _sorted_models(project):
        spec = model.spec if isinstance(model.spec, dict) else {}
        sql = project.files.get(model.name)
        kind = (
            "critical"
            if model.is_marts and spec.get("tier") == "critical"
            else "incremental"
            if _incremental(model, project.dir / sql if sql else None)
            else ""
        )
        if not kind:
            continue
        asks = (
            "a Partner approves a critical model, and CODEOWNERS is what enforces it "
            "(README §3 Stage E)"
            if kind == "critical"
            else "README §2 Control 5A asks for incremental models to be listed explicitly"
        )
        if rules is None:
            out.append(
                block(
                    model.file,
                    model.name,
                    "%s model, and this repository has no "
                    "CODEOWNERS file (%s); %s" % (kind, ", ".join(CODEOWNERS_FILES), asks),
                    "S5",
                )
            )
            continue
        out += [
            block(
                path,
                model.name,
                "%s model, and no line of CODEOWNERS owns %s; %s" % (kind, path, asks),
                "S5",
            )
            for path in sorted(set(p for p in (sql, model.file) if p))
            if not _owners(rules, path)
        ]
    return out


def check_prereg_schema(project: Project) -> list[Finding]:
    """README §3 Stage B — the pre-registration format, as schemas/pre_registration.schema.json."""
    return [
        block(m.file, m.name, message, "P1")
        for m in _sorted_models(project)
        if m.prereg is not None
        for message in schema_errors(m.prereg, "pre_registration", "pre_registration")
    ]


def check_prereg_consistency(project: Project) -> list[Finding]:
    """README §3 Stage B — Rule 6: the intervals are closed, and the metrics are the spec's."""
    out: list[Finding] = []
    for model in _sorted_models(project):
        prereg = model.prereg if isinstance(model.prereg, dict) else None
        if prereg is None:
            continue
        if not isinstance(model.spec, dict):
            out.append(
                block(
                    model.file,
                    model.name,
                    "pre-registration without a spec: the spec is what the diff compares against",
                    "P2",
                )
            )
            continue
        metrics, defined = prereg.get("metrics"), model.spec.get("metrics")
        declared = metrics if isinstance(metrics, dict) else {}
        wanted = defined if isinstance(defined, dict) else {}
        intervals = [("row_delta", _interval(prereg.get("row_delta")))]
        intervals += [
            ("metrics.%s.%s" % (name, _by(body)), _interval(body.get(_by(body))))
            for name, body in sorted(declared.items())
            if isinstance(body, dict)
        ]
        for name, ends in intervals:
            if ends and ends[0] > ends[1]:
                out.append(
                    block(
                        model.file,
                        model.name,
                        "pre_registration.%s has min %s, "
                        "which is above max %s" % (name, ends[0], ends[1]),
                        "P2",
                    )
                )
        out += [
            block(
                model.file,
                model.name,
                "pre_registration.metrics declares %s, which spec.metrics does not define" % name,
                "P2",
            )
            for name in sorted(set(declared) - set(wanted))
        ]
        out += [
            block(
                model.file,
                model.name,
                "spec.metrics defines %s, which "
                "pre_registration.metrics declares no interval for" % name,
                "P2",
            )
            for name in sorted(set(wanted) - set(declared))
        ]
        out += [
            block(
                model.file,
                model.name,
                "pre_registration.altered_columns names %s, "
                "which the model does not declare as a column" % column,
                "P2",
            )
            for column in _strings(prereg.get("altered_columns")) or []
            if column not in model.columns
        ]
    return out


def check_pk_test(project: Project) -> list[Finding]:
    """README §2 Rule 2 — "The agent creates a uniqueness test on the spec's primary_key"."""
    # The forms of uniqueness test this rule accepts. To accept another one, add
    # its name here and add a passing fixture under tests/fixtures/check/.
    ACCEPTED_PK_TESTS = (
        "unique",
        "unique_combination_of_columns",
        "dbt_utils.unique_combination_of_columns",
    )
    out: list[Finding] = []
    for model in _sorted_models(project):
        spec = model.spec if isinstance(model.spec, dict) else {}
        keys = _strings(spec.get("primary_key")) if model.is_marts else None
        if not keys:
            continue
        covered, muted = False, ""
        for column, name, args, cfg in model.tests:
            if name not in ACCEPTED_PK_TESTS:
                continue
            given = json.loads(args)  # a model-level `unique` names its column as an argument
            if not (
                [column or given.get("column_name")] == keys
                if name == "unique"
                else set(_strings(given.get("combination_of_columns")) or []) == set(keys)
            ):
                continue
            covered, muted = covered or _blocks(cfg), muted or _muted(cfg)
        if covered:
            continue
        out.append(
            block(
                model.file,
                model.name,
                "the uniqueness test on primary key [%s] cannot fail the build: %s"
                % (", ".join(keys), muted)
                if muted
                else "no uniqueness test on primary key [%s]; accepted forms: %s"
                % (", ".join(keys), ", ".join(ACCEPTED_PK_TESTS)),
                "T1",
            )
        )
    return out


# --- check: each edge is a unit test, and a unit test mocks every input (README §3 C, Rule 2) ---

_QUOTED = re.compile(r"""['"]([^'"]*)['"]""")


def _inputs(text: str) -> set[str]:
    """Every ref() and source() in a sql, or in a unit test's input, as dbt spells them.

    Comments are left out. A ref is named by its last quoted argument, so
    ref('pkg', 'model') and ref('model', v=2) both read as ref('model'). A ref
    built by a macro or a variable has no quoted name and is not seen.
    """
    text = re.sub(r"\{#.*?#\}|/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r"--[^\n]*", " ", text)
    found = set()
    for kind, args in re.findall(r"\b(ref|source)\(([^()]*)\)", text):
        names = _QUOTED.findall(args)
        if kind == "ref" and names:
            found.add("ref('%s')" % names[-1])
        if kind == "source" and len(names) >= 2:
            found.add("source('%s', '%s')" % (names[0], names[1]))
    return found


def _edge(unit: UnitTest) -> str | None:
    """The edge a unit test names in config.meta.edge, with its spacing normalised, or None."""
    config = unit.body.get("config")
    meta = config.get("meta") if isinstance(config, dict) else None
    edge = meta.get("edge") if isinstance(meta, dict) else None
    return " ".join(str(edge).split()) if edge is not None else None


def _units_of(project: Project, model: Model) -> list[UnitTest]:
    """The unit tests declared for one model, in the order the yml files were read."""
    return [unit for unit in project.unit_tests if unit.model == model.name]


def _edges_of(model: Model) -> list[str] | None:
    """The known edges of a marts model's spec, or None when there is nothing to hold it to."""
    spec = model.spec if isinstance(model.spec, dict) else {}
    return _strings(spec.get("known_edges")) if model.is_marts else None


def check_edges_tested(project: Project) -> list[Finding]:
    """README §3 Stage C Rule 2 — each spec edge becomes a unit test "that names its edge
    verbatim in config.meta.edge"."""
    out: list[Finding] = []
    for model in _sorted_models(project):
        edges = _edges_of(model)
        if edges is None:
            continue
        wanted = {" ".join(edge.split()): edge for edge in edges}
        named = {_edge(unit) for unit in _units_of(project, model)}
        out += [
            block(
                model.file,
                model.name,
                "no unit test names the edge '%s' in config.meta.edge; each edge becomes a unit "
                "test, and the name is what lets a machine tell which (README §3 Stage C Rule 2)"
                % edge,
                "T2",
            )
            for key, edge in wanted.items()
            if key not in named
        ]
        for unit in _units_of(project, model):
            claim = _edge(unit)
            if claim is not None and claim not in wanted:
                out.append(
                    block(
                        unit.file,
                        model.name,
                        "unit test '%s' names an edge the spec does not have: '%s'"
                        % (unit.name, claim),
                        "T2",
                    )
                )
    return out


def check_inputs_mocked(project: Project) -> list[Finding]:
    """README §3 Stage C Rule 2 — a unit test "mocks in given every ref and source the model
    reads"."""
    out: list[Finding] = []
    for model in _sorted_models(project):
        sql = project.files.get(model.name)
        if not model.is_marts or sql is None:
            continue
        reads = _inputs((project.dir / sql).read_text(encoding="utf-8", errors="replace"))
        for unit in _units_of(project, model):
            given = unit.body.get("given")
            mocked: set[str] = set()
            for item in given if isinstance(given, list) else []:
                mocked |= _inputs(str(item.get("input", ""))) if isinstance(item, dict) else set()
            out += [
                block(
                    unit.file,
                    model.name,
                    "unit test '%s' has no given rows for %s, which the model reads; dbt has "
                    "nothing to mock it with, and a unit test that reads a relation is not a "
                    "unit test (README §3 Stage C Rule 2)" % (unit.name, missing),
                    "T3",
                )
                for missing in sorted(reads - mocked)
            ]
    return out


def _rows(value: Any) -> str:
    """How many rows a given or an expect holds, as the yml carries them; ? for a fixture file."""
    if isinstance(value, list):
        return str(len(value))
    if isinstance(value, str):  # csv, with a header line
        return str(max(0, len([line for line in value.splitlines() if line.strip()]) - 1))
    return "?"


def check_edge_readout(project: Project) -> list[Finding]:
    """README §3 Stage E step 5 — "CI prints one line per edge of the spec: the unit test that
    names it, and how many rows it is given and expects"."""
    out: list[Finding] = []
    for model in _sorted_models(project):
        edges = _edges_of(model) or []
        wanted = {" ".join(edge.split()) for edge in edges}
        for unit in _units_of(project, model):
            claim = _edge(unit)
            if claim not in wanted:
                continue
            given, expect = unit.body.get("given"), unit.body.get("expect")
            rows = (
                [_rows(item.get("rows")) for item in given if isinstance(item, dict)]
                if isinstance(given, list)
                else []
            )
            out.append(
                info(
                    unit.file,
                    model.name,
                    "edge '%s' is proven by unit test '%s', given %s rows and expecting %s; the "
                    "third reading of Stage E asks whether the expect says what the edge says"
                    % (
                        claim,
                        unit.name,
                        " + ".join(rows) or "no",
                        _rows(expect.get("rows") if isinstance(expect, dict) else None),
                    ),
                    "I5",
                )
            )
    return out
