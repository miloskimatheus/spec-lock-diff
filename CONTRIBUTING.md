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
