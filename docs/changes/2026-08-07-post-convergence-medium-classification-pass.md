---
type: "Change"
change_type: "removed"
title: "The review loop ends without a separate pass to classify MEDIUM findings"
description: "Reviewers label each finding's disposition when they find it, so the review loop no longer needs a classification pass after it converges."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-08-07T00:00:00-05:00"}
seq: 4
kind: "behavior"
components: ["agent/review-loop"]
evidence: ["follow-on"]
watches: []
---

## Change

The review loop ends without a separate pass to classify MEDIUM findings. Before, that pass ran after the loop converged.

## Evidence

follow-on

## Result

Reviewers label disposition at the point of finding; the pass had nothing left to classify

## Watch

—

## Back-out

—
