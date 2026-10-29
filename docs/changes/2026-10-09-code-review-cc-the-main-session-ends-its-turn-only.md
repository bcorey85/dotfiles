---
type: "Change"
change_type: "changed"
title: "`/code`, `/review`, `/cc`: the main session ends its turn only at the skill's own stops"
description: "`/code`, `/review`, `/cc`: the main session ends its turn only at the skill's own stops; elsewhere it takes the next reversible in-scope step and reports after, asking only before an irreversible or outward step or a real fork."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-09T00:00:00-05:00"}
seq: 3
kind: "behavior"
components: ["skill/code", "skill/review", "skill/cc"]
evidence: ["census"]
watches: []
---

## Change

`/code`, `/review`, `/cc`: the main session ends its turn only at the skill's own stops; elsewhere it takes the next reversible in-scope step and reports after, asking only before an irreversible or outward step or a real fork

## Evidence

census

## Result

Work logs, dotfiles and agent-evals sessions excluded, Oct 3–9: 193 turn ends a day waited on a human reply. 46 a day were permission questions and 113 a day ended with no question; 209 of those got a bare go-ahead (138 permission, 71 no question). Permission questions rose from 30 to 46 a day against Aug 31–Oct 2. No bench: the stop census measures the target directly. Effect on work: watch permission questions and go-ahead replies per day fall in the next intake's stop census, with choice questions and interruptions not rising.

## Watch

—

## Back-out

delete the bold paragraph under `## Instructions` in each of the three skills
