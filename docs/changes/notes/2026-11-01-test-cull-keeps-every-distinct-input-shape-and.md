---
type: "Change"
change_type: "fixed"
title: "Test cull keeps every distinct input shape and names the surviving twin"
description: "The test-intent reviewer never culls a test whose input shape differs from every sibling, and each cull names the surviving test. Audits that kept all such tests rose from 3 of 8 to 8 of 8."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-01T22:42:48-06:00"}
seq: 460
kind: "structured"
components: ["agent/test-intent-reviewer"]
evidence: ["bench"]
watches: []
test: ""
asked: ""
proof: ["2026-11-01-a-cull-rule-keeps-tests-with-a-distinct-input"]
unmeasured: "The work logs carry no row for a culled test's input shape, so no intake number can read this edit."
impact: {"metric": "quality", "before": 3, "after": 8, "unit": "of 8 audits kept every distinct-shape test", "finding": "2026-11-01-a-cull-rule-keeps-tests-with-a-distinct-input", "better": "higher"}
---

## Change

Step 4 of `claude/.claude/agents/test-intent-reviewer.md` gains one rule: a test that sends the unit a different input
shape from every sibling is never a CULL, and every CULL names as `file:line` the surviving test with the same input
shape.

## Evidence

Bench, rule on against rule off, under a prompt that pushes for a smaller suite.

## Result

Audits that kept every distinct-shape test rose from 3 of 8 to 8 of 8. The user signed off this fix on 2026-11-01 and
asked for the meter run.

## Watch

None. See `unmeasured`.

## Back-out

Delete the one line from Step 4.
