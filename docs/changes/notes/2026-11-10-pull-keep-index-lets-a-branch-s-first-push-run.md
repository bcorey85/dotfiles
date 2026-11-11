---
type: "Change"
change_type: "fixed"
title: "pull_keep_index lets a branch's first push run"
description: "On a branch with no upstream, pull_keep_index pulls origin/<branch> when it exists and otherwise exits 0 with nothing set aside, so the chained first `git push -u` runs instead of stopping on a failed pull."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-10T17:51:28-06:00"}
seq: 5
kind: "fix"
components: ["script/pull-keep-index"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_pull_keep_index.py::PullKeepIndexTest::test_a_new_branch_with_no_upstream_and_no_remote_branch_exits_0_and_keeps_staged_files"
asked: ""
proof: []
unmeasured: ""
---

## Change

`scripts/tools/pull_keep_index.py` looks up the upstream before it sets anything aside. With an upstream, it pulls as
before. "No upstream" means no upstream config (`branch.<branch>.merge` unset). A branch whose set upstream does not
resolve (`@{u}` fails: pruned or never fetched) and that its remote says is gone (`ls-remote --exit-code` exits 2)
exits 1 before anything is set aside, naming the gone upstream and the recovery (`git branch --unset-upstream`, then
`git push -u <remote> HEAD`), so a chained push does not recreate it. An unpruned gone upstream resolves `@{u}`, so it ends in the generic pull
failure (still exit 1, so a chained push stops). An upstream that `@{u}` cannot resolve (not fetched, as in a
single-branch clone) but the remote still has goes on to `git pull`, which reads the branch config. With no upstream
config, it asks origin for `refs/heads/<branch>` (the full ref, so `feature/<branch>` does not count): when origin has
it, it pulls `origin <branch>` with the same keep-index handling, then sets `origin/<branch>` as the upstream so a
later bare `git push` works (written as `branch.<branch>.remote` and `.merge` config, so a single-branch clone with no
`origin/<branch>` ref works too); when origin answers that it lacks it, the script prints one line and exits 0. Any
other origin lookup failure or a failed upstream set exits 1 with the git error; a failed branch-name lookup exits 1
naming the failed command.

## Evidence

judgment: every first push of a new branch through the push line failed, because `git pull` with no upstream exits
non-zero and the `&&` chain stopped before `git push -u`.

## Result

The new tests cover no upstream and no remote branch (exit 0, staged files stay staged), a remote branch whose name
only ends in the local name, a remote branch of the same name (pulled, and `@{u}` then resolves to it), a set upstream
deleted on origin and pruned (exit 1 with the recovery message, staged files stay staged), a gone upstream on a
non-origin remote (names that remote), a set upstream deleted on origin and not pruned (exit 1 through the failed pull,
staged files stay staged), a failed configured-remote lookup and a missing remote URL (each exit 1 with the lookup
error), a single-branch clone with no `origin/<branch>` ref (pulled, exit 0, upstream config, remote and merge,
written; a second run with the upstream set and no remote-tracking ref pulls and exits 0), a folder where the branch
lookup fails (exit 1), and no origin (exit 1).

## Watch

None: no intake number counts failed first pushes.

## Back-out

Revert the commit.
