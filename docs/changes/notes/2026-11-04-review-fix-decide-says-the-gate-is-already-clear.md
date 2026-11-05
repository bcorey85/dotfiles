---
type: "Change"
change_type: "fixed"
title: "review_fix decide says the gate is already clear and where the ruling goes"
description: "When no plan impact waits in this session's packet, `review_fix.py decide` says the commit gate is already clear (a defer clears it too), that the ruling goes in the plan's decision log by hand, and that decide reads only this session's packet."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-04T23:55:57-06:00"}
seq: 10
kind: "fix"
components: ["script/review-fix"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest::test_decide_after_a_defer_says_the_gate_is_clear_and_where_the_ruling_goes"
asked: ""
proof: []
unmeasured: ""
---

## Change

`command_decide` keeps its exit and stop; only the usage message changes. It names the cleared gate, the `defer` route, the decision log (`03-decisions.md` or `## Plan Deviations`) and the per-session packet. No option is added: `review_fix.py` is over 1000 lines.

## Evidence

judgment: a worker ran `defer` and then `decide keep` for an orchestrator's ruling, got "no plan-impact is waiting", and had to guess where the ruling went. The new test fails on the base commit and passes after.

## Result

`test_review_fix_script.py` 170 of 170 pass; lint clean.

## Watch

—

## Back-out

Restore the one-line message and remove the test.
