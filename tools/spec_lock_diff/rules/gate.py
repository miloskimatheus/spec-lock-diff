"""gate: what this branch did to the tests, the spec and the pre-registration (README §2 Control
5B, §3 Stage B).
"""

from __future__ import annotations

import json
import re
from typing import Any

from ..findings import Finding, _count, block, info
from ..gitread import Gate, Inventory, _canon
from ..project import _dirs
from .common import DEAD_KEYS, _inherited, _muted


def _by3(inv: Inventory) -> dict[tuple[str, str, str], dict[str, list[dict[str, Any]]]]:
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
    out: dict[tuple[str, str, str], dict[str, list[dict[str, Any]]]] = {}
    for (model, column, name, args), cfgs in sorted(inv["tests"].items()):
        out.setdefault((model, column, name), {})[args] = cfgs
    return out


def _which(group: dict[str, Any], args: str) -> str:
    """Which of several same-named tests on the same column this one is."""
    if len(group) < 2:
        return ""
    return " (%s)" % ", ".join("%s=%s" % pair for pair in sorted(json.loads(args).items()))


def _on(cfg: dict[str, Any]) -> bool:
    """A test that is switched off asserts nothing."""
    return cfg.get("enabled", True) is True


def _live(bag: list[dict[str, Any]]) -> int:
    """How many declarations in a bag are switched on."""
    return sum(1 for cfg in bag if _on(cfg))


def _named(model: str, column: str) -> str:
    return "%s.%s" % (model, column) if column else model


def _file(ctx: Gate, model: str) -> str:
    """The yml that declares the model now, or the one that declared it before."""
    return ctx.after["where"].get(model) or ctx.before["where"].get(model) or ""


def _in_marts(ctx: Gate, model: str) -> bool:
    """In marts when the yml that declares the model is, or the sql that makes it is."""
    return any(
        (inv[kind].get(model) or "").startswith(_dirs(ctx.marts))
        for inv in (ctx.before, ctx.after)
        for kind in ("where", "sqls")
    )


def _changed(ctx: Gate, kind: str, keys: set[Any] | None = None) -> list[Any]:
    """Keys of one part of the inventory whose value is not the same on both sides."""
    if keys is None:
        keys = set(ctx.before[kind]) | set(ctx.after[kind])
    return sorted(k for k in keys if ctx.before[kind].get(k) != ctx.after[kind].get(k))


def gate_test_removed(ctx: Gate) -> list[Finding]:
    """README §2 Control 5B — "Test removed": an agent can remove a failing test instead of
    fixing the code.
    """
    before, after = _by3(ctx.before), _by3(ctx.after)
    out: list[Finding] = []
    for key in sorted(before):
        model, column, name = key
        said, file = "test '%s' on %s " % (name, _named(model, column)), _file(ctx, model)
        old, new = before[key], after.get(key, {})
        gone = sorted(set(old) - set(new))
        if not new:
            out.append(block(file, model, said + "exists on main but not in this PR", "G1"))
        elif gone:
            out.append(
                block(
                    file,
                    model,
                    said + "changed its arguments%s; if that is intended, "
                    "a human changes it before the agent starts, or in a separate PR"
                    % _which(old, gone[0]),
                    "G1",
                )
            )
        else:
            for args in sorted(old):
                if len(new[args]) < len(old[args]):
                    out.append(
                        block(
                            file,
                            model,
                            said + "was declared %d times on main and %d "
                            "here%s" % (len(old[args]), len(new[args]), _which(old, args)),
                            "G1",
                        )
                    )
                elif _live(new[args]) < _live(old[args]):
                    out.append(block(file, model, said + "was disabled" + _which(old, args), "G1"))
    for path in _changed(ctx, "files", set(ctx.before["files"])):
        out.append(
            block(path, "", "singular or generic test %s was removed or changed" % path, "G1")
        )
    for key in sorted(set(ctx.before["units"]) - set(ctx.after["units"])):
        file, model, _ = ctx.before["units"][key]
        out.append(block(file, model, "unit test '%s' was removed" % key[1], "G1"))
    return out


