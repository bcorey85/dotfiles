---
type: "Change"
title: "Orchestration rules, delegation: the main session does not read a file only to hand it to a subagent that"
description: "Orchestration rules, delegation: the main session does not read a file only to hand it to a subagent that will read it."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-14T00:00:00-05:00"}
seq: 1
components: ["rule/orchestration"]
evidence: ["census"]
watches: []
---

## Change

Orchestration rules, delegation: the main session does not read a file only to hand it to a subagent that will read it. It sends the path and what to look for, and reads in main only when the content decides what to dispatch. +37 words, main session only

## Evidence

census

### Anchor reasons

Anchor `orchestration.md`, section `# Orchestration` (evidence: unproven):

Title only, 2 words. Main session only, through the session start hook.

## Result

Work logs, main Opus sessions over 14 days: file reads in main are the largest growth source, 2.86M cache write a week (17% of growth). 47% of those read tokens were files a later subagent read again (coder 24%, architect 6%, code reviewer 4%), a median of 19 main requests before the dispatch. Ceiling: 1.3M Opus cache write and an estimated 25M to 42M Opus cache read a week; the share the rule captures is unmeasured. Cuts no review or check.

## Watch

the re-read share in the main-growth census on the next two intakes, against this one's 46.6%.

## Back-out

delete the bullet
