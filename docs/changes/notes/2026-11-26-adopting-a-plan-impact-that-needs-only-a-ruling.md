---
type: "Change"
change_type: "fixed"
title: "Adopting a plan impact that needs only a ruling settles the review"
description: "decide adopt on a held plan impact that changes no acceptance criterion and has plan cause ends done, records the ruling as applied, and the push check counts the review clean, with no re-dispatch."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-26T02:55:30-06:00"}
seq: 2
kind: "fix"
components: ["script/review-fix", "script/handback"]
evidence: ["tests/scripts/test_review_fix_script.py"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest::test_decide_adopt_through_the_packet_of_a_ruling_only_impact_settles_with_no_pending_ruling"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`handback.adopt_settles` now settles when every held plan impact is applied or needs only the ruling (`needs_only_ruling`: no acceptance-criterion change and cause `plan`), and the packet carries nothing. Both `decide` paths (packet state and hand-back) compute the settle before writing the ruling, and `write_ruling_entry(applied=True)` records each ruled row as applied too, so `handback_store.rulings(...).adopted` no longer hands it to a later fix pass. `APPLIED_ADOPT_LINE` names both cases.

## Evidence

The two settle tests (packet path and hand-back path) fail before the change: decide re-dispatched (or stopped for the caller's loop) and the adopted ruling stayed pending, which the relaunched coder skipped and the loop stopped on as a NOT_APPLIED blocker with a repeat ask. Impacts with an unparsed cause or carried findings still do not settle.

## Result

A held plan impact whose adopt only records the ruling ends `ACTION: done`, the Plan Deviations line is written, the push check counts the review clean, and no later launch hands the coder the ruling.

## Watch

None.

## Back-out

Revert the commit.
