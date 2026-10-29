---
type: "Change"
change_type: "removed"
title: "The shell-write gate now skips the ownership check when the test-ownership-gate script is absent"
description: "The shell-write gate skips the ownership check when the test-ownership-gate script is absent, and the script, whose agent list was empty, is deleted."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-09T00:00:00-05:00"}
seq: 8
kind: "behavior"
components: ["script/shell-write-gate"]
evidence: ["judgment"]
watches: []
---

## Change

The shell-write gate now skips the ownership check when the test-ownership-gate script is absent, and the script is deleted. Its agent list was empty, so it denied nothing

## Evidence

judgment

## Result

No behavior change. The hook entry was removed from settings earlier. Two comments in hook scripts still name it; hook scripts are write-protected, so they stay

## Watch

—

## Back-out

—
