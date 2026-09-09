# Changelog — `tools/`

Versions are tagged `tools-v<version>`. The framework README is versioned
separately; these tools implement it and never lead it.

## 0.3.0 — the shape of the project, not the shape of the fixtures

0.2.0 closed the silent passes the rules had. This one closes the silent passes
the *fixtures* had: every `check` and `gate` fixture kept a model's yml beside
its sql inside `models/marts/`, and every rule that asks "is this a marts
model?" was really asking "is this yml under marts?". Each entry below has a
fixture that fails against 0.2.0.

### New rules

| Rule | What it blocks |
| --- | --- |
| `G8` | a model whose **sql changed on this branch** and which carries no `meta.pre_registration`. Stage B was opt-out: `check` validated a pre-registration only when it found one, no `gate` rule watched for its absence, and `C7` iterates the models that *have* one — so an agent that rewrote a model and deleted its own pre-registration passed all three commands, and `compare` never so much as named the model. Deleting the prediction was cheaper than missing it |
| `I3` | nothing. It shows every test this branch **adds** that carries a `where`, because such a test has no earlier self to be weaker than and `G2` therefore never looked at it — and because a filter may be honest scoping or may be the rows that would have failed, which is a reading and not a measurement |

### Changed behaviour

- **`G3` holds a test the branch adds to the same line as one it edits.** A test
  born `enabled: false`, `severity: warn`, or with an `error_if`, `warn_if`,
  `fail_calc` or `limit` now blocks, exactly as a downgrade of an existing test
  does. `limit` was checked nowhere at all, on new tests or old, while `T1`'s
  own `MUTE_KEYS` had listed it as a mute since 0.2.0: `limit: 0` added to an
  existing `accepted_values` returned no rows, reported a pass, and `gate` said
  `OK`. The two lists are one predicate now — `_muted()` — used by `T1` and by
  `G3`, with `where` held apart in `DEAD_KEYS` because it is the one key that
  might be scoping rather than evasion.

- **The setup instructions install what the tools actually need.** They said
  `pip install pyyaml jsonschema` with no floor, while `templates/ci.yml` pinned
  `jsonschema>=4` — so the machine a reader set up from the README was not the
  machine CI was. The schemas are draft 2020-12 and its validator arrived in
  jsonschema 4.0; on 3.x the tools do not start. A test now holds the README and
  the workflow to the same floor, and a second holds the rule count in both
  READMEs to the length of `RULE_IDS`. The first step also says to read
  `python3` for `python`, which is the first command a reader on most Linux
  distributions runs and the first one that fails.

- **`C5` informs instead of blocking.** A `refactoring` has every interval
  pinned to zero by the pre-registration schema, so `C1` to `C4` already refuse
  every number `C5` could catch — it could never be the only rule that noticed,
  and a reviewer read `2 blocks` for one problem. It stays, because naming the
  promise in one line is worth reading; it is the fourth entry in `INFO_RULES`
  and the only one whose id does not start with `I`, since it was written to
  block. A test holds the argument: if a schema change ever makes `C5` the last
  line of defence, that test fails.

- **An unparseable yml says whether jinja is why.** dbt renders yml through
  jinja before reading it and these tools use a plain YAML parser, so a
  `{% for %}` that generates model entries takes the whole run down with
  `cannot parse ... found character '%'` — which reads like a typo and is not
  one. The message names the cause now, and the limitation is in section 9,
  where it should have been all along.

- **`gate` reads one commit in one git process.** It ran `git show` once per
  file per commit: 150 models across a 30-commit branch spawned 4,983 git
  processes and spent 19.5 s on a local SSD before a rule had looked at
  anything, and the cost is the product of the two numbers, so a real project
  with a long branch is worse. `git cat-file --batch` answers a whole commit
  down one pipe — the same repository is now 64 processes and 5.0 s. Blob sizes
  in that stream are counted in bytes, so it is split before decoding; a test
  covers the multibyte case that gets wrong.

- **M8 is three caps, not one.** The shared machinery, any one rule on its own,
  and the file as a whole. One global number had stopped measuring the promise
  it was written for — a reader reads the machinery once and then one rule at a
  time — and had quietly become a rule-count limit: every rule competed with
  every other rule and with the prose explaining them, so the first fix that
  needed room was offered "delete a gate" as the honest answer. The numbers are
  re-measured at each release.

