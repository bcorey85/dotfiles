---
type: "Change"
change_type: "removed"
title: "Test-writer agent deleted (Claude and opencode copies)"
description: "Test-writer agent deleted (Claude and opencode copies)."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-02T00:00:00-05:00"}
seq: 14
kind: "behavior"
components: ["agent/test-writer", "skill/test-audit", "agent/test-intent-reviewer", "skill/fix", "skill/branch-recap", "shared/closing-phases"]
evidence: ["judgment", "bench smoke"]
watches: []
---

## Change

Test-writer agent deleted (Claude and opencode copies). The test audit and the test-intent reviewer send weak-assertion findings to `/fix`. The README, branch recap, closing phases and audit text no longer name it

## Evidence

judgment, bench smoke

## Result

No dispatcher was left after the review loop stopped sending test gaps to it and the code skill had already dropped it. The coder writes all tests. The Read hook that bound only the test-writer is removed from settings, and its script is deleted.

## Watch

—

## Back-out

restore the deleted files from git
