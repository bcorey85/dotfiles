---
type: "Change"
change_type: "changed"
title: "Handoff becomes /stop and /go; stop-guessing is removed"
description: "The handoff skill splits into /stop, which writes the state file, and /go, which reads it back; the stop-guessing skill and its opencode command are gone, and /debug sends an outside dead-end to a web search instead."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-08T17:54:04-06:00"}
seq: 7
kind: "user-rule"
components: ["skill/handoff", "skill/stop", "skill/go", "skill/stop-guessing", "skill/debug"]
evidence: ["user rule"]
watches: []
test: ""
asked: "2026-11-08: lets remove my stop-guessing skill. i want to rename handoff to /stop and instead of handoff resume i want /go"
proof: []
unmeasured: ""
---

## Change

- `skills/handoff/` moved to `skills/stop/`. It writes the handoff file and ends with "Now run /clear, then: /go".
- New `skills/go/` holds the old resume mode. It calls `~/.claude/skills/stop/handoff-path`, so files already under `claude-handoff/` still resolve.
- Removed `skills/stop-guessing/` and `opencode/.config/opencode/commands/stop-guessing.md`.
- `skills/debug/SKILL.md`: the two lines that sent an outside dead-end to /stop-guessing now say to WebSearch the exact error and versions.

## Evidence

User rule.

## Result

Names only; the handoff file format and path are unchanged.

## Watch

None.

## Back-out

Revert the commit.
