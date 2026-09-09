"""Tests about the tools themselves: Section 3 of the backlog, the mechanisms
that make adherence to the framework something a machine checks.

Every test here names the rule of Section 1 it enforces.
"""

import ast
import re

import pytest

import slp
from conftest import FIXTURES, TOOLS, expectation, run_slp

SOURCE = (TOOLS / "slp.py").read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)
RULES = slp.CHECK_RULES + slp.GATE_RULES + slp.COMPARE_RULES
COVERAGE = re.findall(r"^\|[^|]+\|\s*`([A-Z]\d)`\s*\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|",
                      (TOOLS / "README.md").read_text(encoding="utf-8"), re.M)


def test_folder_layout():
    """The folder every ticket plugs into."""
    for path in ("slp.py", "README.md", "schemas", "templates", "tests/fixtures"):
        assert (TOOLS / path).exists(), "missing tools/" + path


@pytest.mark.parametrize("rule", RULES, ids=lambda r: r.__name__)
def test_m1_every_rule_points_at_a_readme_sentence(rule):
    """R1 and R8: no sentence, no rule. A reader goes output to code to README."""
    assert rule.__doc__, "%s has no docstring" % rule.__name__
    assert re.match(r"^README §\d", rule.__doc__), rule.__doc__.splitlines()[0]


def test_m2_the_coverage_table_lists_every_rule_exactly_once():
    """Section 3, mechanism 1: a rule with no row is a rule nobody can find."""
    assert [row[0] for row in COVERAGE] == sorted(set(row[0] for row in COVERAGE),
                                                  key=[r[0] for r in COVERAGE].index)
    assert set(row[0] for row in COVERAGE) == set(slp.RULE_IDS)


def test_m2_the_code_prints_no_rule_id_the_table_does_not_know():
    """The tuple at the top of slp.py and the ids in its rules cannot drift apart."""
    printed = set(node.value for node in ast.walk(TREE)
                  if isinstance(node, ast.Constant) and isinstance(node.value, str)
                  and re.fullmatch(r"[A-Z]\d", node.value))
    assert printed == set(slp.RULE_IDS)


@pytest.mark.parametrize("row", COVERAGE, ids=lambda row: row[0])
def test_m2_each_rule_has_a_fixture_that_fires_and_one_that_does_not(row):
    """Section 3, mechanism 1: the table is only true if the fixtures do what it says."""
    rule, fires, silent = row
    for name in (fires, silent):
        assert (FIXTURES / name).is_dir(), "no fixture folder %s" % name
    assert rule in expectation(FIXTURES / fires)["rules"], fires
    quiet = expectation(FIXTURES / silent)
    assert quiet["exit"] == 0 and rule not in quiet["rules"], silent


def test_m3_the_tools_depend_on_nothing_new():
    """R2 and R5: no LLM, no network, no warehouse, and nothing dbt does not install."""
    allowed = {"argparse", "json", "os", "pathlib", "subprocess", "sys",
               "dataclasses", "typing", "re", "hashlib", "yaml", "jsonschema"}
    imported = set()
    for node in ast.walk(TREE):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            imported.add((node.module or "").split(".")[0])
    assert imported <= allowed, imported - allowed


def test_m3_the_only_program_the_tools_run_is_git():
    """R2: a subprocess is a door. This one opens onto git and nothing else."""
    calls = [node for node in ast.walk(TREE) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Attribute)
             and isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess"]
    assert calls, "the gate needs git; if that changed, this test should change with it"
    for call in calls:
        first = ast.get_source_segment(SOURCE, call.args[0])
        assert first.startswith('["git"'), first


def test_m4_nothing_here_reaches_for_the_network():
    """R2: a URL in the code is either a mistake or a socket waiting to be opened."""
    looked_at = [TOOLS / "slp.py"] + sorted(TOOLS.glob("schemas/*")) \
        + sorted(TOOLS.glob("templates/*")) + sorted(TOOLS.glob("tests/*.py")) \
        + sorted(p for p in (TOOLS / "tests" / "fixtures").rglob("*") if p.is_file())
    address = re.compile(r"https?" + "://")  # split, so this file does not match itself
    for path in looked_at:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if address.search(line):
                # A schema identifies itself by URL; that is a name, not an address.
                assert '"$id"' in line or '"$schema"' in line, "%s:%d" % (path.name, number)