### Rules that were not doing what they said

| Rule | What was wrong |
| --- | --- |
| `G1`, `G2`, `G3` | 0.2.0 gave every declaration of a same-named test its own config, keyed by its arguments. Two declarations whose **arguments** are identical too — two `dbt_utils.expression_is_true` on one expression, with a `where` each, which is how a team scopes one assertion to two statuses — still collapsed, and the second still overwrote the first. Remove one of the pair and `gate` printed `OK (1 commit)`; remove the other and it printed a `G2` naming a `where` that had been there all along. Declarations are held as a bag under their key now and compared as one |
| `S1`, `T1`, `G7` | a model was held to be in marts when the **yml that declares it** was, not when the **sql that makes it** was. A project with one `models/schema.yml` — which is what `dbt init` scaffolds — had every marts model exempted: no spec demanded, no uniqueness test demanded, and a `meta.spec` the agent rewrote on the branch produced `slp gate: OK`. `S4` did not rescue it either, because the model *was* declared, just elsewhere |

## 0.2.0 — the silent passes

Every finding below was a run that printed `OK` while the thing it exists to
check had not happened. That is the failure this framework was built to
prevent, and the tools had seven of them. Each has a proof in
`tests/fixtures/` that fails against 0.1.0.

### New rules

| Rule | What it blocks |
| --- | --- |
| `S4` | a `.sql` file in a marts path that no yml declares as a model. `check` read yml and nothing else, so a model that existed only as SQL had no spec to be missing and no test to be absent — Stage A was bypassed by leaving a file out rather than by weakening anything |
| `C7` | a model that carries a `meta.pre_registration` and whose `diff.json` was never handed to `compare`. `compare` only ever looked at the files it was given, so a diff step that emitted two files for three models passed. Pass every diff in one call — `compare diff/*.json` — because a rule about what is missing can only see what it was given |
| `I2` | nothing, and that is the point. It prints every number the diff measured next to the band the pre-registration declared for it, how wide that band is, the reason given, and a note when the diff carries no `window`. Stage E step 5 asks the Author "is the pre-registration narrow enough to be able to fail?", and until now the automation answered with a blank line |

### Rules that were not doing what they said

| Rule | What was wrong |
| --- | --- |
| `G1`, `G2`, `G3` | tests were grouped by (model, column, name) with **one** config per group — whichever sorted first by arguments. A column with two `relationships` tests is ordinary dbt, and every one but the first could be given a `where`, a `severity: warn` or an `enabled: false` unseen. The verdict depended on alphabetical order of the arguments. Each declaration now keeps its own config, and the finding names which one it means |
| `G1`, `G4` | unit tests were held in a dict keyed by name. dbt only makes a unit test unique *inside its model*, so two marts may each have one called `cancelled_orders_are_excluded`; whichever file sorted later overwrote the other and neither rule could see the first model's test change **or be deleted**. `gate` reported `OK (no changes)`. Keyed by `(model, name)` now |
| `T1` | `unique` with `where: "1 = 0"` satisfied the primary key requirement. `_blocks()` read `enabled` and `severity` and nothing else, so a mandatory test could be born asserting nothing — and no `gate` rule covered it either, because `G2` and `G3` compare a test against its earlier self and a new test has none. `where`, `error_if`, `warn_if`, `fail_calc` and `limit` now disqualify it, and the message says which one it found |

### Changed behaviour

- **`--marts-path`**, repeatable, on all three commands. `models/marts/` was
  hard-coded in three places. A project with marts in more than one directory
  got a clean run that had checked only one of them.
- **`check`'s summary line** counted every model it read, marts or not:
  `OK (40 models)` when three were in scope. It now reads
  `OK (3 models in models/marts/, of 40 models read)`. Only the first number is
  coverage.
- **Findings sort** blocks before infos, then by rule id, and ties keep the
  order the rule produced them in — so `I2`'s lines read in the order Stage E
  asks for rather than alphabetically.
- **`INFO_RULES`** names the rules that never change the exit code (`I1`,
  `I2`), and meta-test **M2** checks that against the source.
- **`COMPARE_RUN_RULES`** is a second registry for rules that judge the run
  rather than one file. Same docstring, rule id and fixture rules apply.
