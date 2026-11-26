---
type: "Change"
change_type: "added"
title: "lane-status --git prints each lane's branch state"
description: "lane-status --git prints each open lane's branch, merged or ahead/behind against origin's default branch, dirty file count and reports_to."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T19:23:48-06:00"}
seq: 5
kind: "fix"
components: ["script/lane-status", "script/script-utils", "script/verify-common"]
evidence: ["tests/scripts/test_lane_status.py", "tests/scripts/test_script_utils.py"]
watches: []
test: "tests/scripts/test_lane_status.py::LaneStatusTest::test_git_prints_each_lanes_branch_state"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`tools/lane_status.py` takes `--git`. The default branch comes from the new shared `script_utils.remote_default_branch` (origin/HEAD, else origin/master, else origin/main); `review/verify_common.py` drops its own copy and calls the shared one (ruling A by agent-evals-c3-owner).

## Evidence

The new tests fail on the old tree (no `--git` mode) and pass on the new one. The full check passed on the final tree (6728 tests, 0 failed).

## Result

An orchestrator reads every lane's merge state in one command instead of a git call per worktree.

## Watch

—

## Back-out

Revert the commit.
