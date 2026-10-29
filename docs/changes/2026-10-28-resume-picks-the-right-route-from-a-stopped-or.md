---
type: "Change"
change_type: "fixed"
title: "Resume picks the right route from a stopped or stale code run"
description: "/code resume takes a launched coder's report, refuses --help and dash answers, offers review-again after a blocker or setup fault, lists the reviewer's asks apart from the coder's notes, and flags a phase the plan changed."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T01:09:23-05:00"}
seq: 162
kind: "fix"
components: ["script/code-step", "agent/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_resume.py::ResumeTest::test_review_again_is_accepted_after_a_critical_blocker_stop"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `resume` takes a finished coder report whose launch row never reached the log, and moves on to the review in
  place of printing the dispatch again.
- `--help` or `-h` after any verb prints that verb's usage and changes nothing. `resume` refuses an answer that
  starts with `-`.
- A critical-blocker or setup-fault stop records its stop reason, and `review-again` accepts it. The stop names the
  `review-again` command for an environment fault the user fixed. `resume` on either stop prints that same
  message, opened with the stop's own sentence (a critical blocker, or a full check that could not run).
- A blocker stop lists the review packet's `ask[]` questions under "Open questions", apart from the blockers.
- `start --restart <text>` over a saved plan with open phases reads the text as run notes, not task text.
- `start` and `resume` compare the stored phase id and text with the plan. A phase that is gone or changed is named,
  with the restart of the plan's next open phase.
- After a false-clean stop, `resume` dispatches the review again.
- review-loop: after any coder that changed files past the round budget, one reviewer scoped to those files runs before a
  `deferred` or `converged` hand-back.
- review-loop: it never returns `converged` or `deferred` with a coder change after the last reviewer; it returns
  `cap-reached` instead, and the extra reviewer's `fix` findings go to `findings_remaining` with no coder.

## Evidence

- Five /code runs on this machine looped or stopped with no accepted next command: a re-printed dispatch of a coder
  that had finished, `resume --help` sent to a coder as the answer, a blocker stop that every verb refused, a
  false-clean stop that `resume` repeated, and a replay of a phase the plan had split.
- Each new test fails on the old scripts.

## Result

- Each of those stops has one accepted command to go on.

## Watch

—

## Back-out

Revert the commit.
