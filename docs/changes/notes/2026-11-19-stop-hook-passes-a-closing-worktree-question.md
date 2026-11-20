---
type: "Change"
change_type: "fixed"
title: "stop hook passes a closing worktree question"
description: "The Stop hook's permission-question check lets through a closing question that asks to make a worktree, a step the orchestration rule requires a yes for."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-19T02:32:04-06:00"}
seq: 5
kind: "fix"
components: ["script/staged-claim-gate", "script/permission-question"]
evidence: ["stop-hook-blocks-the-worktree-question-that-the"]
watches: []
test: "tests/scripts/test_staged_claim_gate.py::PermissionQuestionTest::test_a_question_naming_a_worktree_passes_on_the_first_try"
asked: ""
proof: []
unmeasured: ""
---

## Change

`gates/permission_question.py` counts making a worktree as a step to ask about. `REASON` names a step a rule requires
a yes for.

## Evidence

The orchestration rule says to ask before making a worktree when the branch has active work. The Stop hook sent that
question back.

## Result

A main-session Stop after the prompt "go" that ends "Want me to make a worktree for this?" passes on the first try.
A question that only mentions a worktree is still sent back.

## Watch

None.

## Back-out

Revert the commit.
