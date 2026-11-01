---
type: "Change"
change_type: "fixed"
title: "A plan ruling credits the tree the review covered, and the commit gate names the ruling step"
description: "A /code commit after a review that held a plan impact now passes the commit gate once the impact is ruled on, instead of being denied until a whole new /review (about 6 minutes) runs; a denial caused by an unruled plan impact now names the ruling command, not /review."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-01T03:35:36-06:00"}
seq: 430
kind: "fix"
components: ["script/review-commit-gate", "script/review-fix"]
evidence: ["census"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest::test_a_deferred_plan_impact_credits_the_tree_the_review_covered_and_not_a_later_edit"
asked: ""
proof: []
unmeasured: ""
---

## Change

- Each review-loop hand-back row now stores the tree it covered: the top level and fingerprint of the repo its dispatch reviewed (`handback_store.record_handback`, used by both the hook and the loop script).
- `handback.record_clean_review` credits that stored tree. A row with no stored tree falls back to the tree as it stands.
- `review_fix.py decide keep` and `review_fix.py defer` call `record_clean_review` after they record the ruling. Before, a hand-back that held a plan impact never recorded its tree, and a ruling recorded only the ruling row.
- When the commit's repo has a hand-back with unruled plan impacts, the commit gate's deny text names `review_fix.py defer` and `review_fix.py decide` and says not to run /review again. Before, it said to invoke /review.

## Evidence

- In 57 /code fork runs since Oct 28 on this machine, 4 hit the commit gate's denial. 2 came after the review had converged with a held plan impact.
  - In one, `defer` ran and printed that the gate counts the review as clean, and the gate still denied the commit three times.
  - In the other, the denial text sent the fork into a whole new /review of about 6 minutes.
- Root cause: the hand-back credit route dies once any later coder (the commit coder) is dispatched. The tree route was never recorded when the hand-back held a plan impact.

## Result

- The new review-fix test fails before the change, because no tree is recorded after `defer`. It passes after.
- The new commit-gate test, `test_review_commit_gate.py::ReviewedWorkCommitTest::test_a_commit_after_a_hand_back_holding_a_plan_impact_names_the_ruling_and_not_another_review`, fails before (the deny text says to invoke /review) and passes after.
- The full suite passes (2938 tests), and ruff passes.
- Not fixed here: an edit to the plan file after the review still changes the tree, so a commit that also ships a plan edit is still denied. That needs notes paths left out of the gate's tree comparison, and it stays an open queue item.

## Watch

- None: work logs carry no commit-gate denial count by cause, so no intake number can read it.

## Back-out

- Revert the commit.
