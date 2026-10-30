---
type: "Change"
change_type: "changed"
title: "A capped review with no blocker and a passed full check of the final tree lands as deferred"
description: "A review that hits its round cap with no blocker, no open class, a scoped reviewer that ran, and a passed full check whose tree equals the work tree now reads as deferred, so a finished lane commits with its leftovers logged instead of having no path to land."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T05:39:07-05:00"}
seq: 319
kind: "fix"
components: ["script/handback", "script/review-fix", "script/review-commit-gate", "script/code-step", "agent/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_clean_status_one_owner.py::CleanStatusOneOwnerTest::test_a_capped_review_stays_capped_when_the_check_is_old_or_not_passed_or_a_blocker_is_open"
asked: ""
proof: []
unmeasured: ""
---

## Change

- The new `review/capped_review.py` owns `effective_status`. A `cap-reached` packet reads as `deferred` only when it
  holds no blocker, no open class and no scoped reviewer that could not run, its full check passed, and that check's
  tree fingerprint equals the work tree's fingerprint now. A fix after the check keeps `cap-reached`.
- `handback.py` imports the rule; `review_fix.py`, the review gate's clean mark, the commit gate and the code-step
  review stops all read the status through it and keep no copy.
- A deferred-from-cap packet names the fix files no reviewer saw after their last change, in the user text and the
  log.
- The hand-back records the tree its passed full check covered. The hook code moves out of `handback.py` into
  `review/handback_hook.py`.
- Both review-loop agent files: the cap exit's scoped reviewer's non-blocker `fix` findings defer, in place of
  `cap-reached`; a blocker still caps.

## Evidence

Overnight toolkit lanes hit the review cap six times. Each time, the fix round's new code drew small findings from
the cap exit's scoped reviewer. With no converged review, the commit gate refused the commit, and a lane with a green
full suite and no open blocker had no path to land.

## Result

Targeted tests pass. A stale check, a blocker, an open class, an unrun scoped reviewer, or a check that did not pass
keeps `cap-reached`.

## Watch

None; a fix with no intake number.

## Back-out

Revert the commit.
