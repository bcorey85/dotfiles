---
type: "Change"
change_type: "fixed"
title: "The code hand-back gate denies once and flags a file the coder left"
description: "A coder blocked at hand-back by a later-phase file it did not write now gets through on its second try, with the file flagged, instead of retrying until the 1800 s wait cap. A stop on a coder with no saved report now names the blocking file. A PLAN-IMPACT about a code-step gate stops the run instead of rewriting the plan, and a block a later hand-back replaced goes to the session for a ruling instead of being adopted by rule."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T10:00:23-05:00"}
seq: 348
kind: "fix"
components: ["script/code-step", "skill/code"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_expected_red.py::ExpectedRedTest::test_a_second_hand_back_with_the_same_file_goes_through_and_the_review_flags_the_file"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `later_phase_edit_denial` denies a coder once per file and logs `later-phase-deny`. A hand-back whose files were all denied before for that coder goes through and logs `later-phase-pass`. A new file denies again.
- `route_coder_report` flags the files that passed, so the summary and the review name them.
- `stopped_coder_report` and `stop_at_wait_cap` print the newest denial reason when the coder has no saved report.
- `names_only_toolkit` in `plan_format.py` reads a block whose `assumed:` or `found:` lines name a code-step hook or gate and no plan step as a toolkit fault, so the run stops and no plan rewrite runs.
- `impact_replaced` finds a block that the coder's newest hand-back no longer carries. `emit_plan_impact_modal` then skips the adopt-by-rule path, on the first route and on a repeat resume, and asks the session for the ruling.
- The `/code` skill description tells the main session not to edit tracked files in the run's checkout while a coder runs.

## Evidence

- One session reported a coder retrying six times on a notes file the main session edited. The run timed out with no report. The same session reported a stale gate block and an options list adopted as plan rulings.

## Result

- `tests/scripts/test_code_step_expected_red.py`, `test_code_step.py` and `test_plan_format.py` cover each change. The full suite passed in review: 4774 tests, 0 failed.

## Watch

None: this fires on a rare stop, and no intake number counts it.

## Back-out

Revert the commit. The new event names are read only by this change.
