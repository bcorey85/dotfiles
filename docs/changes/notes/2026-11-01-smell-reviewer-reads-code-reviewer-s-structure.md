---
type: "Change"
change_type: "changed"
title: "Smell-reviewer reads code-reviewer's structure rules instead of a copy"
description: "smell-reviewer drops from 1,026 to 464 words: it reads code-reviewer's Structure step at run time instead of carrying a near-verbatim copy, so the two lenses can no longer drift, and both now tag dead weight as fix."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-01T01:28:51-05:00"}
seq: 422
kind: "user-rule"
components: ["agent/smell-reviewer", "agent/code-reviewer"]
evidence: ["census"]
watches: []
test: ""
asked: "2026-11-01: after the overnight cut-candidate report: fix everything"
proof: []
unmeasured: ""
---

## Change

- `agents/smell-reviewer.md`: the copied structure rules (duplication forms, layer placement, naming, dead weight, cohesion, disposition, anti-churn, `[design-decision]`) are replaced by an instruction to read `~/.claude/agents/code-reviewer.md` from `### Step 3: Structure` through "Never audit pre-existing smells in surrounding code" and apply it within the dispatched bound. Within-file repeats go. The bound paragraph, scope list, calibration read and output format stay.
- Dead weight is now `fix` in both agents (smell-reviewer said `nit`).
- smell-reviewer now also applies code-reviewer's helper-placement rule, which its copy lacked.

## Evidence

Census: about 496 of smell-reviewer's words repeated code-reviewer lines 43-58, and the two disagreed on the dead-weight tag. Both run on the same large diff in the review loop.

## Result

Full dotfiles suite passes (2,923 tests, 0 failed). smell-reviewer now depends on code-reviewer's `### Step 3: Structure` heading and its closing sentence; renaming either breaks the read.

## Watch

None: the intake has no per-agent tag mix for smell-reviewer.

## Back-out

Revert the commit.
