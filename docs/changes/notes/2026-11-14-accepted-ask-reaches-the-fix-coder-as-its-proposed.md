---
type: "Change"
change_type: "fixed"
title: "Accepted ask reaches the fix coder as its proposed change only"
description: "An accepted ask's findings line now holds its class tag and proposed change, never the question or its If-declined branch, and a fix coder that re-asks a ruled ask in OPEN QUESTIONS has that finding skipped, not counted as fixed."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-14T11:36:05-06:00"}
seq: 2
kind: "fix"
components: ["script/review-fix", "script/review-loop", "script/review-launch"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_fix_first_finding_the_coder_re_asks_in_open_questions_is_skipped_not_fixed"
asked: ""
proof: []
unmeasured: ""
---

## Change

`review/review_fix_asks.py` `ask_finding_text` writes `<file:line> [<class>] Proposed change: <change>`; every accepted
ask that is not a plan impact adds the `acceptance_criteria:` ids, and a plan-impact ask keeps its question. `review/review_user_ruled.py`
`reasked_findings` finds a ruled finding whose file:line a coder's OPEN QUESTIONS names, and `review_loop_script.py`
`fix_first` files it as skipped. Session-ruled asks reach the loop through a new `--session-ruled` launch flag and a
`session-ruled:` prompt-file header, so the check covers both rulers. `review_loop_findings.ruled_plan_impact` also
settles a re-filed accepted plan-drift finding on the same file:line and criterion ids.
`script_utils.locations_named` is shared with `handback.entry_locations`.

## Evidence

judgment: an accepted ask reached the coder with its question and If-declined branch, the coder re-asked it in OPEN
QUESTIONS, and the loop counted the finding as fixed. Second report of this class.

## Result

The new tests in `test_review_fix_script.py`, `test_review_loop_script.py`, `test_review_user_ruled.py`,
`test_review_launch.py` and `test_review_loop_findings.py` cover each part; the five files run 736 tests, 0 failed.

## Watch

None: a script fix with a fixed outcome.

## Back-out

Revert the commit.
