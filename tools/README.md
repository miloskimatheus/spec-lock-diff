# `tools/` — the deterministic gates of Spec-Lock-Diff

**English** · [Português (pt-BR)](README.pt-br.md)

> **Work in progress.** These tools are the first, minimal, reference
> implementation of Spec-Lock-Diff. They are deliberately small. They will
> change. Adapt them to your warehouse, your CI and your team — that is
> expected, not a deviation. And if you improve them, bring the improvement
> back: open a *Field report* or a PR. We are building this together.

Three commands. One file. No model, no network, no warehouse. Everything here
implements a sentence of the [framework README](../README.md); where the README
says nothing, these tools do nothing.

**Contents**

1. [What is in this folder](#1-what-is-in-this-folder)
2. [Set up your environment](#2-set-up-your-environment)
3. [The three commands](#3-the-three-commands)
4. [The `diff.json` contract](#4-the-diffjson-contract)
5. [Templates](#5-templates)
6. [Schemas](#6-schemas)
7. [Output format and exit codes](#7-output-format-and-exit-codes)
8. [Coverage table](#8-coverage-table)
9. [What v0 does not do](#9-what-v0-does-not-do)
10. [How to contribute](#10-how-to-contribute)

---

## 1. What is in this folder

| Path | What it is |
| --- | --- |
| `slp.py` | The whole tool: three commands, twenty-six rules, one file you can read in one sitting. |
| `schemas/spec.schema.json` | What a `meta.spec` must look like (README §3 Stage A). |
| `schemas/pre_registration.schema.json` | What a `meta.pre_registration` must look like (README §3 Stage B). |
| `schemas/diff.schema.json` | What a `diff.json` must look like — the one interface to whatever measures your diff. |
| `templates/CODEOWNERS` | The protected paths of Control 5A, ready to copy. |
| `templates/AGENTS.md` | The 8 agent rules of Stage C, each next to the mechanism that enforces it. |
| `templates/ci.yml` | An example GitHub Actions workflow wiring the three commands. |
| `tests/conftest.py` | The test harness: run a command, build a repository from fixture trees, read a fixture's expectation. |
| `tests/test_cli.py` | The entry point itself: arguments, loaders, exit codes. |
| `tests/test_schemas.py` | Every schema against its valid and invalid fixtures. |
| `tests/test_check.py`, `test_gate.py`, `test_compare.py` | One test per fixture folder of each command. |
| `tests/test_templates.py` | The templates against the README they copy. |
| `tests/test_harness.py` | The harness itself, because a lying harness makes every other test lie. |
| `tests/test_meta.py` | The tools about the tools: references, coverage, dependencies, determinism, size. |
| `tests/fixtures/` | Every case, as real files. One folder per case, each with a `README.txt`. |

---

## 2. Set up your environment

1. **Python 3.9 or newer**, and **git 2.20 or newer**. Check with
   `python3 --version` and `git --version`. Most Linux distributions ship
   `python3` and no `python` at all; every command in this document is written
   `python` for brevity, so if yours is one of them, read `python3` throughout —
   including in `templates/ci.yml` and `templates/AGENTS.md`, where the same
   commands are wired into CI.
2. **PyYAML and jsonschema 4 or newer.** If dbt is installed you already have
   both. If not: `pip install "pyyaml" "jsonschema>=4"`. The floor is not
   decoration — the schemas are JSON Schema draft 2020-12, and the validator for
   it arrived in jsonschema 4.0. On 3.x the tools do not fall back to an older
   draft; they fail to start. These two libraries are all they use.
3. **Copy `tools/` into the root of your dbt repository**, next to
   `dbt_project.yml`.
4. **Copy the templates into place:**
   ```bash
   cp tools/templates/CODEOWNERS .github/CODEOWNERS
   cp tools/templates/AGENTS.md  AGENTS.md
   cp tools/templates/ci.yml     .github/workflows/ci.yml
   ```
   Then edit every line each file marks as yours, and replace
   `@your-org/data-platform` with the team that approves.
5. **Turn on branch protection** for `main`: require pull requests, require
   review from Code Owners, and list `ci` and `diff` as required checks — those
   are the job names in `ci.yml`.
6. **Check that it runs:**
   ```bash
   python tools/slp.py --version
   ```
7. **Optional, and worth it:** `pip install pytest && pytest tools/tests -q`.
   Around two hundred and eighty tests, a few seconds, no network. If they
   pass, the gates on your machine are the gates in CI.

---

## 3. The three commands

```
python tools/slp.py check   [--project-dir .] [--marts-path models/marts]
python tools/slp.py gate    --base <git ref> [--head HEAD] [--project-dir .] [--marts-path ...]
python tools/slp.py compare <diff.json> [<diff.json> ...] [--base <git ref>] [--project-dir .] [--marts-path ...]
python tools/slp.py --version
```

### `check`

**What it is.** `check` reads every model file under `models/` and tells you
whether each model in `models/marts/` has a complete spec, a valid
pre-registration (if it has one), and a uniqueness test on its primary key.

**Why the framework needs it.** Principle 1: "The human decides before, by
writing the spec." Stage A: "PR cannot advance without a completed spec."
Rule 1: "No spec, stop and ask." Rule 2: "The agent creates a uniqueness test
on the spec's primary_key."

**How it works.** It loads the yml files, finds each model's `meta.spec` (or
`config.meta.spec`), validates it against `schemas/spec.schema.json`, checks the
few things a schema cannot — do the primary key columns exist? does the
reconciliation query exist? do the sensitive columns and the `meta.sensitive`
flags agree? — and prints one line per problem. It also lists the `.sql` files
in the marts paths, so a model nobody declared in a yml cannot slip past for
lack of anything to check (`S4`); it never reads what is inside them, never
calls git, and never touches the warehouse.

**Where it looks.** `models/marts/`, because that is where README §3 Stage A
makes the spec mandatory. If your marts live somewhere else, say so with
`--marts-path`, and repeat the flag for more than one directory:

```
python tools/slp.py check --marts-path models/core --marts-path models/finance
```

Pass the same paths to `gate` and `compare`. A path that is not a directory is
an error (exit 2), not a pass — a tool pointed at a folder that is not there
finds nothing wrong with anything, and that reads exactly like a clean run.
That is also why the summary line separates the two numbers: **how many models
were held to the framework**, and how many were read in all. Only the first is
coverage.

A model counts as a marts model when **the `.sql` that makes it** lives in a
marts path — not when the yml that documents it does. A project that keeps one
`models/schema.yml` for everything, which is what `dbt init` scaffolds, is
ordinary dbt; deciding by the yml path would have exempted every model in it
from `S1`, `T1` and `G7` while `check` printed `OK`.

**When it runs.** Stage A, while the Author writes the spec. Stage C, before
the agent commits. Stage D, in CI, on every push.

**How to use it.**

```
$ python tools/slp.py check
slp check: OK (1 model in models/marts/, of 1 model read)
```

```
$ python tools/slp.py check
BLOCK	models/marts/fct_orders.yml	fct_orders	no uniqueness test on primary key [order_id]; accepted forms: unique, unique_combination_of_columns, dbt_utils.unique_combination_of_columns	[T1]
slp check: 1 block - BLOCKED
```

Both are copied from `tests/fixtures/check/spec_ok` and
`tests/fixtures/check/pk_single_missing`; you can run them yourself with
`--project-dir`.

**What counts as a test.** `T1` only accepts a uniqueness test that can fail
the build. A test that is `enabled: false`, or `severity: warn`, or narrowed by
`where`, `error_if`, `warn_if`, `fail_calc` or `limit`, runs and reports a pass
whatever the data does — `unique` with `where: "1 = 0"` looks at no rows at
all. The framework makes this one test mandatory; a mandatory test that cannot
fail is a box ticked, so `check` says which of those it found:

```
BLOCK	models/marts/fct_orders.yml	fct_orders	the uniqueness test on primary key [order_id] cannot fail the build: it sets where	[T1]
```

That is `T1` and not a `gate` rule on purpose: `gate` compares a test against
its earlier self, and a test written this way on a new model has no earlier
self to be weaker than.

**How to change it.** To require a new spec field, add it to
`schemas/spec.schema.json` with a `description` written as a requirement — that
description is the sentence the tool prints — and add one valid and one invalid
fixture under `tests/fixtures/schemas/spec/`. To accept another form of
uniqueness test, add its name to `ACCEPTED_PK_TESTS` inside `check_pk_test` and
add a passing fixture under `tests/fixtures/check/`. To add a check, write one
function whose docstring starts with the README section it enforces, append it
to `CHECK_RULES`, add a blocking fixture and a passing one, and add a row to the
[coverage table](#8-coverage-table). If what you want is not in the framework
README, open a *Framework improvement* issue first.

### `gate`

**What it is.** `gate` compares this branch with the point it started from and
blocks the pull request if anything that judges the code was weakened: a test,
a unit test, a reconciliation query, a package pin, or the spec itself.

**Why the framework needs it.** Control 5B: "A script that runs in CI on the
commits made by the bot … analyzes the diffs and **blocks the PR**." Rule 3:
"Test failed = code wrong. If a test fails, the agent fixes the code. Never the
opposite."

**How it works.** It asks git for the merge-base of `--base` and `--head` — not
the tip of `main`, so a branch that moved on does not look like your branch
removing things — reads the files as they are at that commit and as they are at
`head`, and compares two inventories. A data test is identified by its model,
its column, its name and its arguments — and a unit test by its model and its
name, because dbt only makes those unique inside a model and two marts may each
have one called `cancelled_orders_are_excluded`. So moving a test to another
file or
renaming `tests:` to `data_tests:` changes nothing, while shrinking the values
of an `accepted_values` changes everything. A column that carries two tests of
the same name — two `relationships`, several `accepted_values` — has each of
them compared separately, config and all, and the finding names which one it
means. When two of them carry the *same arguments* as well, and differ only in
their config — two `dbt_utils.expression_is_true` on the same expression with a
`where` each — the pair is held as a bag under one key and compared as one: how
many there were, how many there are, and which configs are in the second bag
and not the first. Numbering them instead would be wrong in the case that
matters, because removing the first of two hands its number to the second,
which reads as a config edit rather than as a removed test. For the two rules
that need history, it walks the commits with `--first-parent`, oldest first.
Everything one commit holds is read down a single `git cat-file --batch`, so a
pull request costs about two git processes per commit rather than one per file
per commit — 150 models across a 30-commit branch used to spend twenty seconds
starting processes before a rule had looked at anything.

**When it runs.** Stage C, before the agent commits (`--base main`). Stage D, in
CI, on every push, with the base and head of the pull request.

**How to use it.**

```
$ python tools/slp.py gate --base main
slp gate: OK (no changes)
```

```
$ python tools/slp.py gate --base main
BLOCK	models/marts/fct_orders.yml	fct_orders	test 'unique' on fct_orders.order_id exists on main but not in this PR	[G1]
slp gate: 1 block - BLOCKED
```

In CI, pass both ends explicitly, and check out the whole history — the walk
needs the commits:

```yaml
- uses: actions/checkout@v4
  with:
    fetch-depth: 0
- run: |
    python tools/slp.py gate \
      --base ${{ github.event.pull_request.base.sha }} \
      --head ${{ github.event.pull_request.head.sha }}
```

**The pre-registration is not optional.** Stage B is where the agent commits to
intervals before it sees any result, and until `G8` nothing made it happen.
`check` validated a pre-registration only when it found one; no `gate` rule
looked for its absence; and `C7` walks the models that *carry* one, so a model
without a pre-registration is not a model `compare` reports as missing — it is a
model `compare` has never heard of. Deleting the prediction was cheaper than
missing it. `G8` blocks when the `.sql` of a marts model changed on the branch
and no `meta.pre_registration` is there to hold its numbers against — or the one
there is the one `main` already had.

**A pre-registration belongs to one pull request** (README §3 Stage B, *whose
it is*). After a merge it stays in the yml as the record of what was predicted,
so the next change to that model finds one already there — written for another
change, against another production. Until 0.4.0 that inherited prediction
satisfied `G8`, made `C7` demand a diff of every model anyone had ever
pre-registered, and turned the honest act of replacing it into an `I1` edit.
Now a pre-registration identical to the merge-base's counts as absent: `G8`
blocks on it, `I1` starts counting from the first commit whose pre-registration
differs from `main`'s, and `compare --base` refuses to read numbers against it
(`C0`) and does not ask for its diff (`C7`).

It is scoped to the `.sql` on purpose: Stage B says the agent declares what it
expects *before writing any code*, so the code changing is the trigger. Adding a
test, writing a description or documenting a column does not ask for an
interval. A change made only in the yml that does move numbers — a
materialisation, a `config` — is a gap, and it is in
[section 9](#9-what-v0-does-not-do).

**What a test the branch adds is allowed to be.** `G2` and `G3` compare a test
against its earlier self, and a test written on this branch has none — so for
years' worth of dbt projects the way past both was to add the test in the same
PR. `G3` holds a new test to the same line as an old one: `enabled: false`, a
`severity` that is not `error`, an `error_if`, a `warn_if`, a `fail_calc` or a
`limit` blocks, because none of those has a reading under which the test can
fail. A `where` is the one that might: it can be honest scoping — a column only
populated after a backfill date — or it can be the rows that would have failed.
No machine can tell those apart, so `I3` prints it and the human doing Stage E's
third reading decides. That is the same predicate `T1` uses, and `T1` refuses a
`where` outright, because it is judging the one test the framework makes
mandatory rather than one the agent chose to add.

**Gate scope.** The gate judges the whole pull request, not "the agent's
commits". There is no bot identity to configure, and a commit author is text
anyone can write. What follows: in an agent PR nobody weakens a test — not the
agent, not a human. A human who must change a test does it **before the agent
starts**, as part of writing the spec, or in a separate PR of their own.

**How to change it.** One rule is one function: a docstring that starts with
the README sentence it enforces, a rule id, and a list of findings. Append it to
`GATE_RULES`, add a fixture folder that blocks and one named `_ok_` that passes
under `tests/fixtures/gate/`, and add a row to the coverage table. The fixture
folders are the test suite: `test_gate.py` iterates them and never needs
editing.

### `compare`

**What it is.** `compare` reads the numbers your diff measured and holds each
one against the interval the pre-registration declared before any code was
written.

**Why the framework needs it.** Stage E step 3: "Each diff number is
automatically compared with the intervals declared in the pre-registration."
Stage B: "the agent commits to intervals *before* seeing the results. If the
numbers fall outside the interval, the PR is automatically blocked — the agent
cannot 'adjust' its prediction later."

**How it works.** It reads one or more `diff.json` files, validates each against
`schemas/diff.schema.json`, finds the model in your project, re-checks that its
pre-registration is valid, and then compares: row delta, removed primary keys,
altered columns, every metric, and — for critical models — the reconciliation
against its tolerance. It does not produce the diff and does not run the
reconciliation query: those touch the warehouse, and these tools do not.

Then it does one thing the files cannot ask it to do: it looks at the project
for models that carry a pre-registration and whose numbers never turned up, and
blocks on those (`C7`). Hand it every diff your build produced, in one call —
`compare diff/*.json`, not one call per file — because a rule about what is
*missing* can only see what it was given.

Give it `--base <git ref>` — the branch the pull request targets, as
`templates/ci.yml` does — and it reads the pre-registration each model had at
the merge-base, the same point `gate` compares against. One that is still
identical to it is `main`'s prediction, not this pull request's: `C7` does not
ask for its diff, and a diff measured against it is refused (`C0`). Without
`--base`, every pre-registration in the project counts as this pull request's.
That is stricter, never looser — `C7` asks for a diff of each, and an inherited
one is compared instead of refused — so a local run without the flag can block
for a model you never touched. Pass it.

**When it runs.** Stage E, once per pull request, after the full build.

**How to use it.**

```
$ python tools/slp.py compare diff.json
INFO	diff.json	fct_orders	measured over order_date from 2025-01-01 to 2025-01-31	[C0]
INFO	diff.json	fct_orders	declared as a data_change, because: include status partially_shipped, previously excluded incorrectly	[I2]
INFO	diff.json	fct_orders	row_delta 8400, declared 0..12000 (a band 12000 wide)	[I2]
INFO	diff.json	fct_orders	removed_pks 0, declared at most 0	[I2]
INFO	diff.json	fct_orders	metric gross_revenue moved 0.42 percent, declared 0.0..0.8 (a band 0.8 wide)	[I2]
INFO	diff.json	fct_orders	altered columns measured [gross_revenue], declared [gross_revenue]	[I2]
slp compare: 6 infos - OK
```

```
$ python tools/slp.py compare diff.json
BLOCK	diff.json	fct_orders	metric gross_revenue moved 2.5 percent, pre-registration allows 0.0..0.8	[C4]
INFO	diff.json	fct_orders	declared as a data_change, because: include status partially_shipped, previously excluded incorrectly	[I2]
INFO	diff.json	fct_orders	row_delta 8400, declared 0..12000 (a band 12000 wide)	[I2]
slp compare: 1 block, 6 infos - BLOCKED
```

Every message names both numbers: what was measured and what was promised —
and `I2` names them **whether or not anything blocked**. That is the point of
it. Stage E step 5 asks the Author three questions, and the second is *"Is the
pre-registration narrow enough to be able to fail? Does the reason justify the
interval?"* A `row_delta` of 8,400 inside a band 12,000 wide is a different
review from the same 8,400 inside a band 200 wide, and a run that prints only
`OK` gives you no way to tell them apart. So `compare` prints the reason that
was given, every number, the band declared for it, and how wide that band is —
which is the width the README calls out when it says `{min: -999999, max:
999999}` is useless.

It also says so when the diff carries no `window`, because README §3 Stage E
step 2 calls the closed, identical window essential and nothing here can verify
it — the second line of that output is the tool telling you which of its
promises it cannot keep for you.

`I2` never changes the exit code. Neither does `I1`. What they say has to be
*read*, which is why `templates/ci.yml` pipes both into the job summary.

**How to change it.** Same shape as the gate: one function, one docstring with
its README sentence, one rule id, appended to `COMPARE_RULES`, with a blocking
fixture and a passing one under `tests/fixtures/compare/` and a row in the
coverage table. If you want to compare something the diff does not carry yet,
the schema is the place to start — and if the framework README does not ask for
that number, open an issue before writing the rule.

---

## 4. The `diff.json` contract

One file per model. The keys mirror the pre-registration on purpose, so the
comparison is key by key.

| Key | Type | Required | Meaning |
| --- | --- | --- | --- |
| `model` | string | yes | the dbt model these numbers were measured on |
| `row_delta` | integer | yes | rows in the PR build minus rows in production, inside the window |
| `removed_pks` | integer ≥ 0 | yes | primary keys present in production and absent in the PR build |
| `altered_columns` | array of strings | yes | columns with at least one PK-matched row whose value differs |
| `metrics` | object of `{delta_pct: number or null}` | yes (may be `{}`) | one measurement per metric |
| `reconciliation` | `{model_value, external_value}` | no | critical models |
| `window` | `{column, start, end}` | no | printed by `compare` for the reviewer |
| `extra` | object | no | anything else you want to carry; ignored |

**The unit and sign of `delta_pct`.** Percentage *points*, written as a plain
number, computed as `(pr − prod) / prod × 100`.

> Production sums 1,000,000.00 of `gross_revenue` in the window. The PR build
> sums 1,008,000.00. Then `delta_pct` is
> `(1008000 − 1000000) / 1000000 × 100 = 0.8` — the number **0.8**, not 0.008
> and not 80. A pre-registration of `{min: 0.0, max: 0.8}` accepts it, at the
> edge. If the PR build sums *less* than production the number is negative.
> When production is 0 the percentage does not exist: write `null`, and
> `compare` blocks, because a number nobody can evaluate is not a number
> anybody approved.

**Where the numbers come from.** Anything deterministic: Recce,
`dbt-audit-helper` in summary mode, or your own SQL. The window must be closed
and identical on both sides — if production has data up to yesterday and the PR
build up to today, "today" shows up as a false difference. A starting point,
adapt freely:

```sql
-- YOU: your schemas, your model, your window, your metrics.
with prod as (
    select * from analytics.fct_orders
    where order_date >= date '2025-01-01' and order_date < date '2025-02-01'
),
pr as (
    select * from ci_pr_42_full.fct_orders
    where order_date >= date '2025-01-01' and order_date < date '2025-02-01'
),
matched as (
    select
        prod.order_id       as prod_key,
        pr.order_id         as pr_key,
        prod.gross_revenue  as prod_gross_revenue,
        pr.gross_revenue    as pr_gross_revenue
    from prod
    left join pr on prod.order_id = pr.order_id   -- the spec's primary_key
)
select
    (select count(*) from pr) - (select count(*) from prod)         as row_delta,
    sum(case when pr_key is null then 1 else 0 end)                 as removed_pks,
    sum(case when pr_key is not null
              and prod_gross_revenue is distinct from pr_gross_revenue
             then 1 else 0 end)                                     as gross_revenue_changed,
    100.0 * ((select sum(gross_revenue) from pr)
             - (select sum(gross_revenue) from prod))
          / nullif((select sum(gross_revenue) from prod), 0)         as gross_revenue_delta_pct
from matched
```

One row out, one `diff.json` in: put `gross_revenue` in `altered_columns` when
`gross_revenue_changed > 0`, and `gross_revenue_delta_pct` — which `nullif`
already turns into `null` when production is 0 — into
`metrics.gross_revenue.delta_pct`. For a multi-column primary key, join on every
column. For a critical model, add the two numbers your reconciliation query
returned as `reconciliation`.

The recommended contract for the reconciliation query itself is one row of
`metric, model_value, external_value`, so the same query can be read by a human
and by whatever writes the JSON.

---

## 5. Templates

### `templates/CODEOWNERS`

**What it is.** The protected-path list of Control 5A as a file you copy.

**Why the framework needs it.** Control 5A: "git requires human approval for
these paths." Principle 2: a limit that is written down and hoped for is not a
control; a branch protection is.

**How it works.** git refuses to merge a pull request touching one of these
paths until an owner approves it. It works whether or not the agent read
`AGENTS.md`.

**When it runs.** Once, when the Platform sets the repository up; then on every
pull request, forever.

**How to use it.** Copy to `.github/CODEOWNERS`, replace
`@your-org/data-platform`, list your incremental models and your critical
directories where the file asks, and turn on "Require review from Code Owners".

**How to change it.** The file follows the README's table row by row, and
`test_templates.py` fails if a row goes missing. It adds three paths the table
does not list — `tools/`, and, commented out, `models/staging/` and `.claude/`
— each with the reason next to it. To add another, add the line and its reason.

### `templates/AGENTS.md`

**What it is.** The eight rules of Stage C, in under a page, each next to the
mechanism that enforces it.

**Why the framework needs it.** Stage C: "Each rule below must have an
infrastructure mechanism that enforces it. The text rule exists only for the
agent to understand the intention; the mechanism exists so that the rule works
even if the agent ignores it."

**How it works.** It does not. That is its first line: nothing in the file is a
control. It tells the agent what the machines around it will do, so the agent
does not waste a pull request finding out.

**When it runs.** Stage C, read by the agent before it writes anything.

**How to use it.** Copy to `AGENTS.md` at the repository root, keep the
protected path list identical to your CODEOWNERS, and protect the file itself.

**How to change it.** The eight rules are copied word for word from the README
and `test_templates.py` compares them; if you want a different rule, change the
README first. Everything after the table — what to run before committing, what
not to touch, when to stop and ask — is yours to adapt.

### `templates/ci.yml`

**What it is.** An example GitHub Actions workflow with two jobs, `ci` and
`diff`, that wires the three commands into the framework's Stages D and E.

**Why the framework needs it.** Stage D: "A CI pipeline that runs automatically
every time the agent pushes … Must complete in less than 15 minutes." Stage E:
"Runs once per PR, when the PR is marked as ready-for-review."

**How it works.** `ci` checks out the whole history, runs `check` and `gate`,
and builds what changed on a sample window. `diff` waits for `ci`, builds with
full data, produces the diff and runs `compare`. Both pipe their output into the
job summary, so the Author reads the findings without opening the logs.

**When it runs.** On every push to a pull request; `diff` only once the pull
request is out of draft.

**How to use it.** Copy to `.github/workflows/ci.yml`, then work through the
marked lines: your adapter, your warehouse authentication, your production
artifacts, your full build, your diff. Each of those steps exits 1 until you
write it — a template that is shipped unedited fails closed. Finally, list `ci`
and `diff` as required checks in branch protection.

**How to change it.** It is an example, not a contract; the only parts other
things depend on are the two job names and the three `slp.py` commands. If you
use GitLab, Buildkite or Jenkins, keep those and translate the rest.

---

## 6. Schemas

All three are JSON Schema draft 2020-12, and every field carries a
`description` written as a requirement — because that description is what the
tool prints when the field is wrong. A schema that reads as documentation and
an error message that reads as a sentence are the same text.

### `schemas/spec.schema.json`

**What it is.** The shape of `meta.spec`: six mandatory fields, plus three more
when `tier: critical`.
**Why.** README §3 Stage A. The spec format is the framework's own invention; a
schema turns an example into a contract.
**How.** `check` validates every spec it finds against it.
**When.** Stages A, C and D.
**Use.** Nothing to do — `check` uses it.
**Change.** Add the field, write its description as a requirement, add a valid
and an invalid fixture under `tests/fixtures/schemas/spec/`. Cross-field rules
("this column must exist") do not belong here; they go in `check_spec_consistency`.

### `schemas/pre_registration.schema.json`

**What it is.** The shape of `meta.pre_registration`.
**Why.** README §3 Stage B and Rule 6: "Open intervals (without min or max) are
invalid." The schema is where that stops being a sentence.
**How.** `check` validates it; `compare` re-validates before comparing anything.
**When.** Stages B, C, D and E.
**Use.** Nothing to do.
**Change.** Same as above. Note the `if/then`: a `refactoring` pins every number
to zero.

### `schemas/diff.schema.json`

**What it is.** The shape of the `diff.json` your automation writes.
**Why.** README §3 Stage E step 2 lists what the diff publishes. This is that
list, as a contract.
**How.** `compare` validates each file before reading a single number from it.
**When.** Stage E.
**Use.** Whatever produces your diff must write this shape. See
[section 4](#4-the-diffjson-contract).
**Change.** If you add a key, add it here and say what it means; `compare`
rejects keys it does not know, which is what stops a typo from being read as
"nothing changed".

---

## 7. Output format and exit codes

One line per finding, tab-separated, then one summary line. Everything on
stdout; errors that stop the tool go to stderr.

```
BLOCK	models/marts/orders.yml	fct_orders	test 'unique' on fct_orders.order_id exists on main but not in this PR	[G1]
INFO	models/marts/orders.yml	fct_orders	pre-registration was modified 2 times after it was first written	[I1]
slp gate: 1 block, 1 info - BLOCKED
```

| Severity | Meaning |
| --- | --- |
| `BLOCK` | Something is wrong. Sets exit code 1. |
| `INFO` | Something the reviewer should see. Never changes the exit code. |

| Exit code | Meaning | What CI does |
| --- | --- | --- |
| 0 | Nothing to report | pass |
| 1 | At least one `BLOCK` | fail |
| 2 | The tool could not do its job: a file it cannot read, yml it cannot parse, a bad argument, not a git repository | fail |

Exit code 2 is a failure, never a pass. What cannot be read cannot be approved:
a silent pass is the exact failure this framework exists to prevent.

Findings are sorted by file, then model, then what blocks before what only
informs, then rule id — and ties keep the order the rule produced them in,
because a rule with several things to say usually has a reading order for them.
`I2`'s is the order Stage E asks you to read the numbers in. The same files in
give the same lines out, in the same order, on every machine.

Four rules only ever inform and never change the exit code: `I1`, the
pre-registration change counter; `I2`, the numbers themselves; `I3`, a filter on
a test this branch adds; and `C5`, which names in one line what a refactoring
promised and what moved. The first three were written to inform, which is why
their ids start with `I`. `C5` was written to block and stopped: a refactoring's
intervals are pinned to zero by the schema, so `C1` to `C4` already refuse every
number it could catch, and blocking twice for one problem makes a reviewer count
two. Meta-test **M2** checks that promise against
the source, so a rule cannot quietly grow a `BLOCK`. What they say is meant to
be *read*, which is why `templates/ci.yml` pipes both commands into the job
summary.

**How to read a run.** Three questions, in this order.

1. **Did it exit 2?** Then nothing was judged. A file it could not read, yml it
   could not parse, a `--marts-path` that is not a directory. Fix that first;
   an exit 2 tells you nothing about the code.
2. **Is there a `BLOCK`?** Each one names what was measured and what was
   promised, and ends in a rule id you can look up in the
   [coverage table](#8-coverage-table). A `gate` block is almost never
   something to work around: it is a test that got weaker, and the framework's
   Rule 3 says the code is what changes.
3. **Then read the `INFO` lines.** They never change the exit code, which is
   exactly why they are easy to skip and worth not skipping. `I1` says how many
   times the pre-registration was edited after it was first written — a number
   the README asks the Author to see. `I2` is the diff itself: every number
   next to the band declared for it, and how wide that band is. `I3` is a test
   the branch added with a `where`, which no machine can tell from honest
   scoping — you can. `C5` is one line saying what a refactoring promised and
   what moved, when `C1` to `C4` have already blocked for the same reason.

A run that blocks nothing is not the same as a run that found nothing to look
at. `slp check: OK (3 models in models/marts/, of 40 models read)` is a
coverage statement; read the first number. `slp compare: OK (1 file)` on a pull
request that pre-registered two models is now impossible (`C7`), and that is
the shape of most of what this tool is for: a green that means *"I did not
look"* is the failure the framework exists to prevent.

**Where the tools look for things.** dbt 1.10 moved `meta` under `config`, so
both spellings are read. If both are present for the same thing, that is an
error (exit 2, "ambiguous: defined twice") — the tool does not guess which one
you meant.

| Thing | Classic | dbt 1.10+ |
| --- | --- | --- |
| spec | `models[].meta.spec` | `models[].config.meta.spec` |
| pre-registration | `models[].meta.pre_registration` | `models[].config.meta.pre_registration` |
| sensitive flag | `columns[].meta.sensitive` | `columns[].config.meta.sensitive` |
| data tests | `tests:` | `data_tests:` |

---

## 8. Coverage table

One row per rule: the README sentence it enforces, the fixture where the rule
fires, and the fixture where it stays silent. Meta-test **M2** fails if a rule
has no row here, or a row names a fixture that does not exist or does not do
what it says. Every rule blocks except the four in `INFO_RULES` — `I1`, the pre-registration
change counter; `I2`, the numbers themselves; `I3`, a filter on a test this
branch adds; and `C5`, the refactoring promise in one line — which only ever
inform. The README asks for
what they say to be *visible*, not for it to stop the PR, and **M2** checks that
against the source so none of them can quietly grow a `BLOCK`.

| README | Rule | Fixture where it fires | Fixture where it stays silent |
| --- | --- | --- | --- |
| §3 Stage A — "PR cannot advance without a completed spec" | `S1` | `check/marts_no_spec` | `check/spec_ok` |
| §3 Stage A — the six mandatory fields and their format | `S2` | `check/spec_invalid_tier` | `check/spec_ok` |
| §3 Stage A — the spec names columns of this model, and a reconciliation query that exists | `S3` | `check/sensitive_mismatch` | `check/spec_ok` |
| §3 Stage A — a model file no yml declares has no spec to ask for | `S4` | `check/sql_without_yml` | `check/spec_ok` |
| §3 Stage B — the pre-registration format | `P1` | `check/prereg_open_interval` | `check/prereg_ok` |
| §3 Stage B, Rule 6 — closed intervals, and the spec's metrics | `P2` | `check/prereg_min_gt_max` | `check/prereg_ok` |
| §2 Rule 2 — "creates a uniqueness test on the spec's primary_key" | `T1` | `check/pk_single_missing` | `check/pk_single_unique` |
| §2 Control 5B — "Test removed" | `G1` | `gate/G1_removed_unique` | `gate/G1_ok_test_added` |
| §2 Control 5B — "WHERE or exclusion clause added to a test" | `G2` | `gate/G2_where_added` | `gate/G2_ok_where_removed` |
| §2 Control 5B — "severity downgraded (e.g., error → warn)" | `G3` | `gate/G3_error_to_warn` | `gate/G3_ok_warn_to_error` |
| §2 Control 5B — "expect value changed in an existing test" | `G4` | `gate/G4_expect_changed` | `gate/G4_ok_new_unit_test` |
| §2 Control 5B — "analyses/reconciliation_* changed in the same PR as the model" | `G5` | `gate/G5_recon_and_sql_changed` | `gate/G5_ok_recon_only` |
| §2 Control 5B — "Package pin changed" | `G6` | `gate/G6_version_bumped` | `gate/G6_ok_untouched` |
| §1 Principle 1, §3 Stage A — the spec is decided before the code | `G7` | `gate/G7_existing_spec_edited` | `gate/G7_ok_new_spec_untouched` |
| §3 Stage C — "cannot start without a valid pre-registration" | `G8` | `gate/G8_sql_changed_no_prereg` | `gate/G8_ok_prereg_present` |
| §3 Stage B — "a change counter is incremented in the PR" | `I1` | `gate/I1_two_edits` | `gate/I1_ok_written_once` |
| §2 Control 5B — "WHERE or exclusion clause added to a test", for a test this branch adds | `I3` | `gate/I3_new_test_with_where` | `gate/I3_ok_new_test_plain` |
| §3 Stage E step 3 — the diff and the pre-registration must both be readable | `C0` | `compare/C0_no_prereg` | `compare/C1_inside` |
| §3 Stage E step 3 — "a number is outside the declared interval" | `C1` | `compare/C1_row_delta_above_max` | `compare/C1_inside` |
| §3 Stage E step 3 — rows that exist in production and not in the new version | `C2` | `compare/C2_removed_pks_over` | `compare/C1_inside` |
| §3 Stage E step 3 — "a column shows a difference but is not in altered_columns" | `C3` | `compare/C3_undeclared_column` | `compare/C1_inside` |
| §3 Stage E step 3 — each metric against its declared interval | `C4` | `compare/C4_metric_outside` | `compare/C1_inside` |
| §3 Stage E step 3 — "the type is refactoring but some delta is not zero", in one line | `C5` | `compare/C5_refactoring_nonzero` | `compare/C1_inside` |
| §3 Stage E step 4 — "if the difference is greater than the tolerance, the PR is blocked" | `C6` | `compare/C6_over` | `compare/C6_ok_within` |
| §3 Stage E step 3 — every pre-registered model is compared, not only the ones whose numbers turned up | `C7` | `compare/C7_prereg_without_diff` | `compare/C1_inside` |
| §3 Stage E step 5 — "Is the pre-registration narrow enough to be able to fail? Does the reason justify the interval?" | `I2` | `compare/C1_inside` | `compare/C0_no_prereg` |

---

## 9. What v0 does not do

Everything below is part of the framework and **not** enforced by these tools.
Some of it is enforced by your platform settings, some of it is a rule for
humans, and some of it is simply not built yet. Knowing which is which is the
point of this list.

| Not enforced here | Why, and what to do about it |
| --- | --- |
| The lock itself: warehouse roles, masking, spending caps, statistical profiles | Controls 1 to 4 are platform settings, not scripts. `REVOKE USAGE ON SCHEMA raw` is the control; no Python can replace it. README §2. |
| The minimum row count test of Rule 2 | The test's name varies by team (`dbt_utils.expression_is_true`, a singular test, a package). Add its name to `ACCEPTED_PK_TESTS`' neighbourhood yourself, or ask for it in an issue. README §2 Rule 2. |
| Generating the statistical profile of Control 4 | It reads the warehouse. Generate it in a scheduled job and protect `docs/profile/` with CODEOWNERS. README §2 Control 4. |
| Dataset lifecycle: dropping `ci_pr_<n>_full` schemas | Warehouse housekeeping. A scheduled job, not a gate. README §3 Stage E. |
| "The pre-registration is immutable from the moment stage D begins" | That needs state outside git — CI has to remember when it first ran. `gate` counts the changes instead and prints the count (`I1`), which is what the README asks the Author to see. README §3 Stage B. |
| Running the reconciliation query | It reads the warehouse with full data. Your CI runs it and writes the two numbers into `diff.json`; `compare` reads them (`C6`). README §3 Stage E step 4. |
| Producing the diff | Warehouse-specific. Recce, dbt-audit-helper or your own SQL; the tools demand the shape, not the method. README §3 Stage E step 2. |
| A model changed only in its yml, in a way that moves numbers | `G8` asks for a pre-registration when a model's `.sql` changes, because Stage B ties the interval to writing code. A materialisation swapped, a `config` edited, a `+where` added in the yml alone can move numbers with the `.sql` untouched, and `G8` will not ask. README §3 Stage B. |
| A schema yml written with jinja | dbt renders yml through jinja before reading it; these tools use a plain YAML parser. A `{% for %}` that generates model entries, or an unquoted `{{ ... }}` in a value, is unreadable here, and an unreadable file is exit 2 for the whole run — fail closed, but the run is down until the file changes. The message names jinja as the cause so the reader is not hunting for a typo. Keep generated yml out of the marts paths, or render it in a pre-commit step. README §3 Stage A. |
| `compare` without `--base` | It cannot tell a pre-registration written for this pull request from one `main` already had, so every one in the project counts as this PR's: `C7` asks for a diff of every pre-registered model, and an inherited one is compared instead of refused. Stricter, never looser — but a local run can block for a model you never touched. Pass `--base`, as `templates/ci.yml` does. README §3 Stage B. |
| `gate` does not check that `--marts-path` exists | `check` and `compare` read the project directory, so a path that is not a directory is exit 2 — "nothing to check is not OK". `gate` reads git and never looks, so `gate --marts-path models/martz` walks the branch, finds no model yml under it, and prints `OK`. A typo in one of the two places the flag is written — the CI workflow and `AGENTS.md` ask for them to be identical — is a silent downgrade rather than an error. Until it is fixed, keep the flag in one place and copy it. README §3 Stage A. |
| A dbt project that is not at the git repository root | `gate` asks `git ls-tree` for paths and then `git cat-file` for their content; the first answers relative to the current directory and the second reads from the repository root, so in a `dbt/` subdirectory every read fails and the command is exit 2. Fail closed, so not a silent pass — but `gate` simply does not run in that layout, and `--project-dir` cannot save it. `spec.reconciliation_query` and the `CODEOWNERS` entry for `analyses/` disagree about the root in the same layout. README §2 Control 5B. |
| `T1` rejects a uniqueness test that is *stronger* than the primary key | The accepted `unique_combination_of_columns` must name exactly the spec's `primary_key`. A `unique` on one column of a two-column key is a stricter claim and still reads as "no uniqueness test on primary key". Add the form you use to `ACCEPTED_PK_TESTS`, or write the test the rule asks for as well. README §2 Rule 2. |
| `dbt_project.yml`, and severity set from it | `gate` reads the model yml, `tests/`, `analyses/reconciliation_*` and the package files. It does not read `dbt_project.yml`, so `data_tests: {+severity: warn}` or `+enabled: false` there turns every test in the project non-blocking and `gate` says `OK (no changes)`. CODEOWNERS protects the file (Control 5A) so a human must approve the change — but the gate will not be the one to tell them what it does. README §2 Control 5B. |
| `macros/` | Same list, same gap. dbt's custom generic tests conventionally live in `macros/`, and Rule 3 names "modifies a test macro" — the gate does not read them. CODEOWNERS covers the approval. README §2 Rule 3. |
| A spec **deleted** | `G7` fires when a spec *changes*; a spec removed outright trips no `gate` rule, and `check` catches only the symptom (`S1`, "model has no meta.spec"), which reads like a model that never had one. A pre-registration deleted alongside a model change is `G8` now; one deleted on its own, with the model untouched, still trips nothing. README §3 Stage A, Stage B. |
| History-shaped evasion of `G7` and `I1` | Both rules read the branch's history, so both depend on its shape. The walk uses `--first-parent`, which skips work done on a side branch and merged in: a spec created *and* edited inside such a branch passes `G7`, and `I1`'s count is understated. **Squashing is not the remedy** — this page used to say it was, and it is worse: a squash erases the intermediate commits outright, so for a spec first written on the branch `G7` has nothing to compare against and `I1` reports zero. Same content, three verdicts depending on branch topology, which sits badly with Principle 3. Until the walk changes: keep the pull request's commits, and read `I1` as a floor. A spec that existed on `main` is safe either way, because the merge-base is what `G7` compares it to. README §3 Stage B. |
| Each spec edge becoming a unit test (Rule 2) | The spec's `known_edges` are validated as text and nothing checks that each became a unit test with a synthetic fixture. A spec with five edges and no unit tests passes `check`. README §2 Rule 2. |
| Whether a tolerance or an anchor can fail | `reconciliation_tolerance: "999%"` and `external_validation: "TODO"` satisfy the schema. The same argument the pre-registration schema makes about open intervals applies to them; the schema does not make it yet. README §3 Stage A. |
| Detecting real data in fixtures (Rule 7) | These tools only check their own fixtures (meta-test M6). For your repository use gitleaks with rules for email and document numbers, as README §3 Stage D describes. |
| Bot-identity mode: judging only the agent's commits | There is no bot identity to configure, and a commit author is text anyone can write. The gate judges the whole pull request; see [Gate scope](#gate). |
| The `PreToolUse` hook that refuses writes to protected paths | Agent-specific and optional. README §2 Control 5B, "Optional (extra layer of protection)". |
| Judging natural language: whether a grain is *good*, whether a reason justifies an interval | Principle 3: an LLM is never the final judge. These are the human's three readings in Stage E step 5. |

---

## 10. How to contribute

- **One rule per pull request.** A rule is one function, one docstring that
  starts with the README sentence it enforces, one rule id, one fixture that
  blocks, one fixture that passes, and one row in the coverage table. The
  meta-tests fail if you forget one of the last three.
- **README first.** These tools may only enforce something the framework README
  says. If your rule needs the README to change, open a *Framework improvement*
  issue and change the README first. No sentence, no rule.
- **Fixtures are synthetic.** Invented data only. Emails end in `@example.com`;
  invented document numbers must fail their own check digit. Meta-test M6
  checks it, and the repository's PR checklist forbids real data anyway.
- **Both languages.** `tools/README.md` and `tools/README.pt-br.md` are the same
  document. If you change the substance of one, change the other, or say in the
  PR that you could not.
- **One file.** All the logic lives in `slp.py`, and meta-test **M8** caps it
  in three places: the **shared machinery** every rule depends on, **any one
  rule** on its own, and the file as a whole as a loose backstop. What it counts
  is the lines that have to be *understood* — code, with blanks, comments and
  docstrings taken out — because under a cap that counts prose, the cheapest way
  to buy room is to delete the explanation that makes the file readable.

  It used to be one global number, and that number stopped measuring the promise
  it was written for. A reader does not read twenty-four rules at once; they read
  the machinery once and then one rule at a time. Under a single cap every rule
  competed with every other rule, so it had quietly become a rule-count limit
  wearing a legibility limit's clothes — and the first time correctness needed
  room, the only honest move it offered was to delete a gate. Split, the pressure
  sits where it belongs: shared machinery is what everyone pays for, and a rule
  too long to read on its own is two rules with two ids and two fixtures. The
  numbers are re-measured at each release; one goes up only when the pull request
  says what was bought with it.

See [CONTRIBUTING.md](../CONTRIBUTING.md) and the issue templates in
`.github/ISSUE_TEMPLATE/`.
