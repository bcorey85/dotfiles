---
type: "Change"
change_type: "fixed"
title: "Calibration and mutation locks move out of the Claude config folder"
description: "The mutation tester and /calibrate write their lock and backups under the XDG state folder, not under ~/.claude. The auto-mode classifier denied writes under ~/.claude, so mutation runs ended INDETERMINATE."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-21T08:08:02-05:00"}
seq: 10
kind: "fix"
components: ["agent/mutation-tester", "skill/calibrate", "script/calibration-guard"]
evidence: ["work incident", "tests"]
watches: []
---

## Change

- `agents/mutation-tester.md` and `skills/calibrate/SKILL.md`: the lock is `${XDG_STATE_HOME:-$HOME/.local/state}/claude-calibration/lock.json`, and backups go to `backups/<basename>.bak` in the same folder.
- `agents/mutation-tester.md`, Step 2: "Never `sed -i`; a hook blocks it."
- `scripts/calibration-guard.py`: the start-up check reads the new lock path, and still reports a lock at the old path.

## Evidence

Work incident: in one work slice, the mutation tester applied a mutation with `sed -i`, and a hook blocked it. The classifier also denied its lock write under `~/.claude`. Two mutants ended INDETERMINATE, so the test audit left two of its findings open.

## Result

Staged 2026-10-21 in the script fix batch. The guard tests pass (20). Installed 2026-10-21.

## Watch

None. No intake metric counts mutation verdicts.

## Back-out

Restore the previous `calibration-guard.py`, `mutation-tester.md` and `calibrate/SKILL.md` from the dotfiles history.
