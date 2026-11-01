---
type: "Change"
change_type: "removed"
title: "Review fix drops the plan-impact status route the loop no longer emits"
description: "review_fix.py loses about 40 lines that served a packet status the review loop stopped emitting. Plan impacts now reach the user only through the plan_impacts list on a converged or capped packet."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-31T20:47:22-05:00"}
seq: 412
kind: "fix"
components: ["script/review-fix"]
evidence: ["tests"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest::test_plan_impact_prints_the_modal_and_decide_builds_the_redispatch_with_both_counters"
asked: ""
proof: []
unmeasured: ""
---

## Change

`review_fix.py` no longer routes a packet whose status is `plan-impact`. These are deleted: `present_plan_impact`, the adopt-by-rule path `adopt_code_side_for_review` with its `ADOPT_NO_PLAN_LINE`, the `adopted_deviations` carry-over in the fix state, and the "Plan deviations adopted" closing section. `record_plan_ruling` loses the `user_lines` and `no_plan_line` parameters that only that path passed. `saved_handback.dispatched_with_ruling` had no other caller, so it is deleted too, with the dispatch row's `resolved_plan_impact` field it read.

These stay: the `plan_impacts` route (`present_plan_impacts`), `decide`, and `defer`. The packet parser in `handback.py` still accepts the `plan-impact` status, because shared packet fixtures and other test files use it. Such a packet stops at a `plan-impact` entry in `STOP_STATUSES`, which presents the `plan_impact` text and waits for direction.

## Evidence

The review loop reports plan impacts as `plan_impacts` entries on a converged or capped packet. It never writes the `plan-impact` status. The deleted code could run only on a hand-written packet.

## Result

The shared `PLAN_IMPACT` test fixture is now a converged packet that holds one plan impact that changes an acceptance criterion. The tests that drive `decide` pass through the kept route. Nine tests that pinned only the deleted route are removed. 777 review tests pass and ruff is clean.

## Watch

None. Deleting code that cannot run changes no number the intake reads.

## Back-out

Revert the commit.
