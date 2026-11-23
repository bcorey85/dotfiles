---
type: "Change"
change_type: "fixed"
title: "review_fix decide keep rules an adopted plan impact the coder never applied"
description: "`decide keep` now re-rules a plan impact that was adopted and left unapplied, so the adopted-not-applied blocker stops carrying."
generated: {"by": "claude-code/claude-fable-5-1", "at": "2026-11-23T01:03:32-06:00"}
seq: 1
kind: "fix"
components: ["shared/review-loop"]
evidence: ["tests/scripts/test_review_fix_script.py"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest.test_decide_keep_rules_an_adopted_impact_the_hand_back_says_the_coder_never_applied"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`review_fix.py decide keep` accepts a plan impact whose latest ruling is `adopt` when the current hand-back carries the adopted-not-applied blocker for it. It writes a newer `keep` row, which `latest_rows_per_text` reads as the ruling, so the review loop no longer hands the impact back as an adopted finding.

## Evidence

The new test plants an adopt row and a hand-back with the blocker, runs `decide keep`, then reads the rulings and the loop's unapplied check.

## Result

Before, `decide keep` refused with no waiting plan impact and the blocker carried on every later run.

## Watch

—

## Back-out

Revert `review_fix_adopted.py` and its call in `waiting_plan_impact_source`.
