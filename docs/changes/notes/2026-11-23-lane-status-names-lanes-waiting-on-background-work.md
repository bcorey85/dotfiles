---
type: "Change"
change_type: "changed"
title: "lane-status names lanes waiting on background work and dead lanes, and prints only changes"
description: "lane-status reports a lane whose idle agent still has background shells or subagents out as waiting, marks a lane dead on no agent, a missing worktree or a transcript that ends on an API error, and with --changes prints only what changed since its last run."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-23T12:03:20-06:00"}
seq: 6
kind: "fix"
components: ["script/lane-status"]
evidence: ["tests"]
watches: []
test: "tests/scripts/test_lane_status.py::LaneStatusTest::test_an_idle_agent_with_an_unreported_background_shell_is_waiting"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

A watcher that polls `lane-status` now tells a lane that stopped to wait on a background run from one that is done. For an agent that is not working, `lane-status` finds its transcript by the herdr session id and counts the background shells and subagents that have not reported back. When any are out it prints `<name>: waiting on <N> background job(s)` in place of the bare `idle`.

Death signs share one shape, `<name>: dead (<reason>)`: `no agent` (workspace closed, killed, out of memory), `worktree gone`, `login expired` (the transcript ends on an API error that asks for a login) and `api error` (any other API error ending).

`lane-status --changes` prints only the lines that differ from its last `--changes` run, plus `<name>: working` for a lane it reported before that works again, so a Monitor loop prints each state once. It keeps the last run in `${XDG_STATE_HOME:-~/.local/state}/lane-status/seen.json`.

## Evidence

Before the fix, a lane that stopped to wait on a background bench and a lane that had finished both printed `idle`, so the watcher woke the orchestrating session for a lane that needed nothing, and printed the same line on every poll.

## Result

`tests/scripts/test_lane_status.py`: 8 of 29 tests fail on the old script (waiting, both API-error deaths, `--changes`, and the four renamed death lines); all 29 pass after. Ruff is clean on both files.

## Watch

None: no intake number counts watcher wake-ups.

## Back-out

Revert `claude/.claude/scripts/tools/lane_status.py` and `tests/scripts/test_lane_status.py`, and delete `~/.local/state/lane-status/seen.json`.
