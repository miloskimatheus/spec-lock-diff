# The gate walkthrough

`gate` is the one command that reads git rather than the working tree, so it
cannot be demonstrated in place: a dbt project that is not at the root of its
repository makes it exit 2 on every read, and `--project-dir` cannot save it.

So this folder is not a project. It is two snapshots of one — `before/`, the
model as `main` has it, and `after/`, the model as the agent left it — and the
walkthrough is to make them into two commits.

## The change

One line, in `models/marts/fct_orders.yml`. The agent's model returned duplicate
`order_id`s. Instead of fixing the model, it deleted the test that said so:

```diff
       - name: order_id
         tests:
-          - unique
           - not_null
```

Nothing else moved. The sql is byte-identical, the spec is byte-identical, and
`dbt build` on the result is green — there is no longer a test to fail.

## Run it

```bash
cd "$(mktemp -d)" && git init -q -b main
cp -r /path/to/spec-lock-diff/examples/gate-walkthrough/before/. .
git add -A && git commit -qm "the model as main has it" && git tag base
rm -rf models && cp -r /path/to/spec-lock-diff/examples/gate-walkthrough/after/models .
git add -A && git commit -qm "the agent's change"
python /path/to/spec-lock-diff/tools/slp.py gate --base base
```

```
BLOCK	models/marts/fct_orders.yml	fct_orders	test 'unique' on fct_orders.order_id exists on main but not in this PR	[G1]
slp gate: 1 block - BLOCKED
```

Exit 1. This is Control 5B, and it is the reason the framework does not trust a
green build: the build *was* green. What the gate compares is not the code
against a standard but this branch against the branch it targets, so a test that
existed and no longer does is visible even when nothing that remains is wrong.

## What else it would have caught

The same two commits, with a different edit in `after/`, produce a different
rule. Each is one line in the yml:

| Edit | Rule |
| --- | --- |
| `severity: warn` on the `unique` test | `G3` — an error turned into a warning makes CI pass and leaves the problem |
| `where: order_id is not null` on it | `G2` — a filter that removes exactly the rows that would fail |
| Changing the sql without adding a `meta.pre_registration` | `G8` — nothing downstream has an interval to hold the numbers against |
| Editing `meta.spec` | `G7` — the spec is the human's, and Stage A happens before Stage C |
| Touching `dbt_project.yml`, `macros/` or `.github/` | `G9` — a protected path, where a macro can silently replace a test everywhere |

Thirteen `gate` rules in all; [the tools README](../../tools/README.md#7-the-rules)
lists every one with the two fixtures that hold it to its word, and
`tools/tests/fixtures/gate/` has seventy-eight more cases than this folder does.
