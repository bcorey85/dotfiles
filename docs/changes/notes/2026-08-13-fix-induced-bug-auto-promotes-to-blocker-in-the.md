---
type: "Change"
change_type: "changed"
title: "fix_induced=bug auto-promotes to blocker in the review loop's finding log"
description: "fix_induced=bug auto-promotes to blocker in the review loop's finding log."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-08-13T00:00:00-05:00"}
seq: 2
kind: "behavior"
components: ["agent/review-loop", "shared/finding-log"]
evidence: ["judgment"]
watches: []
---

## Change

fix_induced=bug auto-promotes to blocker in the review loop's finding log

## Evidence

judgment

## Result

A bug the loop itself introduced cannot be deferred to branch exit — the loop owns it. The TDZ crash (escape #101) is the canonical case: the loop's fix introduced a crash, the loop reported it verified, but verification only re-ran unit tests. 16 fix_induced findings in the first week, 13 deferred, 0 escalated. The rule closes the gap.

## Watch

—

## Back-out

—
