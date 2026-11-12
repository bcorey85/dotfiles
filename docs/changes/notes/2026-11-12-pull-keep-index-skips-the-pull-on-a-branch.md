---
type: "Change"
change_type: "fixed"
title: "pull-keep-index skips the pull on a branch rewritten locally"
description: "When the upstream tip is not on HEAD but is in the branch's own reflog, pull_keep_index prints a force-with-lease hint and exits 0 without pulling."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-12T00:17:03-06:00"}
seq: 1
kind: "fix"
components: ["script/pull-keep-index"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_pull_keep_index.py::PullKeepIndexTest::test_a_branch_rewritten_locally_pulls_nothing_and_says_to_force_push"
asked: ""
proof: []
unmeasured: ""
---

## Change

`pull_keep_index.py` checks, after the stopped-rebase check and before anything is set aside, whether `@{u}` (fetched
from the configured remote first, so it is the remote's real tip) resolves, is not an ancestor of HEAD, and its commit
is in the reflog of the local branch (`rev-list --walk-reflogs`). When so, the branch was rewritten here (rebase onto
a squash-merged base, amend, reset), so it prints `<branch> was rewritten locally (the upstream tip <short> was on it
before); nothing pulled. Push with --force-with-lease.` and exits 0. A tip missing from the reflog (another machine
pushed) is pulled as before. When the fetch fails (the upstream is deleted on the remote, or the remote is unreachable), the run goes on to
the usual upstream checks and pull, so a deleted upstream still exits 1 naming it.

## Evidence

judgment: after a local rewrite the script pulled the old remote branch and rebased the rewritten commits onto it,
replaying the squashed commit and stopping on conflicts, so the chained force push never ran.

## Result

The new rewrite test fails on the old tree and passes; the other-machine test passes on both trees; the
pull_keep_index test file passes (26 tests).

## Watch

The decision costs one `git fetch` of the upstream ref per run; a slow or offline remote falls back to the pull.

## Back-out

Revert the commit.
