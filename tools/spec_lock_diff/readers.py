"""Reading files, and saying what a schema rejected in plain sentences."""

import json
import pathlib
import re

import jsonschema
import yaml

from .findings import SlpError

SCHEMA_DIR = pathlib.Path(__file__).resolve().parent / "schemas"


def parse_yaml(text, where):
    """Parse one YAML document. Unparseable is an error; empty is an empty document."""
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        # dbt renders a yml through jinja before reading it and these tools do
        # not, so say which of the two problems this is: "cannot parse" on its
        # own sends the reader hunting for a typo that is not there.
        why = (
            " - this file contains jinja, which these tools do not render"
            if re.search(r"{%|{{", text)
            else ""
        )
        raise SlpError("cannot parse %s: %s%s" % (where, " ".join(str(exc).split()), why)) from exc
    return {} if doc is None else doc


def load_yaml(path):
    """Read and parse one YAML file from disk."""
    try:
        return parse_yaml(pathlib.Path(path).read_text(encoding="utf-8"), path)
    except (OSError, UnicodeDecodeError) as exc:
        raise SlpError("cannot read %s: %s" % (path, exc)) from exc


def load_json(path):
    """Read and parse one JSON file from disk."""
    try:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        raise SlpError("cannot read %s: %s" % (path, exc)) from exc
    except ValueError as exc:
        raise SlpError("cannot parse %s: %s" % (path, exc)) from exc


_VALIDATORS = {}


def validator(name):
    """The validator for schemas/<name>.schema.json, loaded once, checked itself first."""
    if name not in _VALIDATORS:
        schema = load_json(SCHEMA_DIR / ("%s.schema.json" % name))
        jsonschema.Draft202012Validator.check_schema(schema)
        _VALIDATORS[name] = jsonschema.Draft202012Validator(schema)
    return _VALIDATORS[name]


def _why(err):
    """Turn one schema error into a sentence a non-developer can act on."""
    said = err.schema.get("description", "") if isinstance(err.schema, dict) else ""
    if err.validator == "required":
        found = re.search(r"'([^']*)'", err.message)
        field = found.group(1) if found else "?"
        sub = (err.schema.get("properties") or {}).get(field) or {}
        said = sub.get("description") or said
        return "missing required field '%s'%s" % (field, " - " + said if said else "")
    if err.validator == "additionalProperties":
        unknown = sorted(set(re.findall(r"'([^']*)'", err.message)))
        return "unknown field %s" % ", ".join("'%s'" % f for f in unknown)
    if not said:  # a field the schema does not describe: say what the keyword wanted
        said = {"enum": "must be one of: %s", "const": "must be %s"}.get(
            err.validator, "%s"
        ) % json.dumps(err.validator_value)
    if isinstance(err.instance, (dict, list)):
        return said
    return "%s (got %s)" % (said, json.dumps(err.instance, ensure_ascii=False))


def schema_errors(obj, name, prefix):
    """Every violation of obj against one schema, as sorted sentences with their path."""
    out = []
    for err in validator(name).iter_errors(obj):
        path = prefix
        for part in err.absolute_path:
            path += "[%d]" % part if isinstance(part, int) else "." + str(part)
        out.append("%s: %s" % (path, _why(err)))
    return sorted(out)
