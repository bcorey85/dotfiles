---
type: "Change"
title: "The escape logger's class list now matches the per-finding logger's"
description: "The escape logger's class list now matches the per-finding logger's, and names the handful of retired values older rows carry as legacy never to be remapped."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-01T00:00:00-05:00"}
seq: 13
components: ["script/log-escape", "script/log-review-finding"]
evidence: ["census"]
watches: []
---

## Change

The escape logger's class list now matches the per-finding logger's, and names the handful of retired values older rows carry as legacy never to be remapped

## Evidence

census

## Result

The two logs exist to cross-tabulate the caught and escaped sides, and the escape side's documented list was missing values live rows already use, so a correct row looked invented. The retired values are a fifth of a percent of rows — small enough to report as legacy, and remapping them on judgment would launder old classifications into current counts.

## Watch

—

## Back-out

—
