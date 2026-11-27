---
type: "Change"
change_type: "fixed"
title: "lane-status viewer tests run their fake viewer on runners whose sleep is a multicall binary"
description: "Dotfiles master CI goes green: the lane-status viewer tests start their fake hunk process with argv[0] sleep, so a multicall coreutils binary still runs it."
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

The test's fake viewer copies `sleep` to a file named `hunk` and now starts it with `executable=` that file and
argv[0] `sleep`. The process name still comes from the file, so `ps -o comm=` reads `hunk`. The script is unchanged.

## Evidence

Judgment: the GitHub runner's `sleep` is a multicall coreutils binary that picks its tool from argv[0]. Started as
`hunk`, it printed `coreutils: unknown program 'hunk'` and exited, so 9 viewer tests saw no live viewer.

## Result

The viewer tests fail on the runner before and pass after; they pass on this machine both ways.

## Watch

None: the next master CI run shows it.

## Back-out

Revert the one Popen line in `tests/scripts/test_lane_status.py`.
