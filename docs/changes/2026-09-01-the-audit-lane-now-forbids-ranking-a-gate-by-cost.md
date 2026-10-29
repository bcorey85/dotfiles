---
type: "Change"
change_type: "changed"
title: "The audit lane now forbids ranking a gate by cost per fixed finding when its output is a triage queue"
description: "The audit lane now forbids ranking a gate by cost per fixed finding when its output is a triage queue, and scores those gates on the share of their findings that were real."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-01T00:00:00-05:00"}
seq: 16
kind: "behavior"
components: ["skill/audit"]
evidence: ["census"]
watches: []
---

## Change

The audit lane now forbids ranking a gate by cost per fixed finding when its output is a triage queue, and scores those gates on the share of their findings that were real

## Evidence

census

## Result

A gate whose findings are scope the ticket-owner must rule on correctly produces deferred and escalated rows, so its fixed count is near zero however well it performs; dividing tokens by that number ranked the completeness gate ten times worse than any reviewer while its false-positive rate was zero.

## Watch

—

## Back-out

—
