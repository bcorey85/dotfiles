---
type: "Change"
change_type: "changed"
title: "Committed code may now contain ticket keys"
description: "The coder may write ticket keys into committed code; the shared code vocabulary and the coder core no longer ban them."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-12T00:00:00-05:00"}
seq: 4
kind: "behavior"
components: ["shared/code-vocabulary", "skill/coder-core"]
evidence: ["judgment"]
watches: []
---

## Change

Committed code may now contain ticket keys. Before, code-vocabulary and coder-core banned them.

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
