---
type: "Change"
change_type: "changed"
title: "The optional advisory tier every diff reviewer shares is now budgeted: at most two per run"
description: "The optional advisory tier every diff reviewer shares is now budgeted: at most two per run, and none at all in a run that also reports something to fix."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-12T00:00:00-05:00"}
seq: 13
kind: "behavior"
components: ["agent/code-reviewer"]
evidence: ["finding census"]
watches: []
---

## Change

The optional advisory tier every diff reviewer shares is now budgeted: at most two per run, and none at all in a run that also reports something to fix. Over budget the reviewer keeps the two most likely to change how the next file is written and drops the rest, and may not promote a dropped one to the fix tier to keep it.

## Evidence

finding census

## Result

Across every reviewer's logged output the advisory tier is a third to a half of what the two most-used reviewers emit, and nineteen in twenty of those entries changed nothing. Four fifths of the runs that carry one also carry a real defect, so the attention it consumes is taken directly from the findings that matter. A small number of runs emit ten or more at once, which is where the tier stops being a note and becomes a second report. One reviewer already operates at almost no advisories and is the highest-value gate measured, so the tier is not load-bearing. The cost of the cap is the small share that did get fixed; the budget keeps the two best rather than removing the tier, so that share is reduced rather than lost, and the up-labelling ban is what stops the cap from converting into inflated defects.

## Watch

—

## Back-out

—
