---
type: "Change"
change_type: "changed"
title: "`review-commit-gate` asks the user to confirm a `git commit` while coder work from the session has no"
description: "`review-commit-gate` asks the user to confirm a `git commit` while coder work from the session has no converged review, in place of a block."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-16T00:00:00-05:00"}
seq: 3
kind: "behavior"
components: ["script/review-commit-gate", "script/review-gate-mark"]
evidence: ["judgment"]
watches: []
---

## Change

`review-commit-gate` asks the user to confirm a `git commit` while coder work from the session has no converged review, in place of a block. An internal error in the gate also asks in place of a block. The one-shot `review-gate-mark skip` override is deleted, because the permission prompt now carries that choice

## Evidence

judgment

## Result

Effect unmeasured. The user approves or denies the commit in one prompt, in place of a block, a question and a skip command the user ran by hand.

## Watch

—

## Back-out

restore `deny`, the skip file and the `skip` verb in the gate and in `review-gate-mark`
