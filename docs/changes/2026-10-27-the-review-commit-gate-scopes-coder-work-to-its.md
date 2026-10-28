---
type: "Change"
title: "The review commit gate scopes coder work to its repo and stops misreading merges, peer messages and closed loops"
description: "The review commit gate denies a commit only in a repo a coder edited, credits a converged review-loop hand-back however the run closed, gives merge credit after a leading cd, and keeps a [no-review] order through peer messages, summaries and shell echoes."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T21:58:18-05:00"}
seq: 128
kind: "fix"
components: ["script/review-commit-gate"]
evidence: ["census"]
watches: []
test: "tests/scripts/test_review_commit_gate.py::ReviewedWorkCommitTest::test_coder_work_in_one_repo_leaves_a_commit_in_another_repo_allowed"
asked: ""
proof: []
unmeasured: ""
---

## Change

- A coder dispatch is recorded with its agent id. At commit time, the gate reads that coder's own transcript and
  takes the repos that hold the files its Edit, Write, MultiEdit and NotebookEdit calls named. A commit is denied
  only in a repo a coder edited.
- Every repo stays dirty in these cases:
  - a coder with no transcript;
  - a coder with no edit on record;
  - a coder that edited a file outside any repo;
  - a standing `dirty` mark;
  - a commit whose repo the gate cannot tell.
- The session's latest review-loop hand-back lets the commit through when it is converged or deferred, came after
  the coder work, and answers a review-loop dispatch of the commit's repo. That holds however the run that launched
  the loop closed, a manual tick included. A review-loop dispatch row now records the repo it reviews.
- A command with a `cd`, `pushd` or `popd` anywhere is judged against every candidate repo: the session cwd plus each
  folder a word of the command names. Each candidate must be clean or carry merge, reviewed-tree or hand-back
  credit. The gate does not follow the chain's shape. A target no word names (`$`, a backtick, `eval`, `popd`,
  `cd -`) is judged against every repo.
- A `[no-review]` order holds through records that are not the user's prompt: a peer session's message, a
  compaction summary, a `!` shell echo, a task notification and a tool result. A later human prompt still ends it.
- `git commit-tree` and `git commit-graph` no longer count as a commit.
- The state file holds timed JSON events. A plain `dirty` line from the old format counts from the file's last change.

## Evidence

- Four toolkit bug reports, each one a denied commit the user then had to run by hand:
  - a commit in agent-evals was denied for coder work in a dotfiles worktree;
  - a commit after a converged /code review loop was denied because the run closed through a manual tick;
  - a merge commit of a branch that was already reviewed was denied;
  - a `[no-review] go` order was dropped once a peer message arrived.
- Tests in `tests/scripts/test_review_commit_gate.py` that fail before and pass after:
  - `test_coder_work_in_one_repo_leaves_a_commit_in_another_repo_allowed`
  - `test_a_coder_with_no_edit_on_record_dirties_every_repo`
  - `test_a_converged_hand_back_after_the_coder_lets_the_commit_through_without_a_mark`
  - `test_a_merge_commit_passes_after_any_cd_when_every_candidate_is_clean_or_merging`
  - `test_a_cd_in_any_shape_is_judged_against_the_cwd_and_every_cd_target`
  - `test_a_hand_back_of_another_repo_gives_this_repo_no_credit`
  - `test_a_no_review_order_survives_peer_messages_summaries_and_shell_echoes`
  - `test_a_human_prompt_after_the_order_still_ends_it`
  - `test_commit_tree_is_not_a_commit`
- `tests/scripts/test_handback.py::StoreTest::test_a_dispatch_row_names_the_repo_its_prompt_or_cwd_holds`

## Result

- A commit that holds no unreviewed coder work goes through. The user no longer runs it by hand.
- Unreviewed coder work is still denied in the repo it changed.

## Watch

No new watch. The gate's denials are not logged with the repo they named, so no intake number separates a right
denial from a wrong one.

## Back-out

Revert the commit.
