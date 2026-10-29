---
type: "Change"
title: "A code run's own coder and review-loop plan edits no longer make it stale"
description: "Taking the hand-back of the run's own coder or review-loop re-reads the phase text from the plan, and `resume` skips the stale check when that hand-back is waiting, so the run's own edits under the same phase heading never ask for `start --restart`. A plan edit made after the hand-back was taken, or while the coder is still out, is still stale."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T13:59:07-05:00"}
seq: 197
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_resume.py::ResumeTest::test_a_resume_at_the_asks_after_the_review_loop_edited_the_phase_text_is_not_stale"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `take_handback` (code_step_core.py) calls the new `refresh_phase_text`: when the run's own coder or review-loop
  hands back, the phase text it left in the plan becomes the run's saved phase text. A plan that cannot be read, or
  that lost the phase or whose phase heading changed, keeps the old text so the stale check still reports it.
- `resume_route` (code_step.py) works out the stage route first. When that route takes the hand-back of the run's own
  coder or review-loop and the hand-back is there, it skips the stale check only when the re-read would adopt the
  phase (same heading): taking the hand-back re-reads the plan.
- One root cause behind four reports: a coder's one-word plan fix, a review loop's plan wording fix before the asks,
  a review fix of spec prose, and a review after an adopted plan change each stranded their own run as stale.

## Evidence

- Four queue reports from work sessions, each forced to drop the run with `start --restart` for an edit the run made.
- Tests, each failing before the fix:
  - `test_code_step_resume.py::ResumeTest::test_a_resume_after_the_coder_edited_its_own_phase_text_goes_on_to_the_review`
  - `test_code_step_resume.py::ResumeTest::test_a_resume_at_the_asks_after_the_review_loop_edited_the_phase_text_is_not_stale`
  - `test_code_step_resume.py::ResumeTest::test_a_resume_after_an_adopted_plan_edit_and_a_review_loop_edit_is_not_stale`
- Guard, passing before and after: `test_a_plan_edit_after_the_review_loop_handed_back_is_still_stale`.

## Result

- The run goes on after its own agents edit the plan: edits under the same phase heading are adopted at the
  hand-back whoever made them. A heading change, a missing phase or an unreadable plan still asks about a stale
  phase on the first `resume`, since the heading guard leaves those to the stale check. An edit made while the coder
  is still out and has not handed back, or after the hand-back was taken, still asks too.

## Watch

- None: no intake number counts stale-phase questions.

## Back-out

- Revert the commit.
