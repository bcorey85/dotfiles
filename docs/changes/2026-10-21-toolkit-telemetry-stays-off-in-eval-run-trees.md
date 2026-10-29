---
type: "Change"
change_type: "changed"
title: "Toolkit telemetry stays off in eval run trees unless a run turns it on"
description: "The telemetry switch is off for a session whose project folder is inside ~/dev/evals/, unless CLAUDE_TOOLKIT_TELEMETRY=1. CLAUDE_TOOLKIT_TELEMETRY=0 turns it off everywhere, even when the switch file exists. Eval runs no longer write test rows into the live logs."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-21T12:17:11-05:00"}
seq: 16
kind: "behavior"
components: ["script/telemetry-enabled"]
evidence: ["census", "tests"]
watches: []
---

## Change

- `scripts/telemetry_enabled.sh` and `scripts/telemetry_enabled.py`, with the same behavior:
  - `CLAUDE_TOOLKIT_TELEMETRY=0` is off, even when `~/.claude/toolkit-telemetry` exists.
  - `CLAUDE_TOOLKIT_TELEMETRY=1` is on, even inside `~/dev/evals/`.
  - Otherwise, a project folder inside `~/dev/evals/` is off. The project folder is `CLAUDE_PROJECT_DIR`, or the current folder when that is unset. Symlinks are resolved, and whole path parts are compared.
  - Otherwise the switch file turns telemetry on, as before.
- `tests/scripts/test_telemetry_enabled.py`: a new test file. It runs each case against both scripts.

## Evidence

Census: the ledger doctor found 7 rows in the live logs that came from eval harness runs. The switch file exists on this machine, so every headless run in an eval tree logged into the live files, and no environment variable could turn that off. Those rows mix test runs into the data that the live logs keep for this machine.

Trade: an eval harness that reads its rows from a log in the run folder must now set `CLAUDE_TOOLKIT_TELEMETRY=1`, or it writes no rows. The agent-evals housekeeping queue lists the harnesses that need it. A code review found two defects with a missing folder and a gap in the tests. They were fixed before install.

## Result

Staged 2026-10-21 in the third script fix batch. 32 tests pass on the staged copies. After the fix round, 66 tests pass on the staged copies, and 30 of them fail against the installed scripts. Existing rows stay as they are. Installed 2026-10-21. The full suite passed: 1,461 tests in 39 files.

## Watch

None. The fix stops rows from being written. No intake metric counts eval rows in the live logs.

## Back-out

Restore the previous `telemetry_enabled.sh` and `telemetry_enabled.py` from the dotfiles history, and delete `test_telemetry_enabled.py`.
