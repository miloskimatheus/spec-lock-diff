"""What more than one rule module needs: the model order, intervals, the mute predicate, and
applying rules.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from ..findings import Finding
from ..gitread import _canon
from ..project import Model, Project


def _sorted_models(project: Project) -> list[Model]:
    """Models by name, so the output never depends on the order the files were read."""
    return [project.models[name] for name in sorted(project.models)]


def _strings(value: Any) -> list[str] | None:
    """A yml list of strings, or None when it is something the schema rule already blocked."""
    return value if isinstance(value, list) and all(isinstance(v, str) for v in value) else None


def _interval(value: Any) -> tuple[float, float] | None:
    """(min, max) when both ends are numbers, else None: the schema rule already blocked it."""
    if (
        isinstance(value, dict)
        and isinstance(value.get("min"), (int, float))
        and isinstance(value.get("max"), (int, float))
    ):
        return value["min"], value["max"]
    return None


def _by(body: Any) -> str:
    """How a metric is pre-registered: by the value itself, for a model production does not
    have, or by its percentage move.
    """
    return "value" if isinstance(body, dict) and "value" in body else "delta_pct"


def _moved(by: str, got: Any) -> str:
    """One metric's measurement in words: what it is, or how far it moved."""
    if by == "value":
        return "was not measured" if got is None else "is %s" % got
    if got is None:
        return "moved by a percentage that cannot be evaluated, because the production value is 0"
    return "moved %s percent" % got


# Config keys that stop a test from failing even while it is enabled and severe:
# a threshold it never reaches, or rows it never looks at. dbt runs the test
# either way and reports a pass. DEAD_KEYS are the ones that can only ever mute;
# a `where` is the one that might instead be honest scoping, so it is held apart
# - T1 refuses it on the one test the framework makes mandatory, and I3 shows it
# to the human on every test a branch adds.
DEAD_KEYS = ("error_if", "warn_if", "fail_calc", "limit")

MUTE_KEYS = ("where",) + DEAD_KEYS


def _muted(cfg: dict[str, Any], keys: tuple[str, ...] = MUTE_KEYS) -> str:
    """Why a test cannot fail the build, in one clause, or "" when it can."""
    if cfg.get("enabled", True) is not True:
        return "it is disabled"
    if str(cfg.get("severity", "error")).lower() != "error":
        return "its severity is %s" % cfg.get("severity")
    narrowed = [key for key in keys if key in cfg]
    return "it sets %s" % ", ".join(narrowed) if narrowed else ""


def _blocks(cfg: dict[str, Any]) -> bool:
    """A test only counts when it can fail the build."""
    return not _muted(cfg)


def _inherited(now: Any, then: Any) -> bool:
    """A pre-registration identical to the one at the merge-base: main's prediction, not this
    PR's.
    """
    return now is not None and then is not None and _canon(now) == _canon(then)


def apply_rules(rules: Sequence[Callable[[Any], list[Finding]]], context: Any) -> list[Finding]:
    """Run every rule in order and collect what they found."""
    return [finding for rule in rules for finding in rule(context)]
