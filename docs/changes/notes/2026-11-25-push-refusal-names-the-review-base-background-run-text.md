---
type: "Change"
change_type: "fixed"
title: "Push refusal names the review base"
description: "The changed-since-review push deny now names the commit to review from, so /review after a commit no longer stops with no changes."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-25T18:00:00-06:00"}
seq: 7
kind: "fix"
components: ["script/git-discipline-gate", "script/reviewed-tree"]
evidence: ["queue: push-gate-sends-a-committed-change-to-a-review"]
watches: []
test: "tests/scripts/test_git_discipline_gate.py::PushReviewedTreeTest::test_push_is_denied_when_code_changed_after_the_review"
asked: ""
proof: []
unmeasured: "No logged rate of either message."
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

- `lib/reviewed_tree.py` gains `latest_reviewed_base`: the `base` of the newest entry in the repo's shared bases record, or None. `push_review_state` and it read the record through one helper, `shared_base_entries`.
- `gates/git_discipline_gate.py`: the push deny reads `run /review base=<hash> on this branch, then push`. When the newest entry in the record holds no base string, it keeps the old text.

## Evidence

The push refusal told the session to run `/review` with no base. After a commit, that scope is empty, so the review stopped with "no changes".

## Result

The new tests fail before the change and pass after.

## Watch

None.

## Back-out

Revert the commit.
