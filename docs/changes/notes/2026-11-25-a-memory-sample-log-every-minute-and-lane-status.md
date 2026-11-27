---
type: "Change"
change_type: "added"
title: "a memory sample log every minute and lane-status marks finished idle lanes with their Claude RSS"
description: "A per-minute memory sample log names the top RSS holders by command and herdr workspace, and lane-status --git marks merged lanes with an idle agent as finished idle with their Claude RSS."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T19:23:48-06:00"}
seq: 8
kind: "fix"
components: ["script/memory-sample", "script/process-table", "script/lane-status", "script/install-memory-sample"]
evidence: ["tests/scripts/test_memory_sample.py", "tests/scripts/test_lane_status.py"]
watches: []
test: "tests/scripts/test_memory_sample.py::MemorySampleTest::test_one_line_names_the_top_holders_by_command_and_by_workspace"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

New `lib/process_table.py` reads the process table (Linux /proc, macOS ps, or a fake table for tests). New `tools/memory_sample.py` appends the top 15 holders and MemAvailable to a JSONL rotated at 5 MB; `install/memory-sample` runs it every minute (systemd user timer or LaunchAgent), called from `./setup`. `lane-status --git` marks a merged lane whose agent is idle or done `finished idle` with the summed RSS of Claude processes in its worktree.

## Evidence

The new tests feed a fake process table and pass. The full check passed on the final tree (6728 tests, 0 failed). The installer was only syntax-checked.

## Result

After a freeze, the sample file shows which commands and workspaces held memory in the minutes before it.

## Watch

—

## Back-out

Revert the commit.
