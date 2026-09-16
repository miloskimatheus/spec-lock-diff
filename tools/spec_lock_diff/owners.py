"""CODEOWNERS the way git reads it, for the rule about who approves a critical or incremental
model.
"""

from __future__ import annotations

import pathlib
import re

from .project import Model

# Where git looks for the file, in the order it looks.
CODEOWNERS_FILES = (".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS")


def _owner_rules(root: pathlib.Path) -> list[tuple[re.Pattern[str], list[str]]] | None:
    """The CODEOWNERS file as (pattern, owners) in file order, or None when there is no file.

    The patterns are gitignore's, without negation: a leading slash or a slash
    inside anchors the pattern to the root, otherwise it matches at any depth;
    a trailing slash means the directory and everything under it; `*` stops at
    a slash and `**` does not. The last line that matches a path wins, and a
    line with a pattern and no owner un-owns what it matches.
    """
    path = next((root / p for p in CODEOWNERS_FILES if (root / p).is_file()), None)
    if path is None:
        return None
    rules: list[tuple[re.Pattern[str], list[str]]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        words = line.split("#")[0].split()
        if not words:
            continue
        pattern, owners = words[0], words[1:]
        anchored = pattern.startswith("/") or "/" in pattern.rstrip("/")
        body = (
            re.escape(pattern.strip("/"))
            .replace(r"\*\*", ".*")
            .replace(r"\*", "[^/]*")
            .replace(r"\?", "[^/]")
        )
        tail = "/.*" if pattern.endswith("/") else "(/.*)?"
        rules.append((re.compile(("^" if anchored else "^(.*/)?") + body + tail + "$"), owners))
    return rules


def _owners(rules: list[tuple[re.Pattern[str], list[str]]], path: str) -> list[str]:
    """Who CODEOWNERS makes approve a change to path: the last matching line decides."""
    owners: list[str] = []
    for regex, who in rules:
        if regex.match(path):
            owners = who
    return owners


def _incremental(model: Model, sql: pathlib.Path | None) -> bool:
    """Whether the model is materialized as incremental, in its yml config or in its sql."""
    config = model.entry.get("config")
    config = config if isinstance(config, dict) else {}
    if config.get("materialized") == "incremental":
        return True
    if sql is None or not sql.is_file():
        return False
    return (
        re.search(
            r"materialized\s*=\s*['\"]incremental['\"]",
            sql.read_text(encoding="utf-8", errors="replace"),
        )
        is not None
    )
