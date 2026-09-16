"""spec_lock_diff - the deterministic gates of Spec-Lock-Diff. No network, no model, no warehouse.

One package, read module by module: findings (what a rule says and how a run
ends), readers (yml, json and the schemas), project (a dbt project as its yml
declares it), owners (CODEOWNERS the way git reads it), gitread (two commits
and the walk between them), rules/ (one function per rule, one module per
command) and cli (the three commands). Vendored, `python tools/slp.py` runs
it; installed, `slp` does. cli's docstring says what each command asks.
"""

from .cli import build_parser, main
from .findings import Finding, SlpError, block, info, report
from .gitread import Gate, git, git_blobs, inventory
from .project import MARTS, Model, Project, UnitTest, normalize_test, read_doc, read_project
from .readers import SCHEMA_DIR, load_json, load_yaml, parse_yaml, schema_errors, validator
from .rules import CHECK_RULES, COMPARE_RULES, COMPARE_RUN_RULES, GATE_RULES, INFO_RULES, RULE_IDS
from .rules.common import apply_rules
from .version import __version__

__all__ = [
    "__version__",
    "build_parser",
    "main",
    "Finding",
    "SlpError",
    "block",
    "info",
    "report",
    "Gate",
    "git",
    "git_blobs",
    "inventory",
    "MARTS",
    "Model",
    "Project",
    "UnitTest",
    "normalize_test",
    "read_doc",
    "read_project",
    "SCHEMA_DIR",
    "load_json",
    "load_yaml",
    "parse_yaml",
    "schema_errors",
    "validator",
    "CHECK_RULES",
    "COMPARE_RULES",
    "COMPARE_RUN_RULES",
    "GATE_RULES",
    "INFO_RULES",
    "RULE_IDS",
    "apply_rules",
]
