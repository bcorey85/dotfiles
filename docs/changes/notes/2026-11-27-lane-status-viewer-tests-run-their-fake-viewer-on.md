---
type: "Change"
change_type: "fixed"
title: "lane-status viewer tests run their fake viewer on runners whose sleep is a multicall binary"
description: "Dotfiles master CI goes green: the lane-status viewer tests copy perl, not sleep, as their fake hunk process, so a multicall coreutils binary no longer refuses to run."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-27T17:25:41-06:00"}
seq: 5
kind: "fix"
components: ["script/lane-status"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_lane_status.py::LaneStatusTest::test_a_viewer_over_the_cap_is_named_with_its_lane"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

The test's fake viewer copies `perl` to a file named `hunk` and runs `hunk -e 'sleep 60'`, in place of a copy of
`sleep`. `ps -o comm=` still reads `hunk`. The script is unchanged. Starting the `sleep` copy with argv[0] `sleep` did
not help: the multicall binary reads its tool name from the file, not argv[0].

## Evidence

Judgment: the GitHub runner's `sleep` is a multicall coreutils binary that picks its tool from argv[0]. Started as
`hunk`, it printed `coreutils: unknown program 'hunk'` and exited, so 9 viewer tests saw no live viewer.

## Result

The viewer tests fail on the runner before and pass after; they pass on this machine both ways.

## Watch

None: the next master CI run shows it.

## Back-out

Revert the copy and Popen lines in `tests/scripts/test_lane_status.py`.
