---
type: "Change"
change_type: "fixed"
title: "review_fix reports a pending dispatch before a code run's ownership"
description: "packet now reports a pending standalone review-loop dispatch before it names a /code run as the owner of the session's hand-backs. Before, it named the run as owner when the stored hand-back was the run's but a newer dispatch had not handed back yet."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T01:37:06-05:00"}
seq: 156
kind: "fix"
components: ["script/review-fix"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest::test_pending_standalone_dispatch_after_the_code_run_s_hand_back_reports_no_hand_back_not_the_owner"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `review_fix.py` `saved_hand_back`: the hand-back gap is read first. With a dispatch pending (a loop still waiting,
  or no hand-back since the last dispatch, including a re-dispatch), the /code run owns it only when the run's own
  events log a review-loop dispatch after the stored hand-back (or any, when there is none); otherwise `packet` stops
  with `wait-for-loop` or `stop-no-handback`. With no dispatch pending, the run owns the stored hand-back of an agent
  it launched, as before; the no-dispatch error stays after it.
- Closes the queue item review-fix-names-a-code-run-as-the-hand-back-owner.

## Evidence

- A session ran a standalone review while a /code run in the same session sat at its review stage holding an older
  hand-back. `packet` named the /code run as owner, though the pending loop simply had not handed back.
- The pending-dispatch test fails before the change. A second test pins that the run's own pending review-loop
  dispatch still routes to `code_step.py resume`.

## Result

- The review_fix, review_fixes and handback tests pass, and ruff check is clean.

## Watch

—

## Back-out

Revert the commit. A pending dispatch behind a /code run's stored hand-back reports the run as owner again.
