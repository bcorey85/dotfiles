---
type: "Change"
change_type: "fixed"
title: "The hand-back hook denies a packet that names the plan file"
description: "A review-loop packet whose files_touched names the plan file is denied before delivery, and the stop gate skips its plan check once a hand-back was delivered."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T01:30:00-05:00"}
seq: 142
kind: "fix"
components: ["script/handback", "script/review-loop-gate", "agent/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_handback.py::OneCheckedHandBackTest::test_a_hand_back_whose_files_touched_names_the_plan_file_is_denied_with_the_plan_edit_reason"
asked: "2026-10-28: agent-evals-64 assigned queue item review-loop-stop-gate-asks-a-delivered-loop-for-a"
proof: []
unmeasured: ""
---

## Change

- `handback.plan_edit_reason`: the SubagentHandback hook denies a review-loop packet of any status but plan-impact
  whose files_touched names the dispatch prompt's plan file. The reason is `review_loop_gate.PLAN_EDIT_REASON`, so
  the loop reverts the edit and hands back `status: plan-impact`. The packet is not recorded. A transcript the hook
  cannot read never blocks.
- `review_loop_gate.plan_edit_reason` holds the check both gates use. `ledger_reasons` skips it once a hand-back was
  delivered.
- `review-loop.md` names the hand-back hook as the gate on a packet that names the plan file.
- The branch carries `fix/review-loop-single-handback`, whose change file is renumbered to seq 141 for the shared
  seq 135.

## Evidence

- After a delivered hand-back, the stop gate still blocked a packet that named the plan file and asked for a
  plan-impact hand-back. The hand-back hook denies every second hand-back from the same agent, so the plan impact
  never reached the caller.
- The new test_handback.py and test_review_loop_gate.py tests fail on the old scripts.

## Result

- A packet that names the plan file is denied before delivery, while a plan-impact hand-back still works. A
  delivered loop's stop is not blocked on the plan file.

## Watch

—

## Back-out

Revert the commit.
