---
type: "Change"
change_type: "changed"
title: "pull_keep_index records the upstream on the remote it pulled from"
description: "set_upstream takes the remote from the pull target instead of naming origin a second time, and one helper reads the branch's upstream ref."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-10T22:27:03-06:00"}
seq: 8
kind: "fix"
components: ["script/pull-keep-index"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_pull_keep_index.py::PullKeepIndexTest::test_a_branch_with_no_upstream_pulls_the_remote_branch_of_the_same_name"
asked: ""
proof: []
unmeasured: ""
---

## Change

`scripts/tools/pull_keep_index.py`: the `FALLBACK_REMOTE` constant names `origin` once for `pull_target`'s lookup and pull target, `configured_remote`'s default and the no-upstream message, and
`set_upstream(repo, remote, branch)` writes the remote it is given, so the pull and the recorded upstream cannot name
different remotes. `script_utils.branch_merge_ref` replaces two copies of the `branch.<branch>.merge` read. No behavior change.

## Evidence

judgment: the branch smell review found the remote written out in three places that must agree.

## Result

The pull_keep_index tests pass unchanged, including the one that asserts `@{u}` resolves to `origin/shared` after a
targeted pull.

## Watch

None: structure only.

## Back-out

Revert the commit.
