"""What a rule says, and how a run ends: findings, their lines, the summary and the exit code."""

from __future__ import annotations

from typing import NamedTuple


class SlpError(Exception):
    """Anything that stops the tool from judging. Always exit 2, never a pass."""


class Finding(NamedTuple):
    """One line of output: what is wrong, where it is, and which rule says so."""

    severity: str
    file: str
    model: str
    message: str
    rule_id: str

    def line(self) -> str:
        return "\t".join(self[:4] + ("[%s]" % self.rule_id,))


def block(file: str, model: str, message: str, rule_id: str) -> Finding:
    """A finding that fails the command (exit 1)."""
    return Finding("BLOCK", file, model, message, rule_id)


def info(file: str, model: str, message: str, rule_id: str) -> Finding:
    """A finding the reviewer should see; it never changes the exit code."""
    return Finding("INFO", file, model, message, rule_id)


def _count(n: int, word: str) -> str:
    return "" if not n else "%d %s%s" % (n, word, "" if n == 1 else "s")


def report(findings: list[Finding], command: str, ok_note: str = "") -> int:
    """Print the findings sorted, then one summary line. Returns the exit code.

    By file, then by model, then what blocks before what only informs, and ties
    are left in the order the rules produced them - which is itself sorted, so
    two runs still print the same lines in the same order. A rule that has
    several things to say usually has a reading order for them, and I2's is the
    order Stage E asks the reviewer to read the numbers in.
    """
    for finding in sorted(
        findings, key=lambda f: (f.file, f.model, f.severity != "BLOCK", f.rule_id)
    ):
        print(finding.line())
    blocks = sum(1 for f in findings if f.severity == "BLOCK")
    counts = [c for c in (_count(blocks, "block"), _count(len(findings) - blocks, "info")) if c]
    if counts:
        print("slp %s: %s - %s" % (command, ", ".join(counts), "BLOCKED" if blocks else "OK"))
    else:
        print("slp %s: OK%s" % (command, " (%s)" % ok_note if ok_note else ""))
    return 1 if blocks else 0
