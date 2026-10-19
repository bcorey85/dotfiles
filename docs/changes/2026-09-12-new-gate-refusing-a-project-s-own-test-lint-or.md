---
type: "Change"
title: "New gate refusing a project's own test, lint or type-check command when it is run a second time with no file"
description: "New gate refusing a project's own test, lint or type-check command when it is run a second time with no file edit in between, telling the caller to send the failing run to a log, read the whole log, fix every failure at once, and run again."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-12T00:00:00-05:00"}
seq: 7
components: ["script/quality-check-cap"]
evidence: ["judgment"]
watches: []
---

## Change

New gate refusing a project's own test, lint or type-check command when it is run a second time with no file edit in between, telling the caller to send the failing run to a log, read the whole log, fix every failure at once, and run again.

## Evidence

judgment

## Result

Re-running a failing check to watch it fail again is the most common way a session spends tokens without moving. The cap is keyed on an edit having happened rather than on a timer, so an honest retry after a fix is never touched. It fails open on every state error and carries a per-command escape, because it protects productivity rather than correctness, and a gate of that kind denying everything over a bookkeeping failure costs more than the behaviour it prevents. Detection is anchored to the start of a command segment, so a command named inside a quoted argument does not register as a run of it.

## Watch

—

## Back-out

—
