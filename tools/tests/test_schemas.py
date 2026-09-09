"""The schemas as contracts (SLP-03, SLP-04, SLP-17).

Every fixture under valid/ must validate. Every fixture under invalid/ must be
rejected for the reason its first line names, so a fixture cannot pass for the
wrong reason when the schema changes.
"""

import json

import pytest
import yaml

import slp
from conftest import FIXTURES

# Whatever schemas/ holds: a new schema is covered the moment it lands.
KINDS = tuple(sorted(p.name.split(".")[0]
                     for p in slp.SCHEMA_DIR.glob("*.schema.json")))


def _load(path):
    text = path.read_text(encoding="utf-8")
    return json.loads(text) if path.suffix == ".json" else yaml.safe_load(text)


def _fixtures(group):
    return [(kind, path) for kind in KINDS
            for path in sorted((FIXTURES / "schemas" / kind / group).glob("*.*"))]


def _id(case):
    return "%s/%s" % (case[0], case[1].stem)


@pytest.mark.parametrize("case", _fixtures("valid"), ids=_id)
def test_valid_fixtures_validate(case):
    kind, path = case
    assert slp.schema_errors(_load(path), kind, kind) == []


@pytest.mark.parametrize("case", _fixtures("invalid"), ids=_id)
def test_invalid_fixtures_are_rejected_for_the_stated_reason(case):
    kind, path = case
    first = path.read_text(encoding="utf-8").splitlines()[0]
    expected = first.split("expect:")[1].strip()
    errors = list(slp.validator(kind).iter_errors(_load(path)))
    assert expected in [e.validator for e in errors], [e.message for e in errors]
    assert slp.schema_errors(_load(path), kind, kind)


@pytest.mark.parametrize("kind", KINDS)
def test_the_schema_itself_is_a_valid_schema(kind):
    assert slp.validator(kind) is not None


def test_messages_name_the_field_and_what_it_should_be():
    """R7: a person who is not a developer has to be able to act on the line."""
    bad = _load(FIXTURES / "schemas" / "spec" / "invalid" / "tier_typo.yml")
    assert slp.schema_errors(bad, "spec", "spec") == [
        'spec.tier: must be "critical" or "standard"; critical means the model feeds'
        ' business decisions, financial reports or executive dashboards (got "crítical")']
