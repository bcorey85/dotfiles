---
type: "Change"
change_type: "changed"
title: "review-loop: when every finding the fix coder applied is a docs finding"
description: "review-loop: when every finding the fix coder applied is a docs finding, the loop dispatches no further review and no fix-diff check, and goes straight to the execution gate."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-02T00:00:00-05:00"}
seq: 1
kind: "behavior"
components: ["agent/review-loop"]
evidence: ["census"]
watches: []
---

## Change

review-loop: when every finding the fix coder applied is a docs finding, the loop dispatches no further review and no fix-diff check, and goes straight to the execution gate.

## Evidence

census

## Result

Removes the second review round after docs-only fixes, about 1 in 10 second rounds at work. No defect class is left unread: the skip applies only when no code finding was fixed.

## Watch

—

## Back-out

—
