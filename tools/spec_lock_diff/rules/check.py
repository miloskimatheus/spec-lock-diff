"""check: the spec, the pre-registration and the primary key test of every marts model (README
§3 Stage A, B; §2 Rule 2).
"""

from __future__ import annotations

import json

from ..findings import Finding, block
from ..owners import CODEOWNERS_FILES, _incremental, _owner_rules, _owners
from ..project import Project
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
