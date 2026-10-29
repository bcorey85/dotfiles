---
type: "Change"
change_type: "changed"
title: "The branch-exit residue step now tells \"nothing left unstaged\" apart from \"no diff to classify\""
description: "The branch-exit residue step now distinguishes \"nothing left unstaged\" from \"the classifier had no diff to read\"."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-08-08T00:00:00-05:00"}
seq: 29
kind: "behavior"
components: ["skill/branch-recap"]
evidence: ["census"]
watches: []
---

## Change

The branch-exit residue step now distinguishes "nothing left unstaged" from "the classifier had no diff to read"

## Evidence

census

## Result

The tiering needs a diff; an all-new file gives it none, and its silence printed identically to a clean tree. The same file already carried this guard for its coverage check — report the denominator, because a check that cannot fail has not passed — and it had never been applied to the step beside it

## Watch

—

## Back-out

—
