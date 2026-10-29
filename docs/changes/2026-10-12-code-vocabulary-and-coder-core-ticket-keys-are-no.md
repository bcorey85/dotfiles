---
type: "Change"
change_type: "changed"
title: "code-vocabulary and coder-core: ticket keys are no longer banned from committed code"
description: "code-vocabulary and coder-core: ticket keys are no longer banned from committed code."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-12T00:00:00-05:00"}
seq: 4
kind: "behavior"
components: ["shared/code-vocabulary", "skill/coder-core"]
evidence: ["judgment"]
watches: []
---

## Change

code-vocabulary and coder-core: ticket keys are no longer banned from committed code

## Evidence

judgment

### Anchor reasons

Anchor `skills/_shared/code-vocabulary.md`, section `## The rule` (evidence: judgment):

Bans pipeline vocabulary (phase numbers, decision ids, plan paths, process narration) from committed code. Ticket keys are no longer on the list, by judgment.

Anchor `skills/_shared/code-vocabulary.md`, section `## Sweep before handing back` (evidence: judgment):

Diff-check against the banned table before reporting. Binds the criteria author and the code skill's criteria step; the hooks point here in their messages. The coders, the diff reviewer, and the test writer no longer load this file.

## Result

Rule only, no measure.

## Watch

—

## Back-out

restore the table row and the word in coder-core
