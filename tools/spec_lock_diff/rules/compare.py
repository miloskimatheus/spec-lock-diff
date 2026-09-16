"""compare: the diff against the pre-registration, and the reconciliation against its tolerance
(README §3 Stage E).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any, NamedTuple

from ..findings import Finding, _count, block, info
from ..gitread import git, inventory
from ..project import Model, Project
from ..readers import schema_errors
from .check import check_prereg_consistency, check_prereg_schema
from .common import _by, _inherited, _moved, apply_rules


# One measured model: the file that carries the numbers, the model they claim to
# be about, whether the pair is sound enough for C1 to C6 to say anything, and
# whether its pre-registration is main's rather than this pull request's.
class Diff(NamedTuple):
    file: str
    name: str
    data: dict[str, Any]
    project: Project
    model: Model | None
    ok: bool
    stale: bool

    @property
    def held(self) -> Model:
        """The model the rules after the contract read; ok is only True when there is one."""
        assert self.model is not None
        return self.model


def stale_preregs(project: Project, base: str, marts: Sequence[str]) -> set[str]:
    """The models whose pre-registration is the one the branch started with.

    README §3 Stage B: a pre-registration belongs to one pull request. After a
    merge it stays in the yml as the record of what was predicted, so the next
    change to that model finds one already there - written for another change,
    against another production. Same merge-base as the gate, so a main that
    moved on does not make an untouched model look pre-registered anew.
    """
    point = git(project.dir, "merge-base", base, "HEAD").strip()
    old = inventory(project.dir, point, False, tuple(marts))["preregs"]
    return set(
        name
        for name, model in project.models.items()
        if isinstance(model.prereg, dict) and _inherited(model.prereg, old.get(name))
    )


def compare_contract(ctx: Diff) -> list[Finding]:
    """README §3 Stage E step 3 — "Each diff number is automatically compared with the intervals
    declared in the pre-registration": both sides have to be readable first, and the
    pre-registration has to be this pull request's.
    """
    out = [
        block(ctx.file, ctx.name, message, "C0")
        for message in schema_errors(ctx.data, "diff", "diff")
    ]
    if ctx.model is None:
        out.append(
            block(
                ctx.file,
                ctx.name,
                "models/ declares no model named %s in this project" % (ctx.name or "?"),
                "C0",
            )
        )
    elif not isinstance(ctx.model.prereg, dict):
        out.append(
            block(
                ctx.file,
                ctx.name,
                "the model has no meta.pre_registration; a number "
                "nobody committed to in advance is not evidence",
                "C0",
            )
        )
    elif ctx.stale:
        out.append(
            block(
                ctx.file,
                ctx.name,
                "the model's meta.pre_registration is the one main "
                "already has; a prediction written for an earlier change is not this "
                "change's, and counts as absent",
                "C0",
            )
        )
    else:
        one = Project(ctx.project.dir, {ctx.name: ctx.model}, [], {})
        out += [
            f._replace(file=ctx.file, rule_id="C0")
            for f in apply_rules([check_prereg_schema, check_prereg_consistency], one)
        ]
    window = ctx.data.get("window")
    if isinstance(window, dict) and not out:
        out.append(
            info(
                ctx.file,
                ctx.name,
                "measured over %s from %s to %s"
                % (window.get("column"), window.get("start"), window.get("end")),
                "C0",
            )
        )
    return out


def compare_rows(ctx: Diff) -> list[Finding]:
    """README §3 Stage E step 3 — "A number is outside the declared interval (e.g., row delta is
    15,000, but the pre-registration said max: 12000)".
    """
    if not ctx.ok:
        return []
    low, high = _ends(ctx.held.prereg["row_delta"])
    value = ctx.data["row_delta"]
    if low <= value <= high:
        return []
    return [
        block(
            ctx.file,
            ctx.name,
            "row_delta is %s, pre-registration allows %s..%s" % (value, low, high),
            "C1",
        )
    ]


def compare_removed_pks(ctx: Diff) -> list[Finding]:
    """README §3 Stage E step 3 — the rows that exist in production and not in the new version
    are a number the pre-registration has to allow.
    """
    if not ctx.ok:
        return []
    most, value = ctx.held.prereg["removed_pks"]["max"], ctx.data["removed_pks"]
    if value <= most:
        return []
    return [
        block(
            ctx.file,
            ctx.name,
            "removed_pks is %s, pre-registration allows at most %s" % (value, most),
            "C2",
        )
    ]


def compare_columns(ctx: Diff) -> list[Finding]:
    """README §3 Stage E step 3 — "A column shows a difference but is not in the
    pre-registration's altered_columns list".
    """
    if not ctx.ok:
        return []
    declared = set(ctx.held.prereg["altered_columns"])
    measured = set(ctx.data["altered_columns"])
    out = [
        block(
            ctx.file,
            ctx.name,
            "column %s changed and is not in pre_registration.altered_columns" % column,
            "C3",
        )
        for column in sorted(measured - declared)
    ]
    out += [
        info(
            ctx.file,
            ctx.name,
            "column %s was pre-registered as altered and did not change" % column,
            "C3",
        )
        for column in sorted(declared - measured)
    ]
    return out


def compare_metrics(ctx: Diff) -> list[Finding]:
    """README §3 Stage E step 3 — each metric of the spec is compared with the interval the
    pre-registration declared for it: its percentage move, or "the value itself" for a model
    production does not have.
    """
    if not ctx.ok:
        return []
    out: list[Finding] = []
    declared, measured = ctx.held.prereg["metrics"], ctx.data["metrics"]
    for name in sorted(declared):
        by = _by(declared[name])
        low, high = _ends(declared[name][by])
        got = (measured.get(name) or {}).get(by)
        if name not in measured or (by == "value" and got is None):
            out.append(
                block(
                    ctx.file,
                    ctx.name,
                    "metric %s was pre-registered by %s and the "
                    "diff does not measure it" % (name, by),
                    "C4",
                )
            )
        elif got is None:
            out.append(
                block(
                    ctx.file,
                    ctx.name,
                    "metric %s cannot be evaluated: the production "
                    "value is 0; a model production does not have is pre-registered by "
                    "value, not by delta_pct" % name,
                    "C4",
                )
            )
        elif not low <= got <= high:
            out.append(
                block(
                    ctx.file,
                    ctx.name,
                    "metric %s %s, pre-registration allows %s..%s"
                    % (name, _moved(by, got), low, high),
                    "C4",
                )
            )
    for name in sorted(set(measured) - set(declared)):
        if measured[name]["delta_pct"] != 0:
            by = (
                "value"
                if measured[name]["delta_pct"] is None and "value" in measured[name]
                else "delta_pct"
            )
            out.append(
                block(
                    ctx.file,
                    ctx.name,
                    "metric %s %s and was not pre-registered"
                    % (name, _moved(by, measured[name][by])),
                    "C4",
                )
            )
    return out


def compare_refactoring(ctx: Diff) -> list[Finding]:
    """README §3 Stage E step 3 — "The type is refactoring but some delta is not zero": the
    schema pins every interval of a refactoring to zero, so C1 to C4 are what block; this
    says in one line what the four of them mean together.
    """
    if not ctx.ok or ctx.held.prereg.get("type") != "refactoring":
        return []
    moved = [
        "row_delta %s" % ctx.data["row_delta"] if ctx.data["row_delta"] else "",
        "removed_pks %s" % ctx.data["removed_pks"] if ctx.data["removed_pks"] else "",
        "altered columns %s" % ", ".join(sorted(ctx.data["altered_columns"]))
        if ctx.data["altered_columns"]
        else "",
    ]
    moved += [
        "metric %s %s percent" % (name, body["delta_pct"])
        for name, body in sorted(ctx.data["metrics"].items())
        if body["delta_pct"]
    ]
    moved = [m for m in moved if m]
    if not moved:
        return []
    return [
        info(
            ctx.file,
            ctx.name,
            "pre-registered as a refactoring, which may not change "
            "any number, and the diff moved: %s" % "; ".join(moved),
            "C5",
        )
    ]


def _ends(interval: Any) -> tuple[float, float]:
    """Both ends of an interval the schema accepted: min and max, present and numbers."""
    return interval["min"], interval["max"]


def _drift(numbers: dict[str, Any]) -> float | None:
    """How far the model is from the source of truth, in percent; None when there is no
    percentage.
    """
    outside = numbers["external_value"]
    return None if outside == 0 else abs(numbers["model_value"] - outside) / abs(outside) * 100


def _band(interval: Any) -> str:
    """The band declared for a number and how wide it is: what Stage E asks the reviewer to
    judge.
    """
    low, high = _ends(interval)
    return "declared %s..%s (a band %s)" % (
        low,
        high,
        "%g wide" % (high - low) if high != low else "that pins it to one value",
    )


def compare_reconciliation(ctx: Diff) -> list[Finding]:
    """README §3 Stage E step 4 — "If the difference is greater than the tolerance, the PR is
    blocked".
    """
    if not ctx.ok:
        return []
    spec = ctx.held.spec if isinstance(ctx.held.spec, dict) else {}
    numbers = ctx.data.get("reconciliation")
    if numbers is None:
        if spec.get("tier") != "critical":
            return []
        return [
            block(
                ctx.file,
                ctx.name,
                "critical model without reconciliation numbers; the "
                "query in the spec runs on full data and its two numbers belong in the "
                "diff",
                "C6",
            )
        ]
    allowed = spec.get("reconciliation_tolerance")
    if not (isinstance(allowed, str) and re.match(r"^[0-9]+(\.[0-9]+)?%$", allowed)):
        return [
            block(
                ctx.file,
                ctx.name,
                "reconciliation numbers given, and the spec declares "
                "no reconciliation_tolerance to read them against",
                "C6",
            )
        ]
    drift = _drift(numbers)
    said = "the model says %s and the source of truth says %s" % (
        numbers["model_value"],
        numbers["external_value"],
    )
    if drift is None:  # nothing to take a percentage of; only an exact match passes
        if numbers["model_value"] == 0:
            return []
        return [
            block(
                ctx.file,
                ctx.name,
                "reconciliation: %s; no percentage makes that difference small" % said,
                "C6",
            )
        ]
    if drift <= float(allowed[:-1]):
        return []
    return [
        block(
            ctx.file,
            ctx.name,
            "reconciliation: %s, a difference of %.4g percent, and "
            "the spec allows %s" % (said, drift, allowed),
            "C6",
        )
    ]


def compare_summary(ctx: Diff) -> list[Finding]:
    """README §3 Stage E step 5 — "Is the pre-registration narrow enough to be able to fail?
    Does the reason justify the interval?": the human is asked to judge the interval, so the
    interval, the reason and the number that landed in it are printed whether or not anything
    blocked.
    """
    if not ctx.ok:
        return []
    pre, data, out = ctx.held.prereg, ctx.data, []

    def say(text: str) -> None:
        out.append(info(ctx.file, ctx.name, text, "I2"))

    say("declared as a %s, because: %s" % (pre["type"], pre["reason"]))
    say("row_delta %s, %s" % (data["row_delta"], _band(pre["row_delta"])))
    say("removed_pks %s, declared at most %s" % (data["removed_pks"], pre["removed_pks"]["max"]))
    for name in sorted(pre["metrics"]):
        by, body = _by(pre["metrics"][name]), data["metrics"].get(name)
        say(
            "metric %s %s, %s"
            % (
                name,
                "was not measured" if body is None else _moved(by, body.get(by)),
                _band(pre["metrics"][name][by]),
            )
        )
    say(
        "altered columns measured [%s], declared [%s]"
        % (", ".join(sorted(data["altered_columns"])), ", ".join(sorted(pre["altered_columns"])))
    )
    numbers = data.get("reconciliation")
    if numbers is not None:
        drift = _drift(numbers)
        say(
            "reconciliation: model %s against source of truth %s, a difference of %s, and the "
            "spec allows %s"
            % (
                numbers["model_value"],
                numbers["external_value"],
                "no percentage" if drift is None else "%.4g percent" % drift,
                (ctx.held.spec or {}).get("reconciliation_tolerance"),
            )
        )
    if not isinstance(data.get("window"), dict):
        say(
            "this diff declares no window; README §3 Stage E step 2 asks for a closed "
            "event_time window identical on both sides, and nothing here can check that"
        )
    return out


# What compare has to say about the run as a whole rather than about one file.
class Run(NamedTuple):
    project: Project
    measured: set[str]
    files: int
    stale: set[str]


def compare_coverage(ctx: Run) -> list[Finding]:
    """README §3 Stage E step 3 — "Each diff number is automatically compared with the intervals
    declared in the pre-registration": every model pre-registered for this pull request, not
    only the ones whose numbers turned up.
    """
    return [
        block(
            ctx.project.models[name].file,
            name,
            "this model has a pre-registration "
            "and no diff.json among the %s read; a number that never arrived was "
            "never compared with anything, and a gate that did not look is not a "
            "gate that passed" % _count(ctx.files, "file"),
            "C7",
        )
        for name in sorted(ctx.project.models)
        if isinstance(ctx.project.models[name].prereg, dict)
        and name not in ctx.measured
        and name not in ctx.stale
    ]
