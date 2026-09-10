"""Tests about the tools themselves: Section 3 of the backlog, the mechanisms
that make adherence to the framework something a machine checks.

Every test here names the rule of Section 1 it enforces.
"""

import ast
import re

import pytest

import slp
from conftest import EXAMPLES, FIXTURES, TOOLS, expectation, run_slp

SOURCE = (TOOLS / "slp.py").read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)
RULES = (slp.CHECK_RULES + slp.GATE_RULES + slp.COMPARE_RULES
         + slp.COMPARE_RUN_RULES)
COVERAGE = re.findall(r"^\|[^|]+\|\s*`([A-Z]\d+)`\s*\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|",
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
                  and re.fullmatch(r"[A-Z]\d+", node.value))
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
    for node in ast.walk(TREE):
        if not isinstance(node, ast.FunctionDef):
            continue
        body = ast.get_source_segment(SOURCE, node)
        ids = set(re.findall(r'"([A-Z]\d+)"', body)) & set(slp.RULE_IDS)
        if not ids & set(slp.INFO_RULES):
            continue
        seen |= ids
        assert ids <= set(slp.INFO_RULES), "%s mixes %s" % (node.name, sorted(ids))
        assert not re.search(r"\bblock\(", body), "%s can block" % node.name
    assert seen == set(slp.INFO_RULES), sorted(set(slp.INFO_RULES) - seen)


# What slp.py may import, and which of those come from an index rather than the
# standard library. test_packaging holds the wheel's dependencies to the second
# set, so adding an import is a packaging decision in the same pull request.
ALLOWED_IMPORTS = {"argparse", "json", "os", "pathlib", "subprocess", "sys",
                   "dataclasses", "typing", "re", "hashlib", "yaml", "jsonschema"}
DISTRIBUTIONS = {"yaml": "pyyaml", "jsonschema": "jsonschema"}


def test_m3_the_tools_depend_on_nothing_new():
    """R2 and R5: no LLM, no network, no warehouse, and nothing dbt does not install."""
    allowed = ALLOWED_IMPORTS
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
    # examples/ too, except its markdown: a getting-started page may link out,
    # and the yml, sql, json and CODEOWNERS beside it are where a stray address
    # would actually matter.
    looked_at = [TOOLS / "slp.py"] + sorted(TOOLS.glob("schemas/*")) \
        + sorted(TOOLS.glob("templates/*")) + sorted(TOOLS.glob("tests/*.py")) \
        + sorted(p for p in (TOOLS / "tests" / "fixtures").rglob("*") if p.is_file()) \
        + sorted(p for p in EXAMPLES.rglob("*") if p.is_file() and p.suffix != ".md")
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
    invented = sorted(p for p in FIXTURES.rglob("*") if p.is_file()) \
        + sorted(p for p in EXAMPLES.rglob("*") if p.is_file())
    for path in invented:
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
    rows = lambda lines: re.findall(r"^\|[^|]+\|\s*`([A-Z]\d+)`\s*\|", "\n".join(lines), re.M)
    assert rows(english) == rows(portuguese) == list(slp.RULE_IDS)


def test_the_version_is_the_one_the_changelog_describes():
    """A tag nobody can trace to a list of rules is a number, not a release."""
    changelog = (TOOLS / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## %s " % slp.__version__ in changelog
    for rule in slp.RULE_IDS:
        assert "`%s`" % rule in changelog, rule


# What M8 caps, and why these three numbers rather than one. The promise R6 makes
# is that one person can read this tool. What that person actually does is read
# the machinery once - the loaders, the inventory, the output - and then read one
# rule at a time. So those are the two things worth capping, and the file as a
# whole gets a loose backstop that keeps growth visible without being a cliff.
#
# They are re-measured at each release and written back down here. A number only
# goes up when the pull request says what was bought with it.
#
# 0.4.0, measured after the work: 510 lines of machinery, biggest rule 30, 1317
# in all, thirty rules. MACHINERY went from 430 to 520 and every step bought
# something a rule could not carry alone: the merge-base read compare does for
# --base, the protected-path and singular-test inventory G9 and G10 read, the
# config() reader, the CODEOWNERS matcher S5 reads the way git does, and the
# two helpers every metric line shares now that a metric can be pre-registered
# by value. ONE_RULE did not move: the biggest rule is still 30 lines, four new
# rules landed under it, and a rule that needs more is two rules. WHOLE_FILE
# went from 1150 to 1350, and what was bought is the sentence next to each of
# those: it is the one of the three that counts prose.
#
# 0.3.0, for the record: 424, 30, 1100.
MACHINERY, ONE_RULE, WHOLE_FILE = 520, 32, 1350


def _weights():
    """slp.py by weight: each rule on its own, and the machinery every rule shares.

    Code means the lines that have to be *understood*: blanks, comments and
    docstrings are left out, because under a cap that counts them the cheapest
    way to buy room is to delete the prose that makes the file readable.
    """
    lines = SOURCE.splitlines()
    docstrings = set()
    for node in ast.walk(TREE):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, str):
            docstrings.update(range(node.lineno, node.end_lineno + 1))
    code = lambda span: sum(1 for n in span if lines[n - 1].strip()
                            and not lines[n - 1].strip().startswith("#")
                            and n not in docstrings)
    rules, claimed = {}, set()
    names = set(rule.__name__ for rule in RULES)
    for node in ast.walk(TREE):
        if isinstance(node, ast.FunctionDef) and node.name in names:
            span = set(range(node.lineno, node.end_lineno + 1))
            rules[node.name], claimed = code(span), claimed | span
    return rules, code(set(range(1, len(lines) + 1)) - claimed), len(lines)


def test_m8_the_machinery_is_read_once():
    """R6, first half: everything you must understand before any rule makes sense.

    One global cap used to hold the whole file, and it stopped measuring the
    promise. Every rule competed with every other rule and with the prose that
    explains them, so the cap turned into a rule-count limit dressed as a
    legibility limit - and the first time correctness needed room, the honest
    choice it offered was "delete a gate". Splitting it puts the pressure where
    it belongs: shared machinery is the part that must stay small, because it is
    the part everyone pays for.
    """
    _, machinery, _ = _weights()
    assert machinery <= MACHINERY, "%d lines of shared machinery" % machinery


@pytest.mark.parametrize("rule", RULES, ids=lambda r: r.__name__)
def test_m8_a_rule_is_read_on_its_own(rule):
    """R6, second half: a reader reads one rule, not twenty-four.

    A rule that cannot be said in this many lines is doing more than one thing,
    and the answer is two rules with two ids, two docstrings and two fixtures -
    which is also what makes it findable from the output.
    """
    rules, _, _ = _weights()
    assert rules[rule.__name__] <= ONE_RULE, \
        "%s is %d lines" % (rule.__name__, rules[rule.__name__])


def test_m8_the_file_is_still_one_file():
    """R6, the backstop. Not a legibility measure - a growth one, kept visible."""
    _, _, total = _weights()
    assert total <= WHOLE_FILE, "%d lines in all" % total
