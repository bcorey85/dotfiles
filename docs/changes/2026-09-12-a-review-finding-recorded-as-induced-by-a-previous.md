---
type: "Change"
title: "A review finding recorded as induced by a previous fix is now always recorded as blocking"
description: "A review finding recorded as induced by a previous fix is now always recorded as blocking, whether or not the caller said so."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-12T00:00:00-05:00"}
seq: 10
components: ["script/log-review-finding"]
evidence: ["judgment"]
watches: []
---

## Change

A review finding recorded as induced by a previous fix is now always recorded as blocking, whether or not the caller said so.

## Evidence

judgment

## Result

The rule was already written down in the shared specification both loggers read, and enforced only by the caller remembering it. A defect the loop introduced while repairing another one is the class least safe to defer, and the one a caller under time pressure is most likely to file as ordinary.

## Watch

—

## Back-out

—
