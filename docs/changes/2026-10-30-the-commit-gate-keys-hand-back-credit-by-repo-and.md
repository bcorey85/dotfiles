---
type: "Change"
change_type: "fixed"
title: "The commit gate keys hand-back credit by repo and passes queue-page commits"
description: "A converged review-loop hand-back for one repo keeps its commit credit after a review of another repo, and a dirty commit that ships only QUEUE.md or queue/*.md pages passes as docs/ Markdown does."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T12:40:55-05:00"}
seq: 320
kind: "fix"
components: ["script/review-commit-gate"]
evidence: ["queue item: review-commit-gate voids one repo's review credit after a review in another repo"]
watches: []
test: "tests/scripts/test_review_commit_gate.py::ReviewedWorkCommitTest::test_a_converged_hand_back_keeps_its_repo_credit_after_a_review_of_another_repo"
asked: ""
proof: []
unmeasured: ""
---

## Change

`handback_store.latest_for_repo` reads only the rows of review-loops that reviewed one repo: each dispatch of that repo and the stop and hand-back rows after it. `review_handed_back_since` judges that standing through `handback.standing_false_clean_reason`, so a review of another repo neither answers nor voids this repo's hand-back. `is_notes_path` also passes the top-level `QUEUE.md` and Markdown files directly in the top-level `queue/` folder, and the denial text names them.

## Evidence

A session that reviewed agent-evals and then dotfiles lost the agent-evals hand-back credit, and each refusal cost a full extra /review run. Hand-back credit had one slot: the session's latest dispatch, whatever repo it reviewed.

## Result

The three new gate tests fail on the old gate and pass on the new one. One `test_handback.py` test pinned the old rule, that a dispatch of another repo takes the credit away, and now pins the new one.

## Watch

—

## Back-out

Make `review_handed_back_since` read `handback_store.latest` again and drop the queue branch of `is_notes_path`.
