---
type: "Change"
change_type: "removed"
title: "The unattended rule and its Engineering Judgment heading left the orchestration file"
description: "The unattended rule and its Engineering Judgment heading left the orchestration file, and the CLAUDE.md pointer no longer names working judgment."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-27T00:00:00-05:00"}
seq: 8
kind: "behavior"
components: ["rule/orchestration", "rule/global-claude-md"]
evidence: ["removal round"]
watches: []
---

## Change

The unattended rule and its Engineering Judgment heading left the orchestration file, and the CLAUDE.md pointer no longer names working judgment.

## Evidence

removal round

## Result

With and without the rule, the main session proceeded on an ambiguous request made while the user was away, and asked no question. Neither version stated its reading of the request. The rule showed no effect, so it goes. It saves about 45 tokens per main-session request, about 0.4M Opus cache-read tokens a week. One run per task.

## Watch

—

## Back-out

restore the section from git.
