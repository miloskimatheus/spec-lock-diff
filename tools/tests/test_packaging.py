"""The wheel against the file it wraps (the second way in).

Vendoring copies a folder you can read. Installing puts an index in the trust
root, so what the wheel claims has to be what the file does: the same version,
the same two dependencies, the same schemas beside the same module. Nothing here
lets `slp.py` and `pyproject.toml` drift apart quietly.
"""

import pytest
import yaml
from conftest import TOOLS
from test_meta import ALLOWED_IMPORTS, DISTRIBUTIONS

import spec_lock_diff as slp

PYPROJECT = TOOLS.parent / "pyproject.toml"
PACKAGE = "spec_lock_diff"


def _parsed():
    tomllib = pytest.importorskip("tomllib", reason="a TOML parser arrived in 3.11")
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


def test_the_wheel_ships_the_version_the_file_says_it_is():
    """Read as text, so the oldest leg of the matrix checks it too.

    The version already has to be a heading in the CHANGELOG and a tag; this is
    the fourth place it lives, and the only one a reader never sees.
    """
    assert 'version = "%s"' % slp.__version__ in PYPROJECT.read_text(encoding="utf-8")


def test_the_wheel_installs_exactly_what_the_allowlist_permits():
    """M3 says what slp.py may import. This says the wheel brings that and no more.

    Two lists that agree by hand agree until someone adds an import, so they are
    one decision here: a new dependency fails this test until it is declared, and
    fails M3 until it is allowed.
    """
    declared = {
        name.split(">")[0].split("=")[0].strip() for name in _parsed()["project"]["dependencies"]
    }
    assert declared == set(DISTRIBUTIONS.values())
    assert set(DISTRIBUTIONS) <= ALLOWED_IMPORTS


def test_the_schemas_travel_with_the_module():
    """SCHEMA_DIR is the directory beside readers.py, vendored or installed.

    Package data has to land in the same place the source reads from, and no
    branch in the source knows which world it is in.
    """
    parsed = _parsed()
    assert parsed["tool"]["setuptools"]["package-dir"] == {"": "tools"}
    assert parsed["tool"]["setuptools"]["packages"] == [PACKAGE, PACKAGE + ".rules"]
    globs = parsed["tool"]["setuptools"]["package-data"][PACKAGE]
    for schema in sorted(slp.SCHEMA_DIR.glob("*")):
        assert any(schema.match(pattern) for pattern in globs), schema.name


def test_the_command_is_still_called_slp():
    """argparse prints `usage: slp`, and every summary line begins `slp check:`.

    A command named something else names a command the reader did not type. The
    long name is the way out for anyone whose PATH already has an `slp`.
    """
    scripts = _parsed()["project"]["scripts"]
    assert scripts == {"slp": "%s.cli:main" % PACKAGE, "spec-lock-diff": "%s.cli:main" % PACKAGE}


def test_the_package_is_the_folder_beside_the_shim():
    """One package, read module by module, and one shim that hands over to it.

    A module added here ships as spec_lock_diff.<it> and is read by the
    meta-tests as part of the tool, so the list is the contract.
    """
    assert sorted(p.name for p in TOOLS.glob("*.py")) == ["slp.py"]
    package = TOOLS / PACKAGE
    assert sorted(p.relative_to(package).as_posix() for p in package.rglob("*.py")) == [
        "__init__.py",
        "__main__.py",
        "cli.py",
        "findings.py",
        "gitread.py",
        "owners.py",
        "project.py",
        "readers.py",
        "rules/__init__.py",
        "rules/check.py",
        "rules/common.py",
        "rules/compare.py",
        "rules/gate.py",
        "version.py",
    ]


def test_the_floor_is_the_oldest_python_the_suite_runs_on():
    """A wheel that installs on a version nothing tested is a wheel nobody checked."""
    workflow = yaml.safe_load(
        (TOOLS.parent / ".github" / "workflows" / "tools-tests.yml").read_text(encoding="utf-8")
    )
    legs = workflow["jobs"]["tests"]["strategy"]["matrix"]["python-version"]
    oldest = min(legs, key=lambda v: tuple(int(n) for n in v.split(".")))
    assert _parsed()["project"]["requires-python"] == ">=%s" % oldest