def gate_test_filter(ctx: Gate) -> list[Finding]:
    """README §2 Control 5B — "WHERE or exclusion clause added to a test": a way to make a test
    pass without fixing the problem.
    """
    out: list[Finding] = []
    before, after = _by3(ctx.before), _by3(ctx.after)
    for key in sorted(set(before) & set(after)):
        for args in sorted(set(before[key]) & set(after[key])):
            old = [cfg.get("where") for cfg in before[key][args]]
            added = set(cfg.get("where") for cfg in after[key][args]) - set(old)
            for new in sorted(where for where in added if where is not None):
                out.append(
                    block(
                        _file(ctx, key[0]),
                        key[0],
                        "test '%s' on %s%s now skips "
                        "rows with where: %s"
                        % (key[2], _named(key[0], key[1]), _which(after[key], args), new),
                        "G2",
                    )
                )
    return out


def _sev(cfg: dict[str, Any]) -> str:
    """The severity dbt will use: error unless the test says otherwise."""
    return str(cfg.get("severity", "error")).lower()


def gate_test_severity(ctx: Gate) -> list[Finding]:
    """README §2 Control 5B — "severity downgraded (e.g., error → warn)" and "a test added that
    cannot fail": a test that reports a pass whatever the data does is not a test, whether
    this branch made it that way or wrote it that way.
    """
    out: list[Finding] = []
    before, after = _by3(ctx.before), _by3(ctx.after)
    for key in sorted(after):
        for args in sorted(after[key]):
            was = before.get(key, {}).get(args, [])
            said = "test '%s' on %s%s " % (key[2], _named(key[0], key[1]), _which(after[key], args))
            file = _file(ctx, key[0])
            # Every declaration this branch did not inherit unchanged, held
            # against the bag of declarations it could have come from.
            for new in [cfg for cfg in after[key][args] if cfg not in was]:
                if not was:  # born this way, and every reason it cannot fail counts
                    why = _muted(new, DEAD_KEYS)
                    if why:
                        out.append(
                            block(
                                file,
                                key[0],
                                said + "is new and cannot fail the build: %s" % why,
                                "G3",
                            )
                        )
                    continue
                if _sev(new) == "warn" and not any(_sev(cfg) == "warn" for cfg in was):
                    out.append(
                        block(
                            file,
                            key[0],
                            said + "was downgraded from error to warn, so it cannot block",
                            "G3",
                        )
                    )
                for name in DEAD_KEYS:
                    if name in new and not any(cfg.get(name) == new[name] for cfg in was):
                        out.append(
                            block(
                                file,
                                key[0],
                                said + "sets %s, which changes what counts as failing" % name,
                                "G3",
                            )
                        )
    return out


def gate_test_narrowed(ctx: Gate) -> list[Finding]:
    """README §2 Control 5B — "WHERE or exclusion clause added to a test": a test this branch
    adds has no earlier self to be weaker than, and still asserts nothing about the rows its
    filter removes. Whether those are rows that cannot fail or rows that would have is a
    reading, so this one is shown and not blocked.
    """
    out: list[Finding] = []
    before, after = _by3(ctx.before), _by3(ctx.after)
    for key in sorted(after):
        for args in sorted(after[key]):
            if before.get(key, {}).get(args):
                continue
            out += [
                info(
                    _file(ctx, key[0]),
                    key[0],
                    "test '%s' on %s is new and skips rows "
                    "with where: %s" % (key[2], _named(key[0], key[1]), cfg["where"]),
                    "I3",
                )
                for cfg in after[key][args]
                if cfg.get("where") is not None
            ]
    return out


