---
type: "Change"
change_type: "fixed"
title: "test-ownership-gate: reads the hook input before any early exit, including the skip-flag and empty-list exits"
description: "test-ownership-gate: reads the hook input before any early exit, including the skip-flag and empty-list exits."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-02T00:00:00-05:00"}
seq: 6
kind: "fix"
components: ["script/test-ownership-gate"]
evidence: ["judgment"]
watches: []
---

## Change

test-ownership-gate: reads the hook input before any early exit, including the skip-flag and empty-list exits. Exiting unread broke the pipe for callers that feed it, so piped shell-write checks failed

## Evidence

judgment

## Result

Fixed a regression from the row above. A 300 KB hook input piped in failed 50 of 50 times (exit 141) while one early exit still came before the read, and 0 of 50 after, with and without the skip flag

## Watch

—

## Back-out

—
