# The quickstart project

A dbt project small enough to read in one sitting, complete enough that the
gates pass on it. Two marts — one `standard`, one `critical` — with their specs,
their pre-registrations, the reconciliation query the critical one owes, and the
`diff.json` files a Stage E build would have produced.

**You do not need dbt, a warehouse, a credential or a network connection.**
`check` reads yml and one line of sql; `compare` reads yml and json. Neither
calls dbt, and neither calls out.

From the root of this repository:

```
$ python tools/slp.py check --project-dir examples/quickstart
slp check: OK (2 models in models/marts/, of 4 models read)
```

Two numbers, and only the first is coverage: two models are held to the
framework because their sql is under `models/marts/`, and four were read in all
— `models/staging/schema.yml` declares two more that the framework does not ask
for a spec from. A green that means *"I did not look"* is the failure the
framework exists to prevent, which is why the second number is printed at all.

```
$ python tools/slp.py compare --project-dir examples/quickstart examples/quickstart/diff/*.json
INFO	examples/quickstart/diff/fct_invoices.json	fct_invoices	measured over invoice_date from 2025-01-01 to 2025-02-01	[C0]
INFO	examples/quickstart/diff/fct_invoices.json	fct_invoices	declared as a data_change, because: include invoices issued on the last day of the month	[I2]
INFO	examples/quickstart/diff/fct_invoices.json	fct_invoices	row_delta 312, declared 0..500 (a band 500 wide)	[I2]
INFO	examples/quickstart/diff/fct_invoices.json	fct_invoices	removed_pks 0, declared at most 0	[I2]
INFO	examples/quickstart/diff/fct_invoices.json	fct_invoices	metric invoiced_amount moved 0.03 percent, declared 0.0..0.1 (a band 0.1 wide)	[I2]
INFO	examples/quickstart/diff/fct_invoices.json	fct_invoices	altered columns measured [], declared []	[I2]
INFO	examples/quickstart/diff/fct_invoices.json	fct_invoices	reconciliation: model 1000000.0 against source of truth 1000200.0, a difference of 0.02 percent, and the spec allows 0.1%	[I2]
INFO	examples/quickstart/diff/fct_orders.json	fct_orders	measured over order_date from 2025-01-01 to 2025-02-01	[C0]
INFO	examples/quickstart/diff/fct_orders.json	fct_orders	declared as a data_change, because: include status='partially_shipped', which was excluded by mistake	[I2]
INFO	examples/quickstart/diff/fct_orders.json	fct_orders	row_delta 8400, declared 0..12000 (a band 12000 wide)	[I2]
INFO	examples/quickstart/diff/fct_orders.json	fct_orders	removed_pks 0, declared at most 0	[I2]
INFO	examples/quickstart/diff/fct_orders.json	fct_orders	metric gross_revenue moved 0.42 percent, declared 0.0..0.8 (a band 0.8 wide)	[I2]
INFO	examples/quickstart/diff/fct_orders.json	fct_orders	altered columns measured [gross_revenue], declared [gross_revenue]	[I2]
slp compare: 13 infos - OK
```

Nothing blocks, and thirteen lines say why. Those `I2` lines are the point of
Stage E: every number, the band that was declared for it *before the code was
written*, and how wide that band was. A band wide enough to swallow any result
is a finding about the author, not about the data.

## What to read, and in what order

| File | What it shows |
| --- | --- |
| `models/marts/fct_orders.yml` | A `standard` spec and its pre-registration, six mandatory fields each, with the rule that reads each one named in a comment |
| `models/marts/finance/fct_invoices.yml` | A `critical` spec: three more fields, because a model that feeds a financial report owes a reconciliation and a tolerance |
| `analyses/reconciliation_fct_invoices.sql` | The model compared with something that is not the model. One row out: metric, model value, external value |
| `diff/fct_orders.json` | What a diff producer must write. The keys mirror the pre-registration on purpose, so `compare` reads them key by key |
| `diff/fct_invoices.json` | The same, plus the `reconciliation` block a critical model needs |
| `.github/CODEOWNERS` | Why `fct_invoices` passes `S5`: a critical model has to be owned by somebody |
| `AGENTS.md` | What the agent is told the machines will do, so it does not spend a pull request finding out |

## Break it on purpose

The fastest way to understand a gate is to watch it fire.

- Delete `- unique` from `models/marts/fct_orders.yml` and run `check` again:
  `T1` blocks, because a primary key with no uniqueness test is a grain nobody
  is checking.
- Add `where: order_id is not null` under that `unique` test: `T1` blocks again,
  for a different reason — a test that filters away the rows that would fail it
  cannot fail the build.
- Change `max: 12000` to `max: 100` in the pre-registration and run `compare`:
  `C1` blocks, because the measured `row_delta` of 8400 is outside what was
  promised.
- Delete the `/models/marts/finance/` line from `.github/CODEOWNERS`: `S5`
  blocks, because a critical model nobody owns is a critical model nobody
  approves.
- Remove `reconciliation` from `diff/fct_invoices.json`: `C6` blocks, because a
  critical model without its two numbers was never reconciled with anything.

Put each one back and the run goes green again. Nothing here writes to your
project, and nothing here has to be undone anywhere else.

## What is not here

`gate` — it reads git, not the working tree, and a dbt project that is not at
the root of its repository makes it exit 2 on every read. It gets its own
folder: [`../gate-walkthrough`](../gate-walkthrough/README.md), which is two
commits and one deleted test.
