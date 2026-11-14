---
type: "Change"
change_type: "fixed"
title: "Review fix: a plan impact the user ruled on is left out of the fix run and does not come back as an ask"
description: "decide adopt, decide keep and an accepted plan-impact ask record the impact text in the hand-back store; a later fix launch drops a plan-change finding that text settles, and a skipped one in the packet stays skipped instead of becoming an ask."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-13T14:00:00-06:00"}
seq: 3
kind: "fix"
components: ["script/review-fix", "script/review-launch", "script/handback-store", "script/script-utils", "script/plan-format", "script/verify-log", "script/verify-common"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest::test_asks_done_then_decide_adopt_then_the_fix_round_has_no_ask_and_no_plan_impact"
asked: ""
proof: []
unmeasured: ""
---

## Change

`review/handback_store.py` gains `record_ruled_impact` and `rulings` (a `Rulings` with `.impacts` and `.finding_texts`, read from a `plan-impact-ruled` row, scoped to
the repo that was reviewed, that never clears the commit gate). `plan_format.criterion_ids_in` is the one reader of
criterion ids for `criteria_ids`, `verify_common` and `verify-log`; it reads the ids through `AC_REFERENCE`, so an
id is an upper-case `AC<n>` that stands alone and a `ticket AC<n>` is left out: `ac3-evidence.md`, `test_ac1_x`, `xAC1`
and `AC1_` no longer count. `review_fix.py` `write_ruling_entry` and `review_fix_asks.py` write the row for adopt, keep
and each accepted plan-impact ask. `review_user_ruled.py` `leave_out_ruled_impacts` drops a plan-change finding that a
recorded text settles (same predicate as the loop: near title or the same criteria ids), except a finding whose
number is in `--user-ruled`: a criterion id alone must not let an accepted finding settle a different change. Such a
finding is left out only when its text (spaces collapsed) equals the accepted finding a ruled row stores in its
`finding_text` field (`handback_store.RULED_FINDING_TEXT_KEY`, written by `record_accepted_plan_impacts` from
`review_fix_asks.ask_finding_text`), or when it is a near title of a recorded text. `decide adopt` and `decide keep`
write one row per accepted finding of the same packet whose criterion ids the ruled impact covers
(`review_fix_asks.findings_covered_by_impact`, read through `review_loop_findings.criteria_covered`), each with its
`finding_text`; an accepted ask on another criterion is not linked, and a row written without a packet matches by near
title only. `review_launch.py` applies it before the findings file is written, and
`skipped_become_asks` leaves a settled one in skipped_fp. A finding with no ruling keeps the user-ruled marker. `script_utils.drop_numbered` renumbers the `--user-ruled` numbers.

## Evidence

judgment: after the user accepted a plan-impact ask and adopted the change, the fix coder was still handed the
finding, skipped it for want of a sign-off already given, and the skip came back as an ask and a held plan impact.

## Result

The new tests fail without the change and pass.

## Watch

None: a routing fix with a fixed outcome.

## Back-out

Revert the commit.
