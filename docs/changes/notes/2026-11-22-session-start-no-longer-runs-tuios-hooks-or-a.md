---
type: "Change"
change_type: "removed"
title: "Session start no longer runs tuios hooks or a second skip-hooks warning"
description: "settings.json drops all 14 tuios agent-hook registrations and the Python copy of the skip-hooks warning, so every tool call and session start spawns 15 fewer processes and the skip warning prints once."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T12:06:58-06:00"}
seq: 15
kind: "user-rule"
components: ["rule/settings", "script/warn-skip-hooks"]
evidence: ["user rule", "judgment"]
watches: []
test: ""
asked: "2026-11-22: asked by the user"
proof: []
unmeasured: ""
---

## Change

`claude/.claude/settings.json` loses 15 hook registrations: the 14 `tuios agent-hook` commands and
`scripts/gates/warn_skip_hooks.py`. The events left with no hook (ElicitationResult, PermissionDenied,
PermissionRequest, SubagentStart) are gone from the file. The shell `warn-skip-hooks.sh` registration stays, so a
session started with `CLAUDE_SKIP_HOOKS` set still sees one warning instead of two.

`scripts/gates/warn_skip_hooks.py` and `tests/scripts/test_warn_skip_hooks.py` are deleted. `orchestration.md`
### Git no longer names tuios beside herdr.

Left alone: the tuios branches inside the herdr scripts, which only run when tuios is present.

## Evidence

The user does not use tuios. The two skip-hooks warnings printed the same message.

## Result

The rest of settings.json is byte-identical (a JSON round trip of the old file matched it exactly before the trim).

## Watch

None. No intake number reads hook registrations.

## Back-out

Revert the commit; the 15 registrations and the script come back.
