"""Tests about the tools themselves: Section 3 of the backlog, the mechanisms
that make adherence to the framework something a machine checks.

Every test here names the rule of Section 1 it enforces.
"""

import ast
import re

import pytest
from conftest import EXAMPLES, FIXTURES, TOOLS, expectation, run_slp

import spec_lock_diff as slp

PACKAGE = TOOLS / "spec_lock_diff"
# The tool, module by module: the shim adopters run, and every file of the package.
MODULES = {
    path: path.read_text(encoding="utf-8")
    for path in [TOOLS / "slp.py"] + sorted(PACKAGE.rglob("*.py"))
}
TREES = {path: ast.parse(text) for path, text in MODULES.items()}
RULES = slp.CHECK_RULES + slp.GATE_RULES + slp.COMPARE_RULES + slp.COMPARE_RUN_RULES
COVERAGE = re.findall(
    r"^\|[^|]+\|\s*`([A-Z]\d+)`\s*\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|",
    (TOOLS / "README.md").read_text(encoding="utf-8"),
    re.M,
)


def test_folder_layout():
    """The folder every ticket plugs into."""
    for path in (
        "slp.py",
        "spec_lock_diff",
        "spec_lock_diff/schemas",
        "README.md",
        "templates",
        "tests/fixtures",
    ):
        assert (TOOLS / path).exists(), "missing tools/" + path


@pytest.mark.parametrize("rule", RULES, ids=lambda r: r.__name__)
def test_m1_every_rule_points_at_a_readme_sentence(rule):
    """R1 and R8: no sentence, no rule. A reader goes output to code to README."""
    assert rule.__doc__, "%s has no docstring" % rule.__name__
    assert re.match(r"^README §\d", rule.__doc__), rule.__doc__.splitlines()[0]


def test_m2_the_coverage_table_lists_every_rule_exactly_once():
    """Section 3, mechanism 1: a rule with no row is a rule nobody can find."""
    assert [row[0] for row in COVERAGE] == sorted(
        set(row[0] for row in COVERAGE), key=[r[0] for r in COVERAGE].index
    )
    assert set(row[0] for row in COVERAGE) == set(slp.RULE_IDS)


def test_m2_the_code_prints_no_rule_id_the_table_does_not_know():
    """The tuple in rules/__init__.py and the ids the rules print cannot drift apart."""
    printed = set(
        node.value
        for tree in TREES.values()
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and re.fullmatch(r"[A-Z]\d+", node.value)
    )
    assert printed == set(slp.RULE_IDS)


@pytest.mark.parametrize("row", COVERAGE, ids=lambda row: row[0])
def test_m2_each_rule_has_a_fixture_that_fires_and_one_that_does_not(row):
    """Section 3, mechanism 1: the table is only true if the fixtures do what it says."""
    rule, fires, silent = row
    for name in (fires, silent):
        assert (FIXTURES / name).is_dir(), "no fixture folder %s" % name
    assert rule in expectation(FIXTURES / fires)["rules"], fires
    quiet = expectation(FIXTURES / silent)
    assert rule not in quiet["rules"], silent
    # The silent fixture is a healthy run - except for a rule that only ever
    # informs, which has no healthy silence to point at. I2 speaks whenever
    # there are numbers to show, so the one case where it says nothing is the
    # case where the tool could not read them, and that case blocks.
    assert quiet["exit"] == 0 or rule in slp.INFO_RULES, silent


def test_m2_a_rule_that_only_informs_never_blocks():
    """INFO_RULES is a promise about the exit code. This is that promise, checked."""
    seen = set()
    for path, tree in TREES.items():
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            body = ast.get_source_segment(MODULES[path], node)
            ids = set(re.findall(r'"([A-Z]\d+)"', body)) & set(slp.RULE_IDS)
            if not ids & set(slp.INFO_RULES):
                continue
            seen |= ids
            assert ids <= set(slp.INFO_RULES), "%s mixes %s" % (node.name, sorted(ids))
            assert not re.search(r"\bblock\(", body), "%s can block" % node.name
    assert seen == set(slp.INFO_RULES), sorted(set(slp.INFO_RULES) - seen)


# What the tool may import, and which of those come from an index rather than the
# standard library. Its own modules import each other with relative imports,
# which are not on this list because they are not a dependency. test_packaging
# holds the wheel's dependencies to the second
# set, so adding an import is a packaging decision in the same pull request.
ALLOWED_IMPORTS = {
    "argparse",
    "json",
    "os",
    "pathlib",
    "subprocess",
    "sys",
    "dataclasses",
    "typing",
    "re",
    "hashlib",
    "yaml",
    "jsonschema",
}
DISTRIBUTIONS = {"yaml": "pyyaml", "jsonschema": "jsonschema"}


