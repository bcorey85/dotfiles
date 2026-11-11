---
type: "Change"
change_type: "fixed"
title: "pull_keep_index moves its git questions to script_utils"
description: "The remote-ref lookup and the branch merge-ref and remote reads move to script_utils, and the pipe check's comments say when a bar is a pipe."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-11T12:45:00-06:00"}
seq: 11
kind: "fix"
components: ["script/pull-keep-index", "script/script-utils", "script/pipe-shell-check"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_pull_keep_index.py::PullKeepIndexTest::test_a_branch_whose_upstream_was_deleted_on_origin_exits_1_so_a_chained_push_does_not_run"
asked: ""
proof: []
unmeasured: ""
---

## Change

`scripts/tools/pull_keep_index.py`: `lookup_remote_ref` and `configured_merge_ref` move to `lib/script_utils.py` as
`remote_ref_state` and `branch_merge_ref`, and `configured_remote` reads the branch remote through the new
`branch_remote`. `scripts/tools/pipe_shell_check.py`: the comment and docstring say a bar
before a shell name is a pipe unless it is the second bar of `||`, and that an odd run of backslashes escapes the
first bar. No behavior change.

## Evidence

judgment: the branch review found three plain git questions in a tool and a false comment.

## Result

The pull_keep_index, pipe_shell_check, script_utils and gate replay tests pass unchanged.

## Watch

None: structure and comments only.

## Back-out

Revert the commit.
