---
type: "Change"
title: "A review-loop's cap-exit coder no longer marks its hand-back unreviewed"
description: "The hand-back hook demanded a reviewer after a review-loop's last coder, but the loop's own cap exit dispatches none after its round-2 coder, so every loop whose second review filed a fix ended stop-no-reviewer; from round 2 on, one reviewer dispatch by the loop now suffices."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T06:51:31-05:00"}
seq: 1
kind: "fix"
components: ["script/handback", "agent/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_handback.py::ReviewerRequiredTest::test_cap_exit_coder_after_the_second_review_passes_when_converged"
asked: ""
proof: []
unmeasured: ""
---

## Change

`scripts/review/handback.py`:

- `ran_reviewer` takes the packet's `iter`. At `iter >= 2`, one reviewer dispatch by the loop's agent id is enough: the
  trailing coder is the cap-exit coder, which the review-loop agent's contract never follows with a reviewer (only the
  execution gate reads its diff).
- Below round 2 the old rule stands: a reviewer must follow the last coder.
- `handle_hook` reads `iter` from the parsed packet. An unparsable packet never reaches the reviewer check. The deny-once behaviour,
  the stored `no_reviewer` flag and the no-review exemption are unchanged.

Tests in `tests/scripts/test_handback.py`, `ReviewerRequiredTest`: the cap exit passes when converged and when deferred;
still denied are a loop that never ran a reviewer at round 2 and a reviewer under
another agent id. The converged case fails before this change.

## Evidence

- 2026-10-26: four of four `/review` runs in one session, on two branches, ended `stop-no-reviewer` with `iter: 2`. Each
  loop had run two reviews; the last step was the round-2 coder. The gate refused every clean mark, so no commit could
  land, and each re-dispatch cost a full loop.
- The rule that caused it was added the same day to stop loops that ran no reviewer at all. Both of its motivating
  cases (a loop that reviewed the diff itself, and a redispatch that applied a change with no reviewer) ran zero
  reviewers, and both are still denied.

## Result

A review-loop that reaches its round cap after at least one reviewer pass can turn the review gate clean. Known gap:
the loop's docs-only exit below round 2 (no review after a docs-only fix) still ends `stop-no-reviewer`; the hook cannot
see that the fix was docs-only. A fix-first re-entry at `iter >= 2` (a loop agent whose steps are only
[coder]) is still denied.

## Watch

None. The intake does not count `stop-no-reviewer` outcomes.

## Back-out

Drop the `iter_round` argument from `ran_reviewer` and its call in `handle_hook`, and the four new tests.