def gate_unit_test_changed(ctx: Gate) -> list[Finding]:
    """README §2 Control 5B — "expect value changed in an existing test": if the agent changes
    the expected result, any result becomes correct.
    """
    out: list[Finding] = []
    for key in sorted(set(ctx.before["units"]) & set(ctx.after["units"])):
        file, model, body = ctx.after["units"][key]
        if ctx.before["units"][key][2] != body:
            out.append(
                block(
                    file,
                    model,
                    "unit test '%s' was changed; the rows it is "
                    "given and the rows it expects are the question and the answer, "
                    "and this PR wrote both" % key[1],
                    "G4",
                )
            )
    return out


def gate_recon_with_model(ctx: Gate) -> list[Finding]:
    """README §2 Control 5B — "analyses/reconciliation_* changed in the same PR as the model":
    like a student writing the exam and the answer key.
    """
    out: list[Finding] = []
    moved = set(_changed(ctx, "recons"))
    for model in sorted(ctx.after["specs"]):
        spec = ctx.after["specs"][model]
        query = spec.get("reconciliation_query") if isinstance(spec, dict) else None
        if query in moved and ctx.before["models"].get(model) != ctx.after["models"].get(model):
            out.append(
                block(
                    str(query),
                    model,
                    "%s changed in the same PR as the model it checks; "
                    "a human changes the reconciliation, in its own PR" % query,
                    "G5",
                )
            )
    return out


def gate_packages(ctx: Gate) -> list[Finding]:
    """README §2 Control 5B — "Package pin changed": changing dependency versions can introduce
    different behaviors.
    """
    return [
        block(
            path,
            "",
            "%s changed on this branch; the versions the project builds with "
            "are a human decision" % path,
            "G6",
        )
        for path in _changed(ctx, "packages")
    ]


def gate_protected_paths(ctx: Gate) -> list[Finding]:
    """README §2 Control 5A — "Certain files and directories must be protected so that only
    humans can modify them"; §3 Stage C Rule 8 — "Do not edit protected paths".
    """
    out = [
        block(
            path,
            "",
            "%s changed on this branch; it is a protected path, and Rule 8 says "
            "the agent stops and asks a human, who changes it in a pull request of their "
            "own" % path,
            "G9",
        )
        for path in _changed(ctx, "protected")
    ]
    for path in sorted(set(ctx.after["files"]) - set(ctx.before["files"])):
        if path.startswith("tests/generic/"):
            out.append(
                block(
                    path,
                    "",
                    "%s is a new generic test definition; one that carries "
                    "the name of a test in use replaces that test everywhere it is "
                    "declared, with no test file changing, and a human writes those" % path,
                    "G9",
                )
            )
    return out


# The config() a singular test carries in its own sql, as `key=value` pairs.
_CONFIG = re.compile(r"config\s*\((.*?)\)\s*}}", re.S)


def _muted_sql(text: str) -> str:
    """Why a singular test cannot fail the build, read from its own config(), or "" when it can."""
    cfg: dict[str, Any] = {}
    for body in _CONFIG.findall(text):
        for key, value in re.findall(r"(\w+)\s*=\s*([^,\s)]+)", body):
            cfg[key] = value.strip("'\"")
    if str(cfg.get("enabled", "true")).lower() != "true":
        cfg["enabled"] = False
    return _muted(cfg, DEAD_KEYS)


def gate_singular_born_muted(ctx: Gate) -> list[Finding]:
    """README §2 Control 5B — "A test added that cannot fail": a singular test under tests/
    carries its config in its own sql, where the rules that read the yml cannot see it.
    """
    return [
        block(
            path, "", "%s is a new singular test and cannot fail the build: %s" % (path, why), "G10"
        )
        for path in sorted(set(ctx.after["singular"]) - set(ctx.before["singular"]))
        for why in [_muted_sql(ctx.after["singular"][path])]
        if why
    ]


