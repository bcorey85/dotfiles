---
type: "Change"
change_type: "fixed"
title: "pull_keep_index merges the remote when a rebase replay re-conflicts"
description: "When the pull's rebase stops on a conflict a plain merge of the remote would not have, pull_keep_index aborts the rebase and merges the remote instead."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-12T16:26:52-06:00"}
seq: 4
kind: "fix"
components: ["script/pull-keep-index"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_pull_keep_index.py::PullKeepIndexTest::test_a_replayed_merge_that_had_resolved_conflicts_falls_back_to_a_merge_of_the_remote"
asked: ""
proof: []
unmeasured: ""
---

## Change

`tools/pull_keep_index.py`: a failed rebase pull now runs `merge_in_place_of_rebase`. It reads the branch tip from the
rebase state, asks `git merge-tree --write-tree --quiet <tip> FETCH_HEAD` whether a merge is clean, and when it is,
runs `rebase --abort` and `merge --no-edit FETCH_HEAD`. A merge that would conflict too, or a git without
`merge-tree --write-tree`, keeps the old mid-rebase stop.

## Evidence

judgment: on a branch that had merged master with resolved conflicts, the pull's rebase replayed those merges and
stopped on the same conflicts again, so the push line failed.

## Result

The new test fails against master's script and passes; `test_pull_keep_index.py` passes (27 tests).

## Watch

None: a fallback path with a fixed outcome.

## Back-out

Revert the commit.
