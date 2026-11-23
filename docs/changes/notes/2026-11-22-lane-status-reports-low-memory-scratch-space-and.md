---
type: "Change"
change_type: "added"
title: "lane-status reports low memory, scratch space and open lanes that are not working"
description: "lane-status prints low memory, low or crowded scratch space and each open lane with no agent, a missing worktree or a non-working agent, and nothing when all is well."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-22T19:46:07-06:00"}
seq: 31
kind: "fix"
components: ["script/lane-status", "script/system-resources", "script/session-pane"]
evidence: ["tests"]
watches: []
test: "tests/scripts/test_lane_status.py::LaneStatusTest::test_a_failed_du_exits_2"
asked: ""
proof: []
unmeasured: "No count shows how often a lane sat idle or memory ran low unnoticed."
---

## Change

`lane-status` reads memory available (`/proc/meminfo`, or `vm_stat` on macOS), free space on the scratch root and its size, and every lane file entry. It prints one line for low memory, low free scratch space, scratch use over a cap, and each lane with no claude agent, a missing worktree or an agent that is not working. It prints nothing and exits 0 when all is well, exits 1 when it printed, and exits 2 on a bad lane file, a bad threshold, or a failed `herdr-api`, `df` or `du` call. The thresholds come from `LANE_STATUS_MIN_MEMORY_GB`, `LANE_STATUS_MIN_SCRATCH_GB` and `LANE_STATUS_SCRATCH_CAP_GB`.

A lane with several agents is silent when any is working. `du` exiting 1 while it prints a total, as happens when a file vanishes mid-walk, counts as a read. `herdr_agents.agents_in` (lib/herdr_agents.py) now owns the "agents inside a folder" filter that `resolve` and `lane-status` share.

## Evidence

The tests run the tool against stub `herdr-api`, `df` and `du` commands and a temporary lane file. They cover each printed line, each exit code, several agents in one lane, sibling and symlinked folders, a non-claude agent, unreadable memory, the macOS reader with stubs, and bad, nan and infinite thresholds.

## Result

The lane-status tests pass (25), the system-resources tests pass, lint passes, and the full check passed in the review loop (5419 tests, 0 failed). The macOS `vm_stat` path has not run on a Mac.

## Watch

The macOS memory line on a Mac, and a scratch root that holds many files, where `du` may be slow.

## Back-out

Delete `lane-status`, `lane_status.py`, `system_resources.py` and their tests, and revert `session_pane.py` to the inline filter in `resolve_path`.
