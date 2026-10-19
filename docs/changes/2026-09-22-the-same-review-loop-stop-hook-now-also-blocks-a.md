---
type: "Change"
title: "The same review-loop stop hook now also blocks a loop that changed code and ran no check afterward"
description: "The same review-loop stop hook now also blocks a loop that changed code and ran no check afterward."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-22T00:00:00-05:00"}
seq: 3
components: ["agent/review-loop"]
evidence: ["census", "judgment"]
watches: []
---

## Change

The same review-loop stop hook now also blocks a loop that changed code and ran no check afterward. When a coder step ran, the loop prompt's tests-run field is not a command with exit 0, and no loop shell call after the last coder step ran a project checker or wrote the review-gate log, the hook blocks the stop and tells the loop to run its execution gate. The hook joins every reason that holds into one block, and blocks one time only. `no-review` exempts only the unread-diff check.

## Evidence

census, judgment

## Result

Effect unmeasured. The loop text already required this gate, and the work logs showed the text alone fell short: 13 of 129 runs with a coder step and no exit-0 tests-run ran a check after the last coder step. When diff reviewers ran checks, 107 of 280 results failed. The aim is output quality, from no loop that returns code no check covered. The price is one quality-check run in each such loop, which can add five minutes or more of wall-clock where the project's tests are slow. A per-fix-coder check was left out for that reason: it would repeat the same run once per coder. Live check: that 13 of 129 share, expected near all.

## Watch

—

## Back-out

restore the earlier script, which blocks only on the unread fix diff.
