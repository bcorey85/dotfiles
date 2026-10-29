---
type: "Change"
change_type: "fixed"
title: "A review-loop hand-back with no reviewer run cannot turn the review gate clean"
description: "handback.py records the coder and reviewer dispatches each review-loop makes, and refuses a clean hand-back when no reviewer ran after the loop's last code change; +fast now only changes the reviewer model."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T17:30:48-05:00"}
seq: 66
kind: "fix"
components: ["agent/review-loop", "script/handback", "script/review-fix", "script/script-utils", "script/review-loop-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_handback.py::ReviewerRequiredTest::test_clean_hand_back_with_no_reviewer_is_denied_once_then_stored_flagged_and_refused"
asked: ""
proof: []
unmeasured: ""
---

## Change

- The dispatch hook records each coder and reviewer dispatch a review-loop agent makes, keyed by that agent's id.
- The hand-back hook denies a clean hand-back once when no reviewer ran after the loop's last coder dispatch. A second
  attempt is stored flagged, and `review_fix.py packet` answers it with `ACTION: stop-no-reviewer` (exit 2), so the
  gate never reads it as clean.
- A loop dispatched in `no-review` mode claims one exemption per no-review dispatch and passes.
- `+fast` in the review-loop agent passes `model: "haiku"` to each reviewer and never skips one.
- The coder and reviewer name lists live in `script_utils.py`, shared by `review_loop_gate.py` and `handback.py`.

## Evidence

- Seen twice at work: a `+fast` review-loop reviewed the diff itself and handed back converged, and the review gate went
  clean with no reviewer run.
- A redispatch after a plan-impact adopt applied a 16-file change with no reviewer and handed back clean.
- The new tests fail on the base commit and pass after.

## Result

- Full suite and ruff pass on the worktree.
- Known gap: a normal loop that skips review while an unclaimed no-review loop runs in parallel can take that loop's
  exemption. A SendMessage resume of a coder is not counted as a code change.

## Watch

—

## Back-out

Revert the commit.
