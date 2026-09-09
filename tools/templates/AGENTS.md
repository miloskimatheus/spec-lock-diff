# AGENTS.md

Nothing in this file is a control. Every rule below is enforced by a machine —
a permission, a schema, a CI gate, a branch protection — and the mechanism is
named next to each rule. This file exists so you understand the intention; the
mechanisms exist so the rules hold even if you ignore this file.

This file is a protected path. You may not edit it.

## The 8 rules

| # | Rule | Mechanism that enforces |
| --- | --- | --- |
| 1 | **No spec, stop and ask.** If the model has no spec, the agent does not start. It asks the Author to write it. | CI validates spec presence (JSON Schema). |
| 2 | **Every model has PK test and minimum count.** The agent creates a uniqueness test on the spec's primary_key and a minimum row count test. Each spec edge becomes a unit test with synthetic fixture (invented data representing the described case). | CI validates test presence (JSON Schema + anti-fraud gate). |
| 3 | **Test failed = code wrong.** If a test fails, the agent fixes the code. Never the opposite. The agent never weakens a test, changes an `expect`, modifies a test macro, or removes a reconciliation to make CI pass. | Anti-fraud gate (Control 5B) detects and blocks. |
| 4 | **Metrics live in `models/semantic/`.** Metrics are defined once, in the semantic directory. If the metric the agent needs doesn't exist, it stops and asks the Author to create it. | CODEOWNERS protects `models/semantic/`. |
| 5 | **Fixed execution order.** The agent follows this sequence: `dbt compile` → `dbt test --select test_type:unit` → `dbt build`. If the same command fails 3 times in a row, the agent stops and calls a human. | 3-failure rule in the API gateway. |
| 6 | **Pre-registration before diff.** The agent must deliver the pre-registration (stage B) before any diff. Open intervals (without min or max) are invalid. | JSON Schema in CI. |
| 7 | **Never read individual rows.** The agent does not run `dbt show`, does not do `SELECT` without aggregation, and never pastes a value read from the warehouse into code, test, fixture, or PR comment. Fixtures are always synthetic (invented by the agent). | `agent_ci` role without access to `raw`. Masking in staging/marts. Anti-fraud gate detects real data in fixtures. |
| 8 | **Do not edit protected paths.** If the task requires changing a protected file (macros, CI, generic tests, etc.), the agent stops and asks the Author. | CODEOWNERS blocks merge without human approval. |

## Before you commit

Run these, in this order, and do not commit while any of them is red:

```bash
python tools/slp.py check              # spec, pre-registration, primary key test
python tools/slp.py gate --base main   # YOU: the branch this PR targets, if not main
dbt compile
dbt test --select test_type:unit
dbt build
```

YOU: if the marts of this project do not live in `models/marts/`, add
`--marts-path <dir>` to both commands, once per directory, and keep it
identical to the CI workflow.

`check` and `gate` are the same commands CI runs. If `gate` blocks, do not
work around it: the thing it found is a test you weakened, and rule 3 says the
code is what changes.

Read `check`'s last line. It says how many models it held to the framework and
how many it read: `OK (3 models in models/marts/, of 40 models read)`. If the
first number is not the number of marts models you touched, it is not checking
what you think it is.

## What you must not touch

- `.github/`, `.pre-commit-config.yaml`, `CODEOWNERS`, `AGENTS.md`,
  `packages.yml`, `dbt_project.yml`, `macros/`, `tests/`,
  `analyses/reconciliation_*`, `models/semantic/`, `docs/profile/`, `tools/`,
  the incremental models and the critical model directories your CODEOWNERS
  lists. YOU: keep this list identical to your CODEOWNERS file.
- `meta.spec` of any model. The spec is the human's decision, written before
  you started. If it is wrong, stop and say so; do not correct it.
- Any test, unit test or reconciliation query that already exists. You may add
  tests. You may not weaken one.
- The shape of a test you *do* add, if that shape stops it failing. A
  `severity: warn`, a `where` that removes the rows it would have caught, an
  `error_if` threshold it never reaches, `enabled: false` — a test that cannot
  fail is not a test, and `check` and `gate` both say so. The uniqueness test on
  the primary key is the one the framework makes mandatory; writing it this way
  is the same as not writing it.
- A model file with no yml entry. A `.sql` in a marts path that no yml declares
  has no spec, no primary key and no test, and `check` blocks on it (`S4`).

## When to stop and ask a human

- The model has no spec (rule 1).
- The same command failed three times in a row (rule 5).
- The task cannot be done without changing a protected path (rule 8).
- The metric you need does not exist in `models/semantic/` (rule 4).
- The diff came back outside your pre-registration. You do not widen the
  pre-registration; you explain what you found.

## How to read what the tools print

`BLOCK` fails the run. `INFO` never does, and is there to be read.

`compare` prints an `I2` line for every number it compared — the row delta, the
removed primary keys, each metric, the altered columns, the reconciliation —
next to the band your pre-registration declared for it and how wide that band
is. It prints them whether or not anything blocked. That is not noise: a human
reads those lines to answer *"was this pre-registration narrow enough to be
able to fail?"*, and a band wide enough to swallow any result is a finding
about you, not about the data. Write bands you could actually miss.

`I1` counts how many times the pre-registration changed after it was first
written. The count is visible to the Author in review. Predicting once and
predicting well is the point; editing the prediction until it fits the answer
is the thing pre-registration exists to prevent.
