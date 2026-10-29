---
type: "Change"
change_type: "removed"
title: "The `eng-spec` finalize phase now states its rules without four escape citations"
description: "The `eng-spec` finalize phase loads fewer words (1,561 to 1,482) because it no longer cites four escapes by ticket ID, date and what each one broke. Every rule stays word for word."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-17T00:00:00-05:00"}
seq: 5
kind: "behavior"
components: ["skill/eng-spec"]
evidence: ["judgment"]
watches: []
---

## Change

The `eng-spec` finalize phase now states its rules without four escape citations (ticket IDs, dates and what each escape broke). Every rule they followed stays word for word

## Evidence

judgment

## Result

The eng-spec load at one time drops from 1,561 to 1,482 words, under the 1,500 ceiling, so the word-budget hook allows growing edits again. The citations were provenance, and none of them gave the agent a step to do

## Watch

—

## Back-out

—
