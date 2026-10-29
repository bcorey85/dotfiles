---
type: "Change"
change_type: "changed"
title: "The escape logger now refuses a row whose non-description value contains a space, instead of writing it"
description: "The escape logger now refuses a row whose non-description value contains a space, instead of writing it."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-01T00:00:00-05:00"}
seq: 1
kind: "behavior"
components: ["script/log-escape"]
evidence: ["census"]
watches: []
---

## Change

The escape logger now refuses a row whose non-description value contains a space, instead of writing it

## Evidence

census

## Result

A caller that quoted one argument too widely swallowed the following key=value pairs into the repository name, so the row logged no stage, no gate, and no lane — and the failure was silent, leaving rows that look valid but cannot be attributed to anything. Rejecting the row makes the caller fix the quoting while the escape is still fresh in mind. Only the description field may contain spaces now; a path with a space in it would be refused, and none has appeared so far.

## Watch

—

## Back-out

—
