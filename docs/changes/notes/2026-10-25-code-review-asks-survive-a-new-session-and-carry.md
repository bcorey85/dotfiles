---
type: "Change"
change_type: "fixed"
title: "/code review asks survive a new session and carry one proposed change"
description: "A /code run now pins to the session that opens each dispatch, so open review asks and a review-again hand-back survive a new session; a resume at a closing phase re-invokes its skill; and every structured review ask carries one proposed change, so an accepted answer gives the asks coder an edit to make."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-25T16:14:13-05:00"}
seq: 10
kind: "fix"
components: ["script/code-step", "script/handback", "script/review-fix", "agent/review-loop", "agent/code-reviewer", "agent/smell-reviewer", "agent/test-reviewer", "shared/reviewer-calibration", "skill/review", "skill/fix"]
evidence: ["bench incident", "repro"]
watches: []
test: "tests/scripts/test_code_step_resume.py::test_a_resume_from_a_new_session_keeps_the_open_asks_and_takes_their_answers; tests/scripts/test_code_step_resume.py::test_a_review_again_from_a_new_session_pins_the_run_to_it_so_its_hand_back_counts; tests/scripts/test_code_step_resume.py::test_resume_from_a_new_session_at_a_closing_phase_invokes_its_skill_again; tests/scripts/test_code_step.py::test_the_question_for_the_user_names_each_asks_proposed_change_and_what_each_answer_does; tests/scripts/test_code_step.py::test_an_accepted_ask_sends_its_proposed_change_to_the_asks_coder; tests/scripts/test_handback.py::test_an_ask_carries_its_one_proposed_change_as_its_own_field; tests/scripts/test_handback.py::test_an_either_or_ask_with_no_proposed_change_is_refused; tests/scripts/test_review_fix_script.py::test_present_asks_names_each_proposed_change_and_what_each_outcome_does; tests/scripts/test_review_fix_script.py::test_an_either_or_ask_with_no_proposed_change_is_a_parse_failure"
---

## Change

- `code_step_core.open_dispatch` pins the run to the session that opens the dispatch. A verb run from a new session (resume, review-again) moves the pin to it, so its hook events and its review hand-back count.
- `code_step_boundary.mark_review_gate_clean` checks the false-clean reason against the stored pin and writes the clean mark for the current session.
- `code_step.ask_about_unrecorded_state` at stage `skill` re-emits the closing skill dispatch (`resume_closing_skill`, sharing `emit_closing_skill` with `start_closing_phase`) instead of asking the user.
- `handback` gains the ask field `change`. A structured ask with no `change` is refused at hand-back. A prose ask (no fields) still reaches the user.
- The code-step ask question and the review/fix `present-asks` text print each ask's proposed change and what accepted, rejected and modified do. The asks coder prompt names the proposed change, or the user's change after a modified answer.
- reviewer-calibration, code-reviewer, smell-reviewer, test-reviewer and review-loop write each ask as one proposed change; the opencode ports of code-reviewer, smell-reviewer and review-loop match. The opencode test-reviewer has no spec-assertion section, so it is left as is.
- Deleted `test_code_step.py::test_the_clean_mark_asks_about_the_environments_session_not_the_stored_pin`: it pinned the old check against the environment's session.

## Evidence

Bench, BILL-212 full-toolkit smoke (`~/dev/evals/ab-full/GRADING.md`, kit section): a plain `/code` resume from a new session moved stage `asks` to `stopped` and every later answer was refused; a review-again from a new session lost a 690 s hand-back to the stale pin; an either/or ask answered accepted gave the asks coder nothing to do; and a closing phase resumed in a new session stopped on an ask-user hand-back. Each path has a test above that failed before the change and passes after it.

## Result

Full suite on the draft: 2048 tests in 53 files, 0 failed. Over the real hand-back store, the draft parser reads 45 of 99 stored packets; the 54 it refuses are old structured asks without `change`, an expected format break. The bench rig's `reopen_asks.py` and `unpin_session.py` are no longer needed.

## Watch

None. A fix: the tests reproduce each path.

## Back-out

Revert the branch `fix/code-review-asks`.
