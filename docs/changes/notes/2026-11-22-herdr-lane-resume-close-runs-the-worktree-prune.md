---
type: "Change"
change_type: "changed"
title: "herdr-lane-resume --close runs the worktree prune, which keeps open lanes"
description: "herdr-worktree-prune keeps a tree inside an open lane's worktree, and keeps every tree when the lane list cannot be read, so a close that runs it never removes an open lane."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-22T20:00:55-06:00"}
seq: 32
kind: "fix"
components: ["script/herdr-worktree-prune"]
evidence: ["tests"]
watches: []
test: "tests/scripts/test_herdr_worktree_prune.py::LaneTest::test_a_tree_with_an_open_lane_entry_is_kept_and_goes_once_the_entry_is_removed"
asked: ""
proof: []
unmeasured: "No count shows how often a prune removed the worktree of a lane that was still open."
---

## Change

`herdr-worktree-prune` reads the lane list through `lanes.py list` (`HERDR_LANES_CLI` overrides the path) each time it builds its view of the world, so the apply-time re-check reads it again. A tree equal to or inside an open lane's worktree is kept with `open lane` and a line naming `herdr-lane-resume --close <name>`. When the list cannot be read (missing tool, non-zero exit, unexpected answer) every tree is kept as `cannot check` and nothing is removed: the check fails closed. The docstring names the new condition and adds `refs/pull-keep-index` to the never-touched list. `herdr-lane-resume --close` runs this prune after it closes the workspace.

## Evidence

The tests build merged, clean, agentless worktrees with a real lane file. They cover an open-lane tree kept and then removed once `lanes.py remove` ran, a name-prefix sibling folder, a missing lane tool, a wrong-shape and a non-JSON answer, and a lane opened between the listing and the apply. The three first tests failed before the code change.

## Result

The prune tests pass (74), lint passes, the script is under 1000 lines, and the full check passed in the review loop (5424 tests, 0 failed). The live probe-lane run is the manual step.

## Watch

A lane file that names a worktree by a path that is a symlink, and the 20 second limit on the lane list call.

## Back-out

Remove `check_lane_open`, `read_lanes`, `LaneRead` and the `lanes` field of `World`, and drop `check_lane_open` from `CHECKS`; revert the test setUp changes and the `LaneTest` class.

