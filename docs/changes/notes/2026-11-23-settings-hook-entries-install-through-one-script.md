---
type: "Change"
change_type: "added"
title: "Settings hook entries install through one script line"
description: "A settings.json hook change reaches the user as one settings_hook.py line instead of pasted JSON or a hand-written installer."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-23T23:33:43-06:00"}
seq: 11
kind: "fix"
components: ["script/settings-hook", "shared/lane-brief"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_settings_hook.py::SettingsHookTest::test_add_then_remove_restores_original_bytes"
asked: ""
proof: []
unmeasured: "The new lane-brief line is not metered: no rule-meter fixture has a lane that must change a settings.json hook, so neither arm could show the behavior. It ships on judgment for the orchestrating session to rule on."
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

- New `claude/.claude/scripts/tools/settings_hook.py`: `add` or `remove` one hook entry (event, optional matcher,
  command, optional `if`, `timeout`, `async`) in a settings file. Adding twice writes once. Remove after add gives back
  the original bytes, for a file with no empty hooks object, hook list or group. A file not in `json.dumps(indent=2, ensure_ascii=False)` form is refused unchanged. One line
  names what changed.
- `skills/_shared/lane-brief.md`: a lane sends a settings hook change to its orchestrator as one `settings_hook.py`
  line, never JSON or an installer script.
- `scripts/CLAUDE.md`: owner line for the script.

## Evidence

A lane's hook line reached the user as prose. The agent's Edit on settings.json was blocked, so it wrote and handed a
one-off installer. Earlier lanes also sent JSON for the user to place by hand.

## Result

Before: `settings_hook.py` does not exist, so `test_add_then_remove_restores_original_bytes` fails. After: the 24 tests
in `tests/scripts/test_settings_hook.py` pass. Add then remove on a copy of the live `settings.json` is byte-identical.

## Watch

None: no intake number counts hand-built installers.

## Back-out

Delete the script, its test, its owner line and the lane-brief line.
