# `tools/` — reference implementation of the Spec-Lock-Diff gates

> **Work in progress.** These tools are the first, minimal, reference implementation
> of Spec-Lock-Diff. They are deliberately small. They will change. Adapt them to your
> warehouse, your CI and your team — that is expected, not a deviation. And if you
> improve them, bring the improvement back: open a *Field report* or a PR.
> We are building this together.

Nothing here is finished yet. The full documentation lands with the `check`, `gate`
and `compare` commands; until then, read the framework [README](../README.md) —
it is the source of truth these tools implement.

## What is in this folder

| Path | What it is |
| --- | --- |
| `slp.py` | The single file with all three commands. |
| `schemas/` | JSON Schemas for the spec, the pre-registration and `diff.json`. |
| `templates/` | Copy-paste files: `CODEOWNERS`, `AGENTS.md`, `ci.yml`. |
| `tests/` | The test suite and its fixtures. |
