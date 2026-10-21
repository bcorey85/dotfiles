---
type: "Change"
title: "The branch recap writes no receipt, not clean, when the test audit left no receipt"
description: "The recap sheet and the recap telemetry row now say \"no receipt\" when no /test-audit receipt is in context. Before, the recap wrote \"clean\" with no audit behind it."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-21T07:41:25-05:00"}
seq: 4
components: ["skill/branch-recap"]
evidence: ["work incident"]
watches: []
---

## Change

- `skills/branch-recap/SKILL.md`, the "Cross-phase test audit" line of the recap: write "no receipt" when no /test-audit receipt is in context, and never "clean" without one.
- The same file, the telemetry row: the `test_audit` field takes a fourth value, `no receipt`.

## Evidence

Work incident: a /code run of the recap phase logged `test_audit` "clean" with no audit receipt in its context. The real audit of that branch had 9 findings. A "clean" with no audit behind it is a false done that a reader acts on.

## Result

Edited 2026-10-21. No intake script reads the `test_audit` field, so the new value breaks no count.

## Watch

None. A work-log watch needs the share of recap rows with `no receipt`, and no intake metric reads `branch-recap-receipts.jsonl` by value.

## Back-out

Remove the "no receipt" clause from both places in the skill.
