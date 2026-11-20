---
type: "Change"
change_type: "fixed"
title: "pull_keep_index pulls nothing when the upstream is in HEAD"
description: "pull_keep_index skips the rebase pull when the upstream tip is an ancestor of HEAD, so a local merge of the integration branch keeps its hashes and the push needs no force."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-19T12:55:21-06:00"}
seq: 7
kind: "fix"
components: ["script/pull-keep-index"]
evidence: ["pull-keep-index-rebases-merge-commits-on-push"]
watches: []
test: "tests/scripts/test_pull_keep_index.py::PullKeepIndexTest::test_a_pushed_branch_with_the_integration_branch_merged_in_pulls_nothing_and_keeps_its_hashes"
asked: ""
proof: []
unmeasured: ""
---

## Change

`tools/pull_keep_index.py` reads one upstream relation after the fetch (`UpstreamRelation`). When the upstream is an ancestor of HEAD it prints one line and exits 0 with the index untouched. A locally rewritten branch keeps the force-with-lease message; a branch behind its upstream still pulls.

## Evidence

A pushed feature branch with master merged in locally was rebased by `git pull --rebase=merges`, which rewrote every hash and made the push need a force.

## Result

Three new tests in `test_pull_keep_index.py`: merged-in branch keeps its hashes, a synced branch pulls nothing, a behind branch still pulls; a staged file stays staged in each.

## Watch

None.

## Back-out

Revert the commit.