- **M8** caps the lines that have to be *understood* — code, with blanks,
  comments and docstrings taken out — at 750, and the file as a whole at 1000.
  The old cap counted every line, which made deleting explanatory prose the
  cheapest way to buy room.

### Still not enforced

The seven above are fixed. Three more were found with them and are **not**:
`dbt_project.yml` is never read, so `data_tests: {+severity: warn}` disables
every test in the project unseen; the `--first-parent` walk lets `G7` and `I1`
be evaded or undercounted by doing the work on a merged side branch; and a
deleted `meta.spec` trips no `gate` rule (`check` catches the symptom via
`S1`). They are listed in README section 9 with the rest.

## 0.1.0 — first reference implementation

Three commands in one file, no model, no network, no warehouse.

### `check` — the spec (README §3 Stage A, §2 Rule 2)

| Rule | What it blocks |
| --- | --- |
| `S1` | a model under `models/marts/` with no `meta.spec` |
| `S2` | a spec that does not match `schemas/spec.schema.json` |
| `S3` | a primary key or sensitive column the model does not declare, a model with no columns at all, a `meta.sensitive` flag missing from the spec or missing from the column, a critical model whose reconciliation query does not exist |
| `P1` | a pre-registration that does not match `schemas/pre_registration.schema.json`, including the open interval the README calls invalid |
| `P2` | a min above its max, a metric the spec never defined, a spec metric with no interval, an altered column the model does not declare, a pre-registration on a model with no spec |
| `T1` | no uniqueness test on the spec's primary key, or one that cannot fail the build |

### `gate` — the lock (README §2 Control 5B, §1 Principle 1)

| Rule | What it blocks |
| --- | --- |
| `G1` | a data test removed, its arguments changed or disabled; a file under `tests/` deleted or rewritten; a unit test removed |
| `G2` | a `where` added to or changed on an existing test, written on the test or in its `config` |
| `G3` | an existing test downgraded to `severity: warn`, an `error_if` / `warn_if` / `fail_calc` added or changed, or a new test created that cannot block |
| `G4` | any part of an existing unit test's body: `given`, `expect`, `overrides`, the model. Only `description` may change |
| `G5` | a reconciliation query changed in the same range as the model it checks |
| `G6` | `packages.yml`, `package-lock.yml` or `dependencies.yml` changed |
| `G7` | `meta.spec` changed after it was first written on the branch |
| `I1` | nothing. It counts how many times a pre-registration was edited and prints the count, which is what README §3 Stage B asks the Author to see |

### `compare` — the diff (README §3 Stage E)

| Rule | What it blocks |
| --- | --- |
| `C0` | a `diff.json` that does not match `schemas/diff.schema.json`, names a model that does not exist, or measures a model with no valid pre-registration. Prints the window when the diff declares one |
| `C1` | `row_delta` outside its declared interval, ends included |
| `C2` | more removed primary keys than the ceiling |
| `C3` | a column that changed without being declared. A declared column that did not change is an INFO |
| `C4` | a pre-registered metric that was not measured, one outside its interval, one that cannot be evaluated because production is 0, and one measured but never pre-registered |
| `C5` | a `refactoring` that moved any number |
| `C6` | a critical model with no reconciliation numbers, numbers with no tolerance to read them against, and a difference above the tolerance |

### Also in this release

- `schemas/spec.schema.json`, `schemas/pre_registration.schema.json`,
  `schemas/diff.schema.json` — draft 2020-12, every field describing itself in
  the sentence the tool prints when it is wrong.
- `templates/CODEOWNERS`, `templates/AGENTS.md`, `templates/ci.yml`.
- `README.md` and `README.pt-br.md`, the same document in two languages.
- A test per fixture folder, plus meta-tests M1 to M8: README references,
  coverage, the import allowlist, no network, fixture hygiene, determinism and
  file size.

### Known deviations from the backlog that planned this

- `slp.py` is about eight hundred lines, not the six hundred the backlog's rule
  R6 set before the rules were counted. M8 checks the honest number. The
  promise the cap protects — one person reads the whole thing in one sitting —
  still holds.
- `G3` blocks a *new* test that cannot fail, `G4` compares a unit test's whole
  body, and `G7` exists at all: three behaviors the README's Control 5B table
  does not literally list. Each has a *Framework improvement* issue open.