def _cpf_is_valid(digits):
    """The Brazilian document check digit, so a fixture cannot carry a real one."""
    numbers = [int(d) for d in digits]
    if len(set(numbers)) == 1:
        return False
    for size in (9, 10):
        total = sum(numbers[i] * (size + 1 - i) for i in range(size))
        digit = (total * 10) % 11 % 10
        if digit != numbers[size]:
            return False
    return True


def test_m6_the_fixtures_are_invented():
    """R9: the repository's own PR checklist forbids real data. This checks it."""
    for path in sorted(p for p in FIXTURES.rglob("*") if p.is_file()):
        text = path.read_text(encoding="utf-8", errors="replace")
        for address in re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text):
            assert address.endswith("@example.com"), "%s: %s" % (path.name, address)
        for digits in re.findall(r"(?<!\d)\d{11}(?!\d)", text):
            assert not _cpf_is_valid(digits), "%s: %s looks like a real document number" \
                % (path.name, digits)


def test_m7_the_same_files_give_the_same_lines():
    """R4 and Principle 3: a judge that answers differently twice is not a judge."""
    case = FIXTURES / "check" / "sensitive_mismatch"
    assert run_slp(["check"], case) == run_slp(["check"], case)


def test_m7_the_order_of_the_arguments_changes_nothing():
    case = FIXTURES / "compare" / "two_files_one_bad"
    names = sorted(p.name for p in case.glob("*.json"))
    assert run_slp(["compare"] + names, case) == run_slp(["compare"] + names[::-1], case)


def test_r10_the_two_readmes_are_the_same_document():
    """R10: two languages, one document. What is code in it is not translated."""
    english = (TOOLS / "README.md").read_text(encoding="utf-8").splitlines()
    portuguese = (TOOLS / "README.pt-br.md").read_text(encoding="utf-8").splitlines()

    def numbering(lines, prefix):
        return [line.split(".")[0] for line in lines if re.match(prefix, line)]

    # Same sections, in the same order, and a table of contents that matches them.
    assert numbering(english, r"^## \d") == numbering(portuguese, r"^## \d")
    assert numbering(english, r"^\d+\. \[") == numbering(portuguese, r"^\d+\. \[")
    # The tool's own output is not translated: a CI log reads the same either way.
    printed = lambda lines: [l for l in lines if re.match(r"^(BLOCK|INFO|slp |\$ python)", l)]
    assert printed(english) == printed(portuguese)
    # And both coverage tables cover the same rules, in the same order.
    rows = lambda lines: re.findall(r"^\|[^|]+\|\s*`([A-Z]\d)`\s*\|", "\n".join(lines), re.M)
    assert rows(english) == rows(portuguese) == list(slp.RULE_IDS)


def test_the_version_is_the_one_the_changelog_describes():
    """A tag nobody can trace to a list of rules is a number, not a release."""
    changelog = (TOOLS / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## %s " % slp.__version__ in changelog
    for rule in slp.RULE_IDS:
        assert "`%s`" % rule in changelog, rule


def _weights():
    """The lines of slp.py split into what must be understood and what explains it."""
    docstrings = set()
    for node in ast.walk(TREE):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, str):
            docstrings.update(range(node.lineno, node.end_lineno + 1))
    code = [n for n, line in enumerate(SOURCE.splitlines(), start=1)
            if line.strip() and not line.strip().startswith("#") and n not in docstrings]
    return len(code), len(SOURCE.splitlines())


def test_m8_the_one_file_is_still_one_sitting():
    """R6. The promise is that one person reads the whole thing in one sitting.

    The first version of this test counted every line, which put docstrings and
    comments on the wrong side of the ledger: the cheapest way to buy room was to
    delete the prose that makes the file readable, and that is the opposite of the
    promise. So the tight cap is on the lines that have to be *understood* - code,
    with blanks, comments and docstrings taken out - and a looser one holds the
    file as a whole. Both are honest numbers, measured after the rules were
    written, and both are still caps: if they stop holding, the answer is fewer
    rules or a different structure, not a bigger number.
    """
    code, total = _weights()
    assert code <= 725, "%d lines of code" % code
    assert total <= 1000, "%d lines in all" % total
