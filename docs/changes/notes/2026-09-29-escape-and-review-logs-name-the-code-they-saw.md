---
type: "Change"
change_type: "changed"
title: "Escape and review logs now record the commit they saw and whether the tree was dirty"
description: "Escape and review logs name the code they saw: every review-log row records the commit and whether the tree was dirty, and the PR-comment step logs each escape with its line and the comment's commit."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-29T00:00:00-05:00"}
seq: 8
kind: "behavior"
components: ["script/log-review-metrics", "skill/pr-comments", "script/log-escape"]
evidence: ["census"]
watches: []
---

## Change

Escape and review logs name the code they saw: every review-log row records the commit and whether the tree was dirty, and the PR-comment step logs each escape with its line and the comment's commit. Additive fields, no schema bump

## Evidence

census

## Result

The PR and walkthrough bug escapes carried only date, repo and file, so no count could say whether the review saw the escaped line. The escape logger also records its own commit

## Watch

—

## Back-out

—
