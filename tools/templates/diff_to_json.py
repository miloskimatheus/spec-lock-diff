#!/usr/bin/env python3
"""One row of numbers in, one diff.json out. Copy next to your CI, or vendor it.

The tools do not produce the diff - that reads the warehouse, and they do not.
What they demand is its shape. This closes the last hand-written step between a
comparison query and `slp compare`: the translation of one result row into the
JSON of tools/schemas/diff.schema.json.

It reads one row of CSV or one JSON object, from a file or from stdin, and it
knows the columns by their suffixes:

    row_delta                    integer, required. PR rows minus prod rows.
    removed_pks                  integer, required. Keys in prod and not in the PR.
    <metric>_delta_pct           the metric's move in percentage points, or empty
                                 when production is 0 - which stays null, and
                                 `compare` blocks on it, because a number nobody
                                 can evaluate is not a number anybody approved.
    <metric>_changed             a count. Above zero puts <metric> in altered_columns.
    <metric>_value               the value in the PR build, for a model production
                                 does not have.
    reconciliation_model_value   the two numbers of a critical model's
    reconciliation_external_value  reconciliation query, written as one pair.
    window_column                the closed window the numbers were measured over,
    window_start                 identical on both sides. Printed by `compare` for
    window_end                   the reviewer.

Anything else in the row is ignored, so a query may select more than this needs.

    slp-diff --model fct_orders --out diff/fct_orders.json < row.csv

Stdlib only, and it never opens a socket: the same two promises slp.py makes.
"""

import argparse
import csv
import json
import re
import sys

SUFFIXES = ("_delta_pct", "_changed", "_value")
RECONCILIATION = ("reconciliation_model_value", "reconciliation_external_value")
WINDOW = ("window_column", "window_start", "window_end")


def read_row(stream):
    """The one row, as a dict of strings. CSV with a header, or a JSON object."""
    text = stream.read().strip()
    if not text:
        raise SystemExit("diff_to_json: nothing on the input")
    if text[0] in "[{":
        row = json.loads(text)
        if isinstance(row, list):
            if len(row) != 1:
                raise SystemExit("diff_to_json: expected one row, got %d" % len(row))
            row = row[0]
        return {str(k): row[k] for k in row}
    rows = list(csv.DictReader(text.splitlines()))
    if len(rows) != 1:
        raise SystemExit("diff_to_json: expected one row of csv, got %d" % len(rows))
    return rows[0]


def number(value, name):
    """A cell as a number, or None when the query wrote nothing there."""
    if value is None or (isinstance(value, str) and value.strip().lower() in ("", "null", "none")):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        raise SystemExit("diff_to_json: %s is %r, which is not a number" % (name, value))


def whole(value, name):
    """A cell as an integer. A count that arrives as 8400.0 is still a count."""
    got = number(value, name)
    if got is None or got != int(got):
        raise SystemExit("diff_to_json: %s must be a whole number, got %r" % (name, value))
    return int(got)


def metrics_of(row):
    """The metric names the row carries, by the suffixes it spells them with."""
    names = []
    for column in row:
        for suffix in SUFFIXES:
            if column.endswith(suffix) and not column.startswith("reconciliation_"):
                name = column[: -len(suffix)]
                if name and name not in names:
                    names.append(name)
    return names


def build(row, model):
    """The diff, in the shape of tools/schemas/diff.schema.json."""
    if "row_delta" not in row or "removed_pks" not in row:
        raise SystemExit("diff_to_json: the row needs row_delta and removed_pks")
    diff = {
        "model": model,
        "row_delta": whole(row["row_delta"], "row_delta"),
        "removed_pks": whole(row["removed_pks"], "removed_pks"),
        "altered_columns": [],
        "metrics": {},
    }
    if diff["removed_pks"] < 0:
        raise SystemExit("diff_to_json: removed_pks is negative")
    for name in metrics_of(row):
        measured = {}
        if name + "_delta_pct" in row:
            measured["delta_pct"] = number(row[name + "_delta_pct"], name + "_delta_pct")
        if name + "_value" in row:
            measured["value"] = number(row[name + "_value"], name + "_value")
        if measured:
            # delta_pct is required of every metric; a model production does not
            # have has no percentage, and null is how the diff says so.
            measured.setdefault("delta_pct", None)
            diff["metrics"][name] = measured
        if whole(row.get(name + "_changed", 0) or 0, name + "_changed") > 0:
            diff["altered_columns"].append(name)
    diff["altered_columns"].sort()
    if all(key in row for key in RECONCILIATION):
        diff["reconciliation"] = {
            "model_value": number(row[RECONCILIATION[0]], RECONCILIATION[0]),
            "external_value": number(row[RECONCILIATION[1]], RECONCILIATION[1]),
        }
    if all(key in row for key in WINDOW):
        diff["window"] = {"column": str(row["window_column"]),
                          "start": str(row["window_start"]), "end": str(row["window_end"])}
    return diff


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="diff_to_json", description=__doc__.splitlines()[0])
    parser.add_argument("row", nargs="?", help="one row of csv or json (default: stdin)")
    parser.add_argument("--model", required=True, help="the dbt model these numbers are of")
    parser.add_argument("--out", help="where to write (default: stdout)")
    args = parser.parse_args(argv)
    with open(args.row, encoding="utf-8") if args.row else sys.stdin as stream:
        diff = build(read_row(stream), args.model)
    text = json.dumps(diff, indent=2, sort_keys=True) + "\n"
    if not args.out:
        sys.stdout.write(text)
        return 0
    with open(args.out, "w", encoding="utf-8") as handle:
        handle.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
