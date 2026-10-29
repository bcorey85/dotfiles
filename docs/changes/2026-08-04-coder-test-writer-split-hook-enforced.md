---
type: "Change"
change_type: "changed"
title: "Tests are now written by a separate test-writer, enforced by a hook"
description: "A hook now keeps test writing with the test-writer agent and out of the coder's hands; bug-pinning tests fall to about 0 per run for about +35% spend."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-08-04T00:00:00-05:00"}
seq: 8
kind: "behavior"
components: ["agent/test-writer"]
evidence: ["2 rounds"]
watches: []
---

## Change

The coder and the test-writer are now split, and a hook enforces the split. Bug-pinning tests fall to about 0 per run, at a price of about +35% spend.

## Evidence

2 rounds

## Result

Bug-pinning rate → ~0/run. Price: ~+35% spend. **Kept**

## Watch

—

## Back-out

—
