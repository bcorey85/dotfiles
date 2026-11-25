---
type: "Change"
change_type: "fixed"
title: "Review loop diffs against the merge base when the given base has moved ahead"
description: "A review launched with a base ref whose tip has moved past the branch now diffs against the merge base, so reviewers see only the branch's own changes instead of master's new commits as reverts."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T03:17:41-06:00"}
seq: 1
kind: "fix"
components: ["script/review-loop", "script/code-review-start"]
evidence: ["session report"]
watches: []
test: "tests/scripts/test_merge_free_base.py::ResolveBaseTest::test_a_base_ahead_of_the_merge_base_resolves_to_the_merge_base"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`lib/merge_free_base.py` gains `resolve_base`, which returns a `BaseResolution`. A base that is not an ancestor of
HEAD is replaced by `git merge-base HEAD <base>`. A base with no merge base stops the launch with the reason and the
recovery command. `code_review_start.py` and `review_launch.py` call it before the merged-commit fold. The review
packet names both bases as `given_base` and `base_used`.

## Evidence

Session report: a review launched with `--base origin/master` after master moved showed master's unmerged commits as
reverts. Reviewers flagged a deleted test the branch never deleted, and one fix coder re-applied a master commit by hand.

## Result

The new tests in `test_merge_free_base.py`, `test_code_review_start.py`, `test_review_launch.py` and
`test_review_loop_script.py` fail before the change and pass after it. A base ref ahead of the merge base yields a
diff of the branch's own changes only.

## Watch

None: a fix with a failing-before test.

## Back-out

Revert the commit; the loop again diffs against the given base's tip.
