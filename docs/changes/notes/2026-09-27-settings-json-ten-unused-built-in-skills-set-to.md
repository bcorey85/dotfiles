---
type: "Change"
change_type: "changed"
title: "settings.json: the skill listing now carries names only, with ten unused built-in skills set to `user-invocable-only`"
description: "settings.json: ten unused built-in skills set to `user-invocable-only`, and `skillListingBudgetFraction` set to 0.0001, so the skill listing carries names only."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-27T00:00:00-05:00"}
seq: 17
kind: "behavior"
components: ["rule/settings-json"]
evidence: ["census", "judgment"]
watches: []
---

## Change

settings.json: ten unused built-in skills set to `user-invocable-only`, and `skillListingBudgetFraction` set to 0.0001, so the skill listing carries names only

## Evidence

census, judgment

## Result

The listing cap already cut every personal skill to its name. The built-ins kept full descriptions and filled the cap, and the work log shows 0 starts for all ten. The listing goes from about 6,100 to about 300 chars: about 1,700 tokens per main request, about 15M a week. The model sees the same personal skill names as before. A future CLI can add a built-in at full size.

## Watch

—

## Back-out

—
