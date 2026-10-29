---
type: "Change"
change_type: "changed"
title: "The plan format and verify-branch skill now describe the gate, moved-phase and verdict-row rules"
description: "The shared plan format says that /code stops at an open gated phase and documents the `[-]` moved-phase mark. The verify-branch skill says that verify-log exits 2 when a criterion id has no row."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-23T07:28:51-05:00"}
seq: 1
kind: "behavior"
components: ["skill/plan-format", "skill/verify-branch"]
evidence: ["judgment"]
watches: []
---

## Change

- `skills/_shared/plan-format.md`, Format rules:
  - The gate line says that `/code` stops at an open gated phase and starts no later phase. Before, it said that `/code` skips a gated phase.
  - New line: a phase moved to another ticket is `- [-] Phase N: <title> — moved to <KEY>`, with a Plan Deviations line that names the phase, the key and the user's sign-off.
- `skills/verify-branch/SKILL.md`, Step 3: the agent sends a row for every criterion id. An id with no row makes the script exit 2 and write nothing. Before, the text said that the script logs such an id as `missing`.

## Evidence

- Judgment: the scripts changed on 2026-10-22, and the old text described the old behavior. A plan writer had no way to learn the `[-]` mark except from a failed parse.

## Result

The skill text and the scripts agree. Neither file has rows in the rule-anchors sidecar, so no anchor changed.

## Watch

None.

## Back-out

Restore both files from git.
