---
type: "Change"
change_type: "fixed"
title: "The scratchpad sweep spares every running session's folder, not only the starting one"
description: "A session paused for a day or more keeps its scratchpad when another session starts."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-07T13:53:31-06:00"}
seq: 10
kind: "fix"
components: ["script/sweep-scratchpads"]
evidence: ["incident"]
watches: []
test: "tests/scripts/test_sweep_scratchpads.py::SweepScratchpadsTest::test_a_running_session_s_folder_is_kept_however_old"
asked: ""
proof: []
unmeasured: ""
---

## Change

`scripts/tools/sweep_scratchpads.py` now keeps the folder of every session still running, not only the session in the hook input. A session is running when `<config>/sessions/<pid>.json` names its `sessionId` and that pid is alive (`os.kill(pid, 0)`; a permission error counts as alive). `<config>` is `CLAUDE_CONFIG_DIR` when set, else `~/.claude`. An unreadable or malformed record is skipped, so the hook still fails open.

## Evidence

On 2026-11-07 a live session (its pid still running) lost its whole scratchpad, suite logs included, after a five-day pause: another session's start found the folder untouched for over 24 hours and deleted it.

## Result

The sweep's test file passes 9 of 9. The running-session test fails on the previous script and passes on this one. A record with a dead pid still lets its stale folder go.

## Watch

None: no intake number reads temp-folder deletions.

## Back-out

Revert this commit; the sweep goes back to sparing only the starting session.
