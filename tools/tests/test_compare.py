"""compare: one folder per case under fixtures/compare/.

Each case is a small project plus the diff files measured against it. The
folder name and its README.txt say what must happen.
"""

import pytest

from conftest import FIXTURES, assert_expected, cases, findings, make_repo, run_slp

TREES = ("before", "mid", "after")


@pytest.mark.parametrize("case", cases("compare"), ids=lambda p: p.name)
def test_compare_case(case):
    diffs = sorted(p.name for p in case.glob("*.json"))
    code, out, err = run_slp(["compare"] + diffs, case)
    assert_expected(case, code, out, err)


def _repo(case, tmp_path):
    """A case under fixtures/compare_base/ is a repository: its trees are commits."""
    return make_repo(tmp_path, *[case / name for name in TREES if (case / name).is_dir()])


@pytest.mark.parametrize("case", cases("compare_base"), ids=lambda p: p.name)
def test_compare_base_case(case, tmp_path):
    """compare --base reads the merge-base, so these cases need a history, not a folder."""
    repo = _repo(case, tmp_path)
    diffs = [str(p) for p in sorted(case.glob("*.json"))]
    code, out, err = run_slp(["compare", "--base", "base"] + diffs, repo)
    assert_expected(case, code, out, err)


def test_without_base_an_inherited_pre_registration_still_counts(tmp_path):
    """The run without --base is stricter, never looser: C7 asks for the untouched model's diff."""
    case = FIXTURES / "compare_base" / "C7_ok_stale_not_counted"
    diffs = [str(p) for p in sorted(case.glob("*.json"))]
    code, out, _ = run_slp(["compare"] + diffs, _repo(case, tmp_path))
    assert code == 1 and "C7" in [f[4] for f in findings(out)], out


def test_the_message_states_both_numbers():
    """A reviewer has to see what was measured and what was promised, in one line."""
    case = FIXTURES / "compare" / "C1_row_delta_above_max"
    code, out, _ = run_slp(["compare", "diff.json"], case)
    assert code == 1
    assert out.splitlines()[0] == (
        "BLOCK\tdiff.json\tfct_orders\trow_delta is 15000, pre-registration "
        "allows 0..12000\t[C1]")
    # And the block is followed by the numbers themselves, in reading order.
    assert out.splitlines()[2] == (
        "INFO\tdiff.json\tfct_orders\trow_delta 15000, declared 0..12000 "
        "(a band 12000 wide)\t[I2]")
    assert out.splitlines()[-1] == "slp compare: 1 block, 6 infos - BLOCKED"


def test_reading_the_files_in_another_order_says_the_same_thing():
    """R4: the report is sorted, so the order of the arguments cannot change it."""
    case = [c for c in cases("compare") if c.name == "two_files_one_bad"][0]
    first = run_slp(["compare", "a_orders.json", "b_customers.json"], case)
    second = run_slp(["compare", "b_customers.json", "a_orders.json"], case)
    assert first == second


def test_a_refactoring_that_moved_blocks_without_C5_having_to():
    """C5 informs, so the block has to come from the interval rules themselves.

    A refactoring pins every interval to zero in the schema, which is why C5 can
    never be the only thing that noticed. This is that argument as a test: if a
    schema change ever made C5 the last line of defence, this fails.
    """
    case = FIXTURES / "compare" / "C5_refactoring_nonzero"
    code, out, _ = run_slp(["compare", "diff.json"], case)
    blocked = [f[4] for f in findings(out) if f[0] == "BLOCK"]
    assert code == 1 and blocked and "C5" not in blocked, out
    assert "C5" in [f[4] for f in findings(out) if f[0] == "INFO"], out
