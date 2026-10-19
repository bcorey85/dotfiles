---
type: "Change"
title: "test-ownership-gate: the script is deleted"
description: "test-ownership-gate: the script is deleted."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-09T00:00:00-05:00"}
seq: 8
components: ["script/shell-write-gate"]
evidence: ["judgment"]
watches: []
---

## Change

test-ownership-gate: the script is deleted. Its agent list was empty, so it denied nothing. The shell-write gate skips the ownership check when the script is absent

## Evidence

judgment

## Result

No behavior change. The hook entry was removed from settings earlier. Two comments in hook scripts still name it; hook scripts are write-protected, so they stay

## Watch

—

## Back-out

—
