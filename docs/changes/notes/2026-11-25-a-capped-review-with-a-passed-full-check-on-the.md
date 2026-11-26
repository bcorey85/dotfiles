---
type: "Change"
change_type: "fixed"
title: "A capped review with a passed full check on the tree earns review credit"
description: "A cap-reached review with no blocker reads as deferred when a passed full-check receipt covers the tree, so a plans-only fix after it no longer leaves the push blocked."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T19:30:00-06:00"}
seq: 10
kind: "fix"
components: ["script/capped-review", "script/git-discipline-gate"]
evidence: ["queue: review-loop-write-full-check-tree-so-a-capped", "queue: push-gate-stays-blocked-after-a-capped-review"]
watches: []
test: "tests/scripts/test_git_discipline_gate.py::PushReviewedTreeTest::test_push_passes_after_a_plans_only_commit_on_a_capped_review_and_is_denied_after_a_code_commit"
asked: ""
proof: []
unmeasured: "No logged rate; each hit cost a whole fresh review round or an orchestrator stop."
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

- `review/capped_review.py`: `effective_status` reads a cap-reached packet with no blocker, no open class and no unrun reviewer as `deferred` when either:
  - `lib/full_check_receipt.valid_receipt(repo)` returns a receipt whose result is `passed`; or
  - the packet's `full_check_tree` matches, as before.
- A not-run or CI-only receipt earns no credit.
- No loop writer ever filled `full_check_tree`, so before this change no capped review could read as deferred.

## Evidence

- A branch review hit its cap with one docs-only finding, no blocker and a passed full check, and still read `cap-reached`. The commit gate stayed blocked.
- In another case, a lane fixed plan-text leftovers by hand after a capped review, and the push gate still refused the push.

## Result

The new tests fail before the change and pass after. A code commit after the review is still denied at push.

## Watch

None.

## Back-out

Revert the commit.
