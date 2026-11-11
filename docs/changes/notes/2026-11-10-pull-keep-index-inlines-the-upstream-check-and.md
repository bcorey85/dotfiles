---
type: "Change"
change_type: "fixed"
title: "pull_keep_index inlines the upstream check and shares the stderr decode"
description: "pull_target checks a gone configured upstream itself and returns explicitly after the exit, and the stderr decode moves to script_utils."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-10T23:26:40-06:00"}
seq: 10
kind: "fix"
components: ["script/pull-keep-index", "script/script-utils"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_pull_keep_index.py::PullKeepIndexTest::test_a_branch_whose_upstream_was_deleted_on_origin_exits_1_so_a_chained_push_does_not_run"
asked: ""
proof: []
unmeasured: ""
---

## Change

`scripts/tools/pull_keep_index.py`: `pull_target` runs the gone-upstream check that `configured_upstream_target` held
and ends in an explicit `return []` after the exit. The helper is gone.
The local `stderr_text` moves to `lib/script_utils.py` as `process_stderr_text`. No behavior change.

## Evidence

judgment: the branch review found the implicit no-return after `exit_upstream_gone` and a generic helper in a tool.

## Result

The pull_keep_index and script_utils tests pass unchanged.

## Watch

None: structure only.

## Back-out

Revert the commit.
