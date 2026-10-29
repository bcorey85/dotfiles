---
type: "Change"
change_type: "removed"
title: "`code-reviewer` no longer has to report a differential comparison"
description: "`code-reviewer`'s report no longer has to include a differential comparison."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-08-08T00:00:00-05:00"}
seq: 1
kind: "behavior"
components: ["agent/code-reviewer"]
evidence: ["prior round"]
watches: []
---

## Change

`code-reviewer` no longer has to report a differential comparison. Required-output changes were retired as a line of attack, and this requirement predates the differential patch that was actually measured.

## Evidence

prior round

## Result

Required-output changes were retired as a line of attack; this requirement predates the differential patch that was actually measured

## Watch

—

## Back-out

—
