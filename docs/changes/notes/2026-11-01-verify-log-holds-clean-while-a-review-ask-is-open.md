---
type: "Change"
change_type: "fixed"
title: "verify-log holds CLEAN while a review ask is open"
description: "verify-branch no longer prints CLEAN while the branch review logged an ask on the same tree; it prints ASKS OPEN until the ask is ruled on or the code is fixed and reviewed again."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-01T02:36:55-06:00"}
seq: 428
kind: "fix"
components: ["script/verify-log", "script/verify-prep", "skill/verify-branch"]
evidence: ["defect report"]
watches: []
test: "tests/scripts/test_verify_branch_script.py::OpenAskTest::test_an_open_ask_on_the_reviewed_tree_is_not_clean"
asked: ""
proof: []
unmeasured: ""
---

## Change

`verify-log review` saves the review's open asks with the tree they cover, and verify-prep carries them forward. When the verdict rows hold no gap but an ask is open on the same tree, `verify-log --rows` prints ASKS OPEN with each ask, in place of CLEAN and the review packet. `--asks-ruled "<who, what, when>"` prints the user's ruling and lets the run print CLEAN. A later review of a changed tree replaces the asks. The verify-branch skill gains an "Asks open" route.

## Evidence

A verify-branch run where the code reviewer logged an ask saying the code contradicted a ticket criterion, the plan verifier marked that criterion done from the plan's reading, and verify-log printed CLEAN. The session had to override the verdict by hand; a session that trusted the CLEAN line would have handed over a merge line.

## Result

The new tests fail before the change (CLEAN printed, `--asks-ruled` unknown) and pass after. The plan-verifier prompt already says to verdict each ticket criterion from the ticket's own words and to mark a reworded one `missing` without a sign-off, so it is unchanged.

## Watch

—

## Back-out

Revert the commit; old saved contexts with no `reviewAsks` key print CLEAN as before.
