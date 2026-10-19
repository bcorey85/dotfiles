---
type: "Change"
title: "The coder's core skill gained a block that tells the coder to check the plan against the code it names (104"
description: "The coder's core skill gained a block that tells the coder to check the plan against the code it names (104 words, 638 in all): open the definition of each existing type, function, or field that the plan describes, read the code that sets a value that the new code depends on."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-18T00:00:00-05:00"}
seq: 11
components: ["skill/coder-core"]
evidence: ["seeded round"]
watches: []
---

## Change

The coder's core skill gained a block that tells the coder to check the plan against the code it names (104 words, 638 in all): open the definition of each existing type, function, or field that the plan describes, read the code that sets a value that the new code depends on, and report a difference as a plan-impact finding even when a workaround exists, with only the untouched part built.

## Evidence

seeded round

## Result

On two planted mismatches between the plan and existing code, the coder flagged nearly every run with the block and about one run in four without it, and every flag carried the three fields. One mismatch showed only in the code that sets the field. Without the block, no run read that code, and every run shipped a bootstrap mean that counts aborted runs, with every held-out test green. With the block, the coder read that code in most runs and flagged the mismatch each time it did. No block appeared on a clean tree. The cost is about a quarter more coder tokens on a clean phase, from more tool calls, and most of it is cache reads. A flagged run builds only the untouched part, so the phase needs a second coder pass after the decision, and some flagged runs dropped the plan's fields from the types. On a clean tree the coder opened the definition in every run and the code that sets the fields in none, so the evidence on false stops from that second read rests on the seeded runs, where no report named a second difference.

## Watch

—

## Back-out

—
