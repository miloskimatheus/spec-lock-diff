"""check: one folder per case under fixtures/check/.

The folder name and its README.txt say what must happen, so adding a rule means
adding a folder - never editing this file.
"""

import pytest

from conftest import FIXTURES, assert_expected, cases, run_slp


@pytest.mark.parametrize("case", cases("check"), ids=lambda p: p.name)
def test_check_case(case):
    code, out, err = run_slp(["check"], case)
    assert_expected(case, code, out, err)


def test_the_lines_say_what_is_wrong_and_where():
    """R7: file, model, one plain sentence, rule id - and nothing else."""
    case = FIXTURES / "check" / "sensitive_mismatch"
    code, out, _ = run_slp(["check"], case)
    assert code == 1
    assert out == (
        "BLOCK\tmodels/marts/dim_customers.yml\tdim_customers\tcolumn customer_document"
        " is marked meta.sensitive: true but is not in spec.sensitive_columns\t[S3]\n"
        "BLOCK\tmodels/marts/dim_customers.yml\tdim_customers\tspec.sensitive_columns"
        " names customer_email, but that column is not marked meta.sensitive: true\t[S3]\n"
        "slp check: 2 blocks - BLOCKED\n")


def test_a_missing_spec_points_at_the_readme():
    code, out, _ = run_slp(["check"], FIXTURES / "check" / "marts_no_spec")
    assert code == 1
    assert "model has no meta.spec (README §3 Stage A)" in out
