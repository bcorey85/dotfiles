---
type: "Change"
title: "The per-finding review logger now refuses a row whose non-free-text value contains a space"
description: "The per-finding review logger now refuses a row whose non-free-text value contains a space, and its call template passes context fields as an array instead of one unquoted string."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-01T00:00:00-05:00"}
seq: 4
components: ["script/log-review-finding"]
evidence: ["census"]
watches: []
---

## Change

The per-finding review logger now refuses a row whose non-free-text value contains a space, and its call template passes context fields as an array instead of one unquoted string

## Evidence

census

## Result

The template packed five context fields — repository, branch, lane, scope, phase, iteration — into a single shell variable that was correct only while left unquoted, in a toolkit whose every other rule trains callers to quote. Quoting it collapsed all five into the repository name, which happened on nearly every row in the log and destroyed the join keys the per-gate report depends on: which branch a finding belongs to, and whether two gates named the same place. An array is correct under quoting, and the guard makes the old shape fail loudly instead of logging a row that looks valid.

## Watch

—

## Back-out

—
