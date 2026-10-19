---
type: "Change"
title: "Coder: before it writes a helper, it searches for code that does the same job"
description: "Coder: before it writes a helper, it searches for code that does the same job; a near fit is extended with an option its caller sets, existing callers and test expectations unchanged, never copied with a line changed."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-09T00:00:00-05:00"}
seq: 1
components: ["agent/coder"]
evidence: ["census", "bench round"]
watches: []
---

## Change

Coder: before it writes a helper, it searches for code that does the same job; a near fit is extended with an option its caller sets, existing callers and test expectations unchanged, never copied with a line changed

## Evidence

census, bench round

### Anchor reasons

Anchor `skills/coder-core/SKILL.md`, section `## Extend, never copy` (evidence: census, bench round):

Before a new helper, constant, type or block of logic, search for code that does the same job, call it if it fits, and extend it with a caller-set option if it is a line or two off, keeping every existing caller and test expectation. Work logs: 92 duplication-like escapes past review since July. Bench: copies fell from 12 of 15 to 4 of 15, held-out tests passed in every run, and old helper behavior held in every run. Cost: median coder tokens +8% with nothing to reuse, +49% with a near fit.

## Result

Work logs, dotfiles and agent-evals sessions excluded: 92 duplication-like escapes past review since July, 48 caught at the branch-end refactor pass. Bench, helpers one line off what the phase needs: copies 12 of 15 without the rule, 4 of 15 with it; held-out tests 14/14 in every run; old helper behavior kept in every run. An earlier wording without the keep-callers clause cut copies to 0 of 15 but rewrote a helper's behavior and its tests in 1 of 5 runs. Cost: median coder tokens +8% when nothing exists to reuse, +49% when a near fit exists. Effect on work: watch duplication-class escapes at the refactor pass.

## Watch

—

## Back-out

restore `skills/coder-core/SKILL.md` from git
