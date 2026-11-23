---
type: "Change"
change_type: "fixed"
title: "review_fix decide keep rules an adopted plan impact the coder never applied"
description: "`decide keep` now re-rules a plan impact that was adopted and left unapplied, so the adopted-unapplied stop no longer holds the loop."
generated: {"by": "claude-code/claude-fable-5-1", "at": "2026-11-23T01:03:32-06:00"}
seq: 1
kind: "fix"
components: ["script/review-fix", "shared/review-loop"]
evidence: ["tests/scripts/test_review_fix_script.py"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest.test_decide_keep_rules_an_adopted_impact_the_hand_back_says_the_coder_never_applied"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

An adopted finding the coder reports as already in the tree is read as applied: it raises no critical blocker and is recorded as applied, so a relaunch after `decide adopt` on a change already made no longer stops. The coder brief tells the coder to write `ALREADY APPLIED <n>: <where>` for such an issue, and only when an issue is adopted (the `adopted_numbers` argument of `coder_prompt`). The loop reads the marker through `coder_report.already_applied_issues`, which wraps `coder_report.issue_marker_lines`. An `ALREADY APPLIED` line on an issue that is not adopted is filed as a skip with the coder's line as its reason (`review_loop_ruled.ordinary_already_applied_skips`).

`review_fix.py decide keep` accepts a plan impact whose latest ruling is `adopt` when the hand-back's `adopted_unapplied` lists the adopted ruling's text. It writes one newer `keep` row per distinct adopted text, which `latest_rows_per_text` reads as the ruling, so the review loop no longer hands the impact back as an adopted finding.

## Evidence

The coder's report may also carry `ALREADY APPLIED <n>: <file:line>` for an adopted issue whose change the tree already holds. `tests/scripts/test_review_loop_ruled.py::UnappliedAdoptedBlockersTest.test_an_adopted_finding_the_coder_reported_already_in_the_tree_is_no_blocker` fails without the `already_applied` read in `not_applied_why`.

The new test plants an adopt row and a hand-back packet whose `adopted_unapplied` lists the ruling, runs `decide keep`, then reads the rulings and the loop's unapplied check.

## Result

Before, `decide keep` refused with no waiting plan impact and the adopted-unapplied stop carried on every later run.

## Watch

—

## Back-out

Revert the `already_applied` argument of `not_applied_why`, `unapplied_adopted` and `settle_adopted_after_pass`, `coder_report.already_applied_issues` and `ALREADY_APPLIED_MARKER`, the `adopted_numbers` argument of `coder_prompt` with its coder-brief line (`review_loop_prompts.py`), `adopted_numbers` and `ordinary_already_applied_skips` (`review_loop_ruled.py`) with their calls in `review_loop_script.py`, the `row_impact_texts` argument of `write_ruling_entry` and the `row_per_text` field of `PlanImpactSource`, and `review_fix_adopted.py` and its call in `waiting_plan_impact_source`, the `adopted_unapplied` field of the loop outcome, packet and `handback.py` packet keys (`review_loop_ruled.py`, `review_loop_script.py`, `review_loop_packet.py`, `handback.py`).
