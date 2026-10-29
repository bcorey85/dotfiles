---
type: "Change"
change_type: "changed"
title: "plan-reviewer and plan-format: no cap on acceptance criteria"
description: "plan-reviewer and plan-format: no cap on acceptance criteria."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-12T00:00:00-05:00"}
seq: 6
kind: "behavior"
components: ["agent/plan-reviewer", "shared/plan-format"]
evidence: ["judgment"]
watches: []
---

## Change

plan-reviewer and plan-format: no cap on acceptance criteria. The reviewer no longer flags a criteria file past 8 criteria, and the plan format no longer says that more than 8 means two tickets

## Evidence

judgment

## Result

The user cannot split a ticket. At work, finished plans carry a median of 72 criteria, so the cap fired on almost every plan and asked for a step that cannot happen. The phase-size and skeleton checks stay.

## Watch

—

## Back-out

restore the sentence in each file