def test_m3_the_tools_depend_on_nothing_new():
    """R2 and R5: no LLM, no network, no warehouse, and nothing dbt does not install."""
    allowed = ALLOWED_IMPORTS | {"spec_lock_diff"}  # the shim and __main__ name the package
    imported = set()
    for tree in TREES.values():
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                imported.add((node.module or "").split(".")[0])
    assert imported <= allowed, imported - allowed


def test_m3_the_only_program_the_tools_run_is_git():
    """R2: a subprocess is a door. This one opens onto git and nothing else."""
    calls = [
        (path, node)
        for path, tree in TREES.items()
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "subprocess"
    ]
    assert calls, "the gate needs git; if that changed, this test should change with it"
    assert set(path.name for path, _ in calls) == {"gitread.py"}
    for path, call in calls:
        first = ast.get_source_segment(MODULES[path], call.args[0])
        assert first.startswith('["git"'), first


def test_m4_nothing_here_reaches_for_the_network():
    """R2: a URL in the code is either a mistake or a socket waiting to be opened."""
    # examples/ too, except its markdown: a getting-started page may link out,
    # and the yml, sql, json and CODEOWNERS beside it are where a stray address
    # would actually matter.
    looked_at = (
        list(MODULES)
        + sorted(PACKAGE.glob("schemas/*"))
        + sorted(p for p in TOOLS.glob("templates/*") if p.is_file())
        + sorted(TOOLS.glob("tests/*.py"))
        + sorted(p for p in (TOOLS / "tests" / "fixtures").rglob("*") if p.is_file())
        + sorted(p for p in EXAMPLES.rglob("*") if p.is_file() and p.suffix != ".md")
    )
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
    invented = sorted(p for p in FIXTURES.rglob("*") if p.is_file()) + sorted(
        p for p in EXAMPLES.rglob("*") if p.is_file()
    )
    for path in invented:
        text = path.read_text(encoding="utf-8", errors="replace")
        for address in re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text):
            assert address.endswith("@example.com"), "%s: %s" % (path.name, address)
        for digits in re.findall(r"(?<!\d)\d{11}(?!\d)", text):
            assert not _cpf_is_valid(digits), "%s: %s looks like a real document number" % (
                path.name,
                digits,
            )


# The words that lower a threshold without touching it: a comment that exempts
# a line from coverage, a mark that exempts a test from running, a comment that
# exempts a line from a linter or a type checker. Assembled from pieces, so that
# this file, which has to name them, does not fail its own test.
HATCHES = (
    "pragma" + ":",
    "no" + " cover",
    "no" + "cover",
    "mark." + "skip",
    "skip" + "if(",
    "xf" + "ail",
    "no" + "qa",
    "type" + ": ignore",
    "importor" + "skip",
)
# The two skips that are justified: a vendored tools/ has no examples/ beside it,
# and a TOML parser arrived in 3.11. Each is a line that must contain the words.
JUSTIFIED = (
    ("test_examples.py", "skip" + "if(not EXAMPLES.is_dir()"),
    ("test_packaging.py", "importor" + 'skip("tomllib"'),
)


def test_m9_no_escape_hatch_lowers_a_threshold():
    """The 100 percent and the 30 of crap.py are immutable only while nothing can exempt a line."""
    for path in list(MODULES) + sorted(TOOLS.glob("tests/*.py")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            hatch = next((h for h in HATCHES if h in line), None)
            if hatch is None:
                continue
            assert any(path.name == name and words in line for name, words in JUSTIFIED), (
                "%s:%d carries an escape hatch: %s" % (path.name, number, line.strip())
            )


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
    def printed(lines):
        return [line for line in lines if re.match(r"^(BLOCK|INFO|slp |\$ python)", line)]

    assert printed(english) == printed(portuguese)

    # And both coverage tables cover the same rules, in the same order.
    def rows(lines):
        return re.findall(r"^\|[^|]+\|\s*`([A-Z]\d+)`\s*\|", "\n".join(lines), re.M)

    assert rows(english) == rows(portuguese) == list(slp.RULE_IDS)


def test_the_version_is_the_one_the_changelog_describes():
    """A tag nobody can trace to a list of rules is a number, not a release."""
    changelog = (TOOLS / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## %s " % slp.__version__ in changelog
    for rule in slp.RULE_IDS:
        assert "`%s`" % rule in changelog, rule