def gate_spec_changed(ctx: Gate) -> list[Finding]:
    """README §1 Principle 1 — "The human decides before, by writing the spec"; README §3 Stage
    A — the six fields are read and approved before any line of code is written.
    """
    out: list[Finding] = []
    for model in sorted(ctx.after["specs"]):
        spec = ctx.after["specs"][model]
        if spec is None or not _in_marts(ctx, model):
            continue
        first = next(
            (inv["specs"][model] for inv in ctx.walk if inv["specs"].get(model) is not None), None
        )
        if first is not None and _canon(first) != _canon(spec):
            out.append(
                block(
                    _file(ctx, model),
                    model,
                    "meta.spec changed after it was first "
                    "written on this branch; the spec is the human's decision, and a "
                    "human changes it in a separate PR",
                    "G7",
                )
            )
    return out


def gate_spec_first_written(ctx: Gate) -> list[Finding]:
    """README §3 Stage A — "the 6 fields must be read and approved by the human before any line
    of code is written": a spec that was not on main was written on this branch, and the
    Author is told where, because nothing in git can say by whom it was approved.
    """
    out: list[Finding] = []
    for model in sorted(ctx.after["specs"]):
        if (
            ctx.after["specs"][model] is None
            or ctx.before["specs"].get(model) is not None
            or not _in_marts(ctx, model)
        ):
            continue
        at = next(i for i, inv in enumerate(ctx.walk) if inv["specs"].get(model) is not None)
        out.append(
            info(
                _file(ctx, model),
                model,
                "meta.spec was first written on this branch, "
                "in commit %s; the framework asks the Author to have read and approved "
                "its six fields before any line of code, and only the Author can say "
                "whether that happened" % ctx.commits[at],
                "I4",
            )
        )
    return out


def gate_prereg_present(ctx: Gate) -> list[Finding]:
    """README §3 Stage C — "Cannot start without a valid pre-registration"; Stage B — the agent
    declares the numerical changes it expects "before writing any code", and a
    pre-registration "belongs to one pull request".
    """
    out: list[Finding] = []
    for model in sorted(ctx.after["code"]):
        if ctx.before["code"].get(model) == ctx.after["code"][model]:
            continue
        if model not in ctx.after["where"] or not _in_marts(ctx, model):
            continue
        now, then = ctx.after["preregs"].get(model), ctx.before["preregs"].get(model)
        said = "the sql of this model changed on this branch and "
        if now is None:
            out.append(
                block(
                    _file(ctx, model),
                    model,
                    said + "it carries no "
                    "meta.pre_registration; nothing downstream has an interval to hold "
                    "its numbers against, and compare will not so much as look at it",
                    "G8",
                )
            )
        elif _inherited(now, then):
            out.append(
                block(
                    _file(ctx, model),
                    model,
                    said + "its meta.pre_registration is "
                    "the one main already has; a prediction written for an earlier "
                    "change is not this change's, and counts as absent",
                    "G8",
                )
            )
    return out


def gate_prereg_counter(ctx: Gate) -> list[Finding]:
    """README §3 Stage B — "a change counter is incremented in the PR (visible to the Author in
    review)"; a pre-registration "belongs to one pull request", so replacing the one main had
    is where this PR's count starts.
    """
    out: list[Finding] = []
    for model in sorted(ctx.after["preregs"]):
        if ctx.after["preregs"][model] is None:
            continue
        seen: str | None = None
        edits = 0
        for inv in ctx.walk:  # the commit it first differs from main's in is not an edit
            current = inv["preregs"].get(model)
            if current is None or _inherited(current, ctx.before["preregs"].get(model)):
                continue
            if seen is not None and _canon(current) != seen:
                edits += 1
            seen = _canon(current)
        if edits:
            out.append(
                info(
                    _file(ctx, model),
                    model,
                    "pre-registration was modified %s after "
                    "it was first written" % _count(edits, "time"),
                    "I1",
                )
            )
    return out
