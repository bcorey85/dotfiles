---
type: "Change"
change_type: "fixed"
title: "A coder that edited no work tree leaves every repo clean"
description: "review-commit-gate counts a coder whose readable transcript shows no edit inside a work tree (nothing, a scratch file, a git dir, a deleted worktree) against no repo, so scratch-repo commits and a /code fork's reviewed commit pass."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-03T19:23:16-06:00"}
seq: 6
kind: "fix"
components: ["script/review-commit-gate"]
evidence: ["work incident"]
watches: []
test: "tests/scripts/test_review_commit_gate.py::ReviewedWorkCommitTest::test_a_coder_that_edited_no_work_tree_lets_a_commit_in_a_scratch_repo_through"
asked: ""
proof: []
unmeasured: ""
---

## Change

`edited_repos` returns an empty set, not None, when a readable coder transcript shows no Edit/Write/MultiEdit/NotebookEdit path inside a work tree. A folder that no longer exists is placed by its nearest existing ancestor. A folder inside a `.git` dir, or with no `.git` in it or above it, is outside every work tree. `dirty_since` then skips that coder for every repo. Fail-closed stays for an unreadable transcript, a missing agent id, and a folder with a `.git` above it that git cannot place. The edit tools are the record of coder writes because the shell-write-gate denies coder shell writes to tracked files.

Second test, for the /code fork credit: `tests/scripts/test_review_commit_gate.py::ReviewedWorkCommitTest::test_a_converged_review_in_a_code_fork_credits_its_commit_after_a_scratch_only_coder`. Fail-closed pin: `test_a_coder_edit_git_cannot_place_denies_a_commit_in_any_repo`.

## Evidence

Across the 40 latest gate sessions, 93 of 355 coder agents counted against every repo. They had edited nothing, only scratch or non-repo folders, only review-loop reports inside a git dir, or a worktree since deleted. In one /code fork, a deny came 3 minutes after a converged hand-back. The coders after the hand-back had made no edits or had written only a scratchpad file.

## Result

The two new tests failed before the change (5 subtests denied) and pass after. All 147 tests in test_review_commit_gate.py pass. Gate median wall time on a dirty-session commit with three coders (repo, scratch, none), 25–30 runs per sample: 104.7–141.6 ms before, 104.5–130.1 ms after. No measurable change.

## Watch

None.

## Back-out

Restore `edited_repos` to return `{...} or None` with `repo_root` per existing folder, and drop `folder_repo_top`.
