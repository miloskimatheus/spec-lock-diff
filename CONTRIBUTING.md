# Contributing to Spec-Lock-Diff

Thanks for taking an interest. This repository is a **framework specification** —
mostly prose, plus the schemas and scripts that make its gates enforceable.
Contributions of both kinds are welcome.

> Contributions in **English or Portuguese (pt-BR)** are equally welcome.
> Contribuições em **inglês ou português (pt-BR)** são igualmente bem-vindas.

## Ways to contribute

| I want to…                                             | Do this                                                                 |
| ------------------------------------------------------ | ----------------------------------------------------------------------- |
| Ask something, or flag a passage that is unclear       | Open a **Question / unclear passage** issue                             |
| Propose a change or addition to the framework          | Open a **Framework improvement** issue first, then a PR                 |
| Share what happened when you implemented it            | Open a **Field report** issue — these are the most valuable input       |
| Fix a typo, broken link, or formatting bug             | Open a PR directly, no issue needed                                     |
| Port a section to the other language                   | Open a PR directly                                                      |

For anything that changes the *substance* of the framework — a new control, a new
stage, a changed rule — please open an issue before writing the PR. It is cheaper
to disagree about an idea than about a diff.

## Opening a pull request

1. **Fork** the repository and create a branch from `main`.
2. Make your change. Keep the commit history readable; squash noise before pushing.
3. **Keep the two languages in sync.** `README.md` (English) and `README.pt-br.md`
   (pt-BR) are the same document. If you change the substance of one, change the
   other too. If you cannot write the other language, say so in the PR description —
   that is fine, and the gap will be tracked.
4. Open the PR against `main` and fill in the template.

`main` is protected: it cannot be force-pushed or deleted, and contributor changes
land through pull requests from a fork. Only the maintainer can merge.

## Working on `tools/`

```bash
pip install -e ".[dev]"   # or: pip install pyyaml "jsonschema>=4" pytest
pytest tools/tests -q     # around three hundred and seventy, ten seconds, no network
```

The suite is most of the review. Before you open a pull request that touches the
tools, this is what it will ask of you:

| If you… | You also need |
| --- | --- |
| add a rule | a function whose docstring opens with the framework sentence it enforces (`README §n`), a rule id, one fixture that blocks and one that passes, a row in the tools README's rule table, and a mention in the changelog — **M1**, **M2** |
| add an import | it in the allowlist (**M3**) *and* in `pyproject.toml`'s dependencies. One decision in two files, and a test that fails until they agree |
| change what a command prints | the pinned output in `examples/*/README.md`, compared character for character |
| change a template | the assertions in `tests/test_templates.py`, which parse the file rather than reading it |
| change the tools README | the same change in `README.pt-br.md` — **R10** checks section numbering, rule order, and every line the tool itself prints |
| write more code | room under **M8**, which caps the shared machinery, any one rule, and the file. Raising a number is allowed; the pull request has to say what was bought with it |
| release | `__version__`, the `## <version>` heading in `CHANGELOG.md`, and the version in `pyproject.toml`, held together by one test |

A fixture folder is the unit of a test. Its name is the assertion —
`<RULE>_<what_happens>` must block, `<RULE>_ok_<what>` must pass — and a
`README.txt` beside it can be more precise (`expect exit 0`, `expect rules I1 G1`,
`expect absent G2`, `expect count 2`). So adding a rule means adding folders, and
never editing `test_check.py`, `test_gate.py` or `test_compare.py`.

`python assets/generate.py` writes every drawing in the READMEs — both themes,
both languages. It is deterministic: a run that changes nothing rewrites nothing.

## Style

- Prose over jargon. The framework is meant to be readable by an analytics engineer
  who has never heard of it.
- Every rule should name **the mechanism that enforces it**, not just the intent.
  A rule with no mechanism is a suggestion — that is the framework's own Principle 2,
  and it applies to the document about the framework too.
- Tables for anything enumerable. They survive translation better than paragraphs.
- Keep line-level Markdown simple: no HTML beyond the header image.

## Scope

In scope: the Spec / Lock / Diff phases, the 5 setup controls, the 5 PR stages,
post-merge maintenance, and reference implementations of the gates
(JSON Schemas, the anti-fraud gate, CI templates).

Out of scope: general dbt style guides, general data quality tooling, and anything
that is not specific to a **non-human** author writing the SQL.

## Code of conduct

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

Contributions are accepted under the [MIT License](LICENSE) that covers this project.
