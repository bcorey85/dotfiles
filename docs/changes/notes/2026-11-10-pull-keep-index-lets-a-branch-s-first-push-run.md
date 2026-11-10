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
before. With none, it asks origin for `refs/heads/<branch>` (the full ref, so `feature/<branch>` does not count): when
origin has it, it pulls `origin <branch>` with the same keep-index handling; when origin answers that it lacks it, the
script prints one line and exits 0. Any other lookup failure exits 1 with the git error.

## Evidence

judgment: every first push of a new branch through the push line failed, because `git pull` with no upstream exits
non-zero and the `&&` chain stopped before `git push -u`.

## Result

The new tests cover no upstream and no remote branch (exit 0, staged files stay staged), a remote branch whose name
only ends in the local name, a remote branch of the same name (pulled), and no origin (exit 1).

## Watch

None: no intake number counts failed first pushes.

## Back-out

Revert the commit.
