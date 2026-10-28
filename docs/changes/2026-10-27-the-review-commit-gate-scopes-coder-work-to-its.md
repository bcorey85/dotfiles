---
type: "Change"
title: "The review commit gate stops misreading merges, peer messages and closed loops"
description: "The review commit gate credits a converged review-loop hand-back however the run closed, keeps a [no-review] order through peer messages, summaries and shell echoes, and stops counting commit-tree; it still denies a commit in any repo while coder work is unreviewed."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T21:58:18-05:00"}
seq: 146
kind: "fix"
components: ["script/review-commit-gate"]
evidence: ["census"]
watches: []
test: "tests/scripts/test_review_commit_gate.py::ReviewedWorkCommitTest::test_a_converged_hand_back_after_the_coder_lets_the_commit_through_without_a_mark"
asked: ""
proof: []
unmeasured: ""
---

## Change

- A coder dispatch or a `dirty` mark still makes the session dirty, whatever repo the coder changed. While it is
  dirty, a commit in any repo is denied unless it earns a credit.
- A coder dispatch is recorded with its agent id. A coder counts as dirty from its dispatch or its transcript's last
  change, whichever is later, so a background coder that writes after a review is not covered by it.
- The session's latest review-loop hand-back credits a commit when it is converged or deferred, came after the coder
  work, and answers a review-loop dispatch of the commit's repo. That holds however the run that launched the loop
  closed, a manual tick included. A review-loop dispatch row now records the repo it reviews, by the loop's own
  rule: the prompt's `repo:` line, else the first absolute path the prompt names, else the session cwd.
- Merge, reviewed-tree and hand-back credit go to the repo each `git commit` runs in: the cwd moved by each
  `git -C`. A command that changes folder or repo (cd, pushd, popd, eval, source, `.`, a git dir or work-tree option
  or variable, a disguised `c\d` or `'c'd`) or holds a `$` or backtick outside a quoted heredoc message or single
  quotes earns no credit. A commit message written as a quoted heredoc is not read as commands.
- A `[no-review]` order holds through records that are not the user's prompt: a peer session's message, a
  compaction summary, a `!` shell echo, a task notification and a tool result. A later human prompt still ends it.
- `git commit-tree` and `git commit-graph` no longer count as a commit.
- The state file holds timed JSON events. A plain `dirty` line from the old format counts from the file's last change.
- Dropped: scoping a commit to the repos a coder edited and to the folders a `cd` names. Each version of the shell
  reader left a route that let a commit reach a dirty repo, the last one through a `HOME` assignment before a
  `git -C ~/...`. So a commit in agent-evals is still denied for coder work in a dotfiles worktree, and a merge
  commit after a `cd` gets no merge credit.

## Evidence

- Four toolkit bug reports, each one a denied commit the user then had to run by hand:
  - a commit in agent-evals was denied for coder work in a dotfiles worktree (not fixed: scoping dropped);
  - a commit after a converged /code review loop was denied because the run closed through a manual tick;
  - a merge commit of a branch that was already reviewed was denied after a `cd` (not fixed: scoping dropped);
  - a `[no-review] go` order was dropped once a peer message arrived.
- Tests in `tests/scripts/test_review_commit_gate.py` that fail before and pass after:
  - `test_a_converged_hand_back_after_the_coder_lets_the_commit_through_without_a_mark`
  - `test_a_hand_back_of_another_repo_gives_this_repo_no_credit`
  - `test_a_hand_back_before_a_background_coder_last_wrote_gives_no_credit`
  - `test_a_coder_with_no_agent_id_gets_no_hand_back_credit`
  - `test_a_folder_option_emptied_with_a_heredoc_message_earns_no_credit`
  - `test_a_second_commit_in_another_repo_or_behind_a_wrapper_gets_no_credit_from_the_cwd_hand_back`
  - `test_a_no_review_order_survives_peer_messages_summaries_and_shell_echoes`
  - `test_a_human_prompt_after_the_order_still_ends_it`
  - `test_commit_tree_is_not_a_commit`
- Tests that hold the deny rule: `test_coder_work_in_one_repo_denies_a_commit_in_any_repo`,
  `test_a_folder_change_or_an_unknown_target_earns_no_credit`.
- `tests/scripts/test_handback.py::StoreTest::test_a_dispatch_row_names_the_repo_its_prompt_or_cwd_holds`

## Result

- A commit after a converged review loop, or under a `[no-review]` order with peer messages after it, goes through.
- Unreviewed coder work in any repo still denies every commit.

## Watch

No new watch. The gate's denials are not logged with the repo they named, so no intake number separates a right
denial from a wrong one.

## Back-out

Revert the commit.
