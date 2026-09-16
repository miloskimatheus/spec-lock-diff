"""Every rule id these tools can print, and the registries the three commands run.

A rule is one function: context in, findings out. The check rules take a
Project, the gate rules a Gate, the compare rules a Diff, and the rules about
the compare run as a whole a Run.
"""

from .check import (
    check_model_declared,
    check_owned,
    check_pk_test,
    check_prereg_consistency,
    check_prereg_schema,
    check_spec_consistency,
    check_spec_present,
    check_spec_schema,
)
from .compare import (
    compare_columns,
    compare_contract,
    compare_coverage,
    compare_metrics,
    compare_reconciliation,
    compare_refactoring,
    compare_removed_pks,
    compare_rows,
    compare_summary,
)
from .gate import (
    gate_packages,
    gate_prereg_counter,
    gate_prereg_present,
    gate_protected_paths,
    gate_recon_with_model,
    gate_singular_born_muted,
    gate_spec_changed,
    gate_spec_first_written,
    gate_test_filter,
    gate_test_narrowed,
    gate_test_removed,
    gate_test_severity,
    gate_unit_test_changed,
)

# Every rule id these tools can print. The README coverage table has one row per
# id and the fixtures one folder per id; meta-test M2 keeps the three in step.
RULE_IDS = (
    "S1",
    "S2",
    "S3",
    "S4",
    "S5",
    "P1",
    "P2",
    "T1",
    "G1",
    "G2",
    "G3",
    "G4",
    "G5",
    "G6",
    "G7",
    "G8",
    "G9",
    "G10",
    "I1",
    "I3",
    "I4",
    "C0",
    "C1",
    "C2",
    "C3",
    "C4",
    "C5",
    "C6",
    "C7",
    "I2",
)

# Rules that only ever inform. The README asks for what they say to be visible,
# not for it to stop the pull request, so they never raise the exit code.
# C5's id does not start with I because it was written as a block. It informs
# because a refactoring's intervals are pinned to zero by the schema, so C1 to
# C4 already refuse every number it could catch; if that stops being true, this
# tuple is where C5 goes back to blocking.
INFO_RULES = ("I1", "I2", "I3", "I4", "C5")

CHECK_RULES = [
    check_spec_present,
    check_model_declared,
    check_spec_schema,
    check_spec_consistency,
    check_owned,
    check_prereg_schema,
    check_prereg_consistency,
    check_pk_test,
]

GATE_RULES = [
    gate_test_removed,
    gate_test_filter,
    gate_test_severity,
    gate_test_narrowed,
    gate_unit_test_changed,
    gate_recon_with_model,
    gate_packages,
    gate_protected_paths,
    gate_singular_born_muted,
    gate_spec_changed,
    gate_spec_first_written,
    gate_prereg_present,
    gate_prereg_counter,
]

COMPARE_RULES = [
    compare_contract,
    compare_rows,
    compare_removed_pks,
    compare_columns,
    compare_metrics,
    compare_refactoring,
    compare_reconciliation,
    compare_summary,
]

# Rules about the whole run. They see every file at once, so they cannot live in
# the loop above; everything else about them - docstring, rule id, fixtures - is
# the same, and the meta-tests hold them to it.
COMPARE_RUN_RULES = [compare_coverage]
