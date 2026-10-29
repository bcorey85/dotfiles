---
type: "Change"
change_type: "changed"
title: "The metrics switch reads only the environment variable"
description: "The metrics writers log only when CLAUDE_TOOLKIT_TELEMETRY=1. The file ~/.claude/toolkit-telemetry no longer turns logging on, and the ~/dev/evals/ folder check is gone because nothing else turns it on."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-24T17:16:55-05:00"}
seq: 17
kind: "behavior"
components: ["script/telemetry-enabled"]
evidence: ["judgment", "tests"]
watches: []
test: ""
unmeasured: "The change decides only whether metrics rows are written, not what any agent does. The intake's toolkit-telemetry line reads the switch on each pull."
---

## Change

- `scripts/telemetry/telemetry_enabled.sh` and `telemetry_enabled.py`: on when `CLAUDE_TOOLKIT_TELEMETRY=1`, off otherwise. The file check and the `~/dev/evals/` folder check are deleted. The folder check never overrode `=1`, so with the file gone it could not change the answer.
- `skills/review/review-scope-check`: its self-check turns the switch on with the variable instead of a file in a fake home.
- Comment wording in `log_agent_usage.py` and `skills/review/log-review-finding`.
- Tests under `tests/scripts/` set the variable in each script's environment instead of making the file. `test_telemetry_enabled.py` proves the file alone leaves the switch off.

## Evidence

Judgment: the user set the switch as an environment variable only. The file was a stopgap for sessions started before the export. It hid a work machine with the switch off: the intake read the file rule as a second way on, and the fix handed to the user named the file.

Tests: the full dotfiles suite passes, 1,953 tests in 51 files.

## Result

Installed 2026-10-24 by editing the live scripts. Neither this machine nor the work machine has the switch file, so neither changes behavior. The work machine exports the variable from 2026-10-24.

## Watch

None. See `unmeasured`.

## Back-out

Restore the previous `telemetry_enabled.sh`, `telemetry_enabled.py` and the touched tests from the dotfiles history.
