"""compare: one folder per case under fixtures/compare/.

Each case is a small project plus the diff files measured against it. The
folder name and its README.txt say what must happen.
"""

import pytest

from conftest import FIXTURES, assert_expected, cases, run_slp


@pytest.mark.parametrize("case", cases("compare"), ids=lambda p: p.name)
def test_compare_case(case):
    diffs = sorted(p.name for p in case.glob("*.json"))
    code, out, err = run_slp(["compare"] + diffs, case)
    assert_expected(case, code, out, err)


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
