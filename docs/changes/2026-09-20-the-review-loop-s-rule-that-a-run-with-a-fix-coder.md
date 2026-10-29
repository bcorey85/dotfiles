---
type: "Change"
change_type: "fixed"
title: "The review loop's end-on-a-reviewer rule now names the one caller flag that is exempt"
description: "The review loop's rule that a run with a fix coder ends on a reviewer now names the one caller flag that is exempt."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-20T00:00:00-05:00"}
seq: 15
kind: "fix"
regression: "2026-09-20-the-review-loop-now-ends-every-run-that-dispatched"
components: ["agent/review-loop"]
evidence: ["judgment"]
watches: []
---

## Change

The review loop's rule that a run with a fix coder ends on a reviewer now names the one caller flag that is exempt. That flag returns converged with no reviewer by design, so the rule as written was false on that path.

## Evidence

judgment

## Result

Effect unmeasured. The flag appears in no saved run, so the path is real in the file and unexercised in the data.

## Watch

—

## Back-out

—
