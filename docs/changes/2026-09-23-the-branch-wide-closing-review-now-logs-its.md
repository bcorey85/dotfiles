---
type: "Change"
change_type: "changed"
title: "The branch-wide closing review now logs its findings with the branch-exit scope"
description: "The branch-wide closing review now logs its findings with the branch-exit scope, so the finding log separates it from the per-phase reviews by scope instead of by agent name."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-23T00:00:00-05:00"}
seq: 4
kind: "behavior"
components: ["shared/finding-log"]
evidence: ["judgment"]
watches: []
---

## Change

The branch-wide closing review now logs its findings with the branch-exit scope, so the finding log separates it from the per-phase reviews by scope instead of by agent name.

## Evidence

judgment

## Result

The deleted deep reviewer name was the only mark on these rows. The log already defines the branch-exit scope for closing-phase gates. Effect unmeasured. Live check: closing-review rows in the finding log carry the branch-exit scope.

## Watch

—

## Back-out

—
