---
type: "Change"
change_type: "added"
title: "pull_keep_index keeps staged files staged through pull before push"
description: "`tools/pull_keep_index.py <repo>` pulls with `--rebase=merges` and puts local changes back with `stash apply --index`, so staged files stay staged."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-08T09:19:32-06:00"}
seq: 1
kind: "fix"
components: ["script/pull-keep-index"]
evidence: ["pull-with-autostash-unstages-files-the-user-staged"]
watches: []
test: "tests/scripts/test_pull_keep_index.py::test_staged_and_unstaged_changes_keep_their_state_across_the_pull"
asked: ""
proof: []
unmeasured: ""
---

## Change

New `claude/.claude/scripts/tools/pull_keep_index.py <repo>`. It saves local changes with `git stash create` (a dangling commit, never on the shared stash stack), resets, runs `git pull --rebase=merges --no-autostash`, then `git stash apply --index`. A failed fetch puts the changes back. A stopped rebase or a failed apply exits 1 and names the saved commit and the recovery command.

## Evidence

pull-with-autostash-unstages-files-the-user-staged. git 2.56 `pull --rebase=merges --autostash` turned `M  f` into ` M f`. No git option makes autostash keep the index.

## Result

The push line keeps the user's index. The global rule's push wording must name the wrapper; that edit is the orchestrator's.

## Watch

—

## Back-out

Delete the script and its test; the push rule goes back to `git pull --rebase=merges --autostash`.
