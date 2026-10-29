---
type: "Change"
change_type: "fixed"
title: "Review commit gate credits merges, user-ordered commits, reviewed trees and the repo a commit runs in"
description: "A dirty session now commits a merge, a commit the user ordered with a [no-review] prompt, a tree a converged review covered, and judges git -C commits by the target repo."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-25T23:56:35-05:00"}
seq: 35
kind: "fix"
components: ["script/review-commit-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_commit_gate.py::ReviewedWorkCommitTest::test_a_commit_that_concludes_a_merge_passes, tests/scripts/test_review_commit_gate.py::ReviewedWorkCommitTest::test_a_commit_the_user_ordered_without_review_passes_that_turn, tests/scripts/test_review_commit_gate.py::ReviewedWorkCommitTest::test_a_commit_with_git_dash_c_is_judged_by_that_repos_review_state, tests/scripts/test_review_commit_gate.py::ReviewedWorkCommitTest::test_a_commit_of_a_tree_that_converged_review_covered_passes_after_a_later_coder_dispatch"
asked: ""
proof: []
unmeasured: ""
---

## Change

The commit gate blocked any commit in a dirty session. It now passes four more cases, each checked against something a subagent cannot write:

- A commit that concludes a merge (the repo has a MERGE_HEAD).
- A commit while the user's latest prompt in the main transcript starts with `[no-review]`. Tool results, meta records, subagent records and task notifications never count, so a subagent report cannot carry the order. The next prompt without the marker ends it.
- A commit of a working tree that a converged review covered. `review-gate-mark clean` and /code's phase finish now record a fingerprint of the repo's tree (new `lib/reviewed_tree.py`, under `review_gate_dir()`); a later coder dispatch that edits nothing, such as a commit-only hand-off after two converged phases, leaves the fingerprint equal, so the commit passes. Any edit or new untracked file changes it and the commit is denied again.
- A commit run as `git -C <dir>` or from a cwd outside the repo is judged by that repo's tree. A command with `--git-dir` or `--work-tree` gets no credit.

An unreviewed coder commit is still denied.

## Evidence

judgment: the reported blocks (the user committing by hand three times after ordered no-review fix and merge commits; orchestrator commits from outside the repo root; a full /review run to pass a commit of work that had already converged in /code).

## Result

Unmeasured until the next intake; the hook-block counts for this gate show whether the false blocks stop.

## Watch

None.

## Back-out

Restore review_commit_gate.py's `check_commit` to deny whenever the state is dirty and the commit is not notes-only; drop the `record_reviewed` call in code_step_boundary.py.
