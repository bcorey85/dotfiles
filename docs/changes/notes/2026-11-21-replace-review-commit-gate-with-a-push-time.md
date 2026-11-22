---
type: "Change"
change_type: "removed"
title: "Replace review-commit-gate with a push-time reviewed-tree check"
description: "review-commit-gate and its dirty tracking are deleted; git-discipline-gate denies a git push or gh pr create whose HEAD tree holds code changed after the repo's last converged review, passes a notes-only change, and passes a repo with no review record."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-21T22:23:26-06:00"}
seq: 1
kind: "fix"
components: ["script/review-commit-gate", "script/commit-gate-dirty", "script/git-discipline-gate", "script/reviewed-tree"]
evidence: ["census"]
watches: ["replace-review-commit-gate-push-check"]
test: "tests/scripts/test_git_discipline_gate.py::PushReviewedTreeTest::test_push_is_denied_when_code_changed_after_the_review"
asked: ""
proof: []
unmeasured: "No bench: the watch counts hook blocks per day; no metric counts main-session turns that end right after a block."
---

## Change

- Deleted `review/review_commit_gate.py`, `review/commit_gate_dirty.py`, `review/commit_gate_denials.py`, `review/commit_placement.py` and `tests/scripts/test_review_commit_gate.py`, the omp bridge's review-commit-gate entry and task arming, and the pi settings hook entry.
- `lib/reviewed_tree.py` `push_review_state(repo_dir)` reads the shared reviewed record and returns no record, reviewed or changed; the HEAD commit's tree is fingerprinted in `target` mode, notes paths left out.
- `gates/git_discipline_gate.py` runs it for `git push` and `gh pr create` and denies a changed tree with "code changed since the last review: run /review on this branch, then push".
- A repo with no review record pushes freely: the push check cannot tell a repo the toolkit never reviewed from one whose record was lost.
- Phase asks are no longer enforced at commit. `phase_asks.py list` and `rule` still open and rule them, and `verify_common.branch_review_covers` still needs them ruled.
- Prompt and doc mentions of the commit gate now name the push check or the review record.
- A stale test now expects the fix-coder prompt's `coder-model:` header, and an over-long docstring line in `review/review_loop_script.py` is wrapped, so the suite and lint pass.

## Evidence

Work census of hook blocks (queue item replace-review-commit-gate-with-a-push-time): 204 main-session and 31 subagent review-commit-gate blocks. 31 main-session turns ended right after one, so review-commit-gate made the most main-session turn ends of any rule, and 63 queue items closed against its dirty-repo guesses and commit parsing.

## Result

Commits are never blocked for review. A push is blocked only when HEAD's code tree differs from every tree a converged review recorded for the repo. A merge after the review changes the tree, so its push is denied until the next /review.

## Watch

`replace-review-commit-gate-push-check`: review-commit-gate and git-discipline-gate blocks per day, down.

## Back-out

Revert the commit and put the two `review_commit_gate.py` hook entries back in `claude/.claude/settings.json`.
