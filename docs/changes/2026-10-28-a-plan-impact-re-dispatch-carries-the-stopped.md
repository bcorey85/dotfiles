---
type: "Change"
title: "A plan-impact re-dispatch carries the stopped round's open findings"
description: "After a plan-impact ruling, the re-dispatch carried only the ruling and the counters, so the stopped round's fix findings and asks were lost and the next packet looked complete. The ruling's re-dispatch lines now list them under carried-findings, the scripted loop puts the round's unapplied fixes in findings_remaining, and review-loop accounts for every carried line in its packet."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T23:45:38-05:00"}
seq: 225
kind: "fix"
components: ["script/review-fix", "script/handback", "script/review-loop-script", "script/code-step", "agent/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest::test_plan_impact_redispatch_carries_the_round_s_open_findings"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `handback.py` gains `carried_findings`, moved from `code_step_review.py` so /review and /code share it. It skips a PLAN-IMPACT ask, which the ruling settles. `is_plan_impact_ask` moves with it.
- `review_fix.py`: a plan-impact packet saves its carried findings; the ruling's re-dispatch lines add them under `carried-findings:`.
- `review_loop_script.py`: a plan-change stop keeps the round's fix findings open, from reviews sorted before the stop, the stopping review and the reviews after it, or the fixes the stopping coder held. `review_loop_packet.py` puts them in `findings_remaining`, which /code already carries. The stopping and later reviews' other asks and `[design-decision]` items join the packet's asks. A coder that stops on a plan impact keeps its edits: its unskipped issues go to `fixed` when it changed a file, and its changed files to `files_touched`. A `[design-decision]` item with the plan-change mark stops the loop like a plan-change ask; one predicate, `plan_change_items`, serves the stop and the packet's plan-impact list. A fix the plan-change round reports again leaves `fixed` and stays open. Two reviewers' identical asks become one ask.
- review-loop: a plan-impact return lists every unapplied fix in `findings_remaining`, and the packet accounts for every carried line as fixed, skipped or still open.
- Closes the queue items review-plan-impact-redispatch-drops-the-first and review-loop-re-dispatch-drops-earlier-rounds-open.

## Evidence

- A reported run lost 4 of 6 fix findings after a plan-impact ruling, one a correctness bug.
- Failing first: on the base commit, the carry test in `test_review_fix_script.py` and the plan-change tests in `test_review_loop_script.py` fail.

## Result

- The scoped suites pass, ruff is clean, and the duplicate-code check passes.

## Watch

—

## Back-out

Revert the commit.
