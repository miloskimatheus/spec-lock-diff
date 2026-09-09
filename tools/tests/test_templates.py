"""The templates against the README they copy (SLP-20, SLP-21, SLP-22).

A template that drifts from the README is worse than no template: it looks
like the framework and enforces something else.
"""

import re

import pytest
import yaml

from conftest import TOOLS

README = (TOOLS.parent / "README.md").read_text(encoding="utf-8")
TEMPLATES = TOOLS / "templates"


def _table(after, before):
    return README.split(after)[1].split(before)[0]


def test_codeowners_protects_every_path_the_readme_lists():
    """Control 5A is a table in prose; the template is the same table as a control."""
    template = (TEMPLATES / "CODEOWNERS").read_text(encoding="utf-8")
    paths = re.findall(r"^\| `([^`]+)`", _table("**Part A — CODEOWNERS", "**Part B"), re.M)
    assert len(paths) == 11
    for path in paths:
        assert path.strip("/") in template, path


def test_codeowners_adds_only_what_it_explains():
    """The three additions to the README's list are the only ones."""
    template = (TEMPLATES / "CODEOWNERS").read_text(encoding="utf-8")
    owned = re.findall(r"^(/\S+)\s+@", template, re.M)  # commented lines own nothing
    # The additions the template explains: the gate itself, the second place git
    # looks for CODEOWNERS, and the other two files that pin dependencies.
    extra = {"/tools/", "/CODEOWNERS", "/.github/CODEOWNERS",
             "/package-lock.yml", "/dependencies.yml"}
    for path in owned:
        assert path in extra or path.strip("/").split("*")[0] in README, path


def test_every_placeholder_says_what_to_put_there():
    """A line the reader must edit is marked, and never left to be guessed."""
    for name in sorted(p.name for p in TEMPLATES.iterdir()):
        text = (TEMPLATES / name).read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), start=1):
            if "YOU:" in line:
                assert len(line.split("YOU:")[1].split()) >= 4, "%s:%d" % (name, number)


def test_agents_md_carries_the_eight_rules_and_their_mechanisms():
    """Rule and mechanism travel together: a rule with no mechanism is a suggestion."""
    template = (TEMPLATES / "AGENTS.md").read_text(encoding="utf-8")
    table = _table("**The 8 agent rules:**", "### Stage D")
    rows = [r for r in table.splitlines() if re.match(r"^\| \d", r)]
    assert len(rows) == 8
    for row in rows:
        number, rule, mechanism = [c.strip() for c in row.strip().strip("|").split("|")][:3]
        assert rule in template, "rule %s is not in AGENTS.md as the README writes it" % number
        assert mechanism in template, "rule %s lost its mechanism" % number


def test_agents_md_says_it_is_not_a_control():
    template = (TEMPLATES / "AGENTS.md").read_text(encoding="utf-8")
    assert "Nothing in this file is a control" in template.split("\n\n")[1]
    for command in ("python tools/slp.py check", "python tools/slp.py gate --base",
                    "dbt compile", "dbt test --select test_type:unit", "dbt build"):
        assert command in template
