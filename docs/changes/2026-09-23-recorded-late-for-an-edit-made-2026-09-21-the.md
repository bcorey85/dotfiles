---
type: "Change"
change_type: "changed"
title: "The refactor skill's description now gives one clause per mode (recorded late, edit made 2026-09-21)"
description: "Recorded late, for an edit made 2026-09-21: the refactor skill's description now gives one clause per mode."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-23T00:00:00-05:00"}
seq: 2
kind: "behavior"
components: ["skill/refactor"]
evidence: ["judgment"]
watches: []
---

## Change

Recorded late, for an edit made 2026-09-21: the refactor skill's description now gives one clause per mode. It no longer lists what the simplify mode deletes, the audit mode's method or its no-coders note, or the "debt audit" and "reduce the complexity in X" trigger phrases.

## Evidence

judgment

### Anchor reasons

Anchor `skills/refactor/SKILL.md`, section `(preamble)` (evidence: judgment):

Frontmatter: name, description with the four modes by argument and their triggers, and the allowed tools. The description now gives one clause per mode. Gone: the simplify mode's list of what it deletes, the audit mode's method and its no-coders note, and the "debt audit" and "reduce the complexity in X" triggers. The shorter text was not measured.

## Result

Effect unmeasured. The description is what the model reads when it picks a skill on its own, so the lost trigger phrases can change routing: a request phrased as a debt audit or a complexity cut is less likely to reach the skill unless the user types the command. The cut shortens the always-loaded skill listing. Live check: the census count of refactor skill calls by mode, before and after.

## Watch

—

## Back-out

restore the prior description.
