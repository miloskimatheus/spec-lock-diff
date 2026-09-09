## What does this PR change?

<!-- One or two sentences. -->

## Type of change

- [ ] Typo, broken link, or formatting fix
- [ ] Translation / language parity (porting a section between EN and pt-BR)
- [ ] Clarification — same rules, clearer wording
- [ ] Substantive change to the framework (new rule, changed rule, new control or stage)
- [ ] Reference implementation (schema, anti-fraud gate, CI template)

## Related issue

<!-- Substantive changes should link an issue discussed beforehand. Fixes #___ -->

## Language parity

`README.md` (English) and `README.pt-br.md` (pt-BR) are the same document.

- [ ] This PR does not change substance, so parity is unaffected
- [ ] Both versions are updated
- [ ] Only one version is updated — I cannot write the other language, and it needs a follow-up

## If this adds or changes a rule

> Principle 2: limits belong in the infrastructure, not in text instructions to the agent.

**Mechanism that enforces it:**

<!-- Which permission, CI gate, schema, or branch protection makes the rule real?
     If the answer is "the agent is told not to", the rule is not finished yet. -->

## If this changes `tools/`

**Which README sentence does this enforce?**

<!-- Rule R1: a tool may only enforce something the framework README says.
     No sentence, no rule — open a *Framework improvement* issue first. -->

**Which fixture proves it blocks, and which proves it passes?**

<!-- Every rule needs one fixture that blocks and one that passes.
     Meta-test M2 fails if a rule id has no fixture and no coverage-table row.
     A rule that only informs (INFO_RULES) has no healthy-and-silent case; its
     second fixture is one where the tool could not read the numbers at all. -->

**Can it pass something it should have looked at?**

<!-- The failure this framework exists to prevent is a green that means "I did
     not look". If the rule reads a list, ask what happens when something is
     missing from the list rather than wrong in it: a model with no yml, a diff
     that never arrived, a second test of the same name. Those were seven real
     bugs in v0.1.0, and every one of them printed OK. -->

## Checklist

- [ ] I read [CONTRIBUTING.md](CONTRIBUTING.md)
- [ ] No real data, credentials, internal table names, or production metric values are included
- [ ] Internal links and the table of contents still resolve
