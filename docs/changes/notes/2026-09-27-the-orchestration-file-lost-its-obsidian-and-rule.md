---
type: "Change"
change_type: "removed"
title: "The orchestration file is shorter: Obsidian, rule-maintenance and two of three judgment items are gone"
description: "The orchestration file is shorter: its Obsidian and rule-maintenance sections and two of its three judgment items (state the approach before non-trivial work, and push back only on material trade-offs) are gone."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-27T00:00:00-05:00"}
seq: 7
kind: "behavior"
components: ["rule/orchestration", "rule/global-claude-md"]
evidence: ["removal round"]
watches: []
---

## Change

The orchestration file is shorter: its Obsidian and rule-maintenance sections and two of its three judgment items (state the approach before non-trivial work, and push back only on material trade-offs) are gone. The unattended rule stays: proceed on the most reasonable reading and record the assumption. The CLAUDE.md pointer no longer names Obsidian or rule maintenance.

## Evidence

removal round

## Result

Without the three sections, the main session acted the same in 6 of 7 tasks. It refused an irreversible delete it could not undo, did a style the user chose with no pushback, proposed a hook instead of only adding emphasis, and flagged a hardcoded path, in both versions. Two rules never fired even with their text present: it stated no approach before a three-file change, and it suggested no vault note after a non-obvious root cause. On an ambiguous unattended request, both versions proceeded with no question. The unattended rule stays by judgment: the only sign of an effect was a scope note in the version with the text, not a stated reading of the request. The three sections added 363 tokens per main-session request. The removal cuts 140 of 159 words, about 320 tokens per request and about 2.8M Opus cache-read tokens a week. One run per task.

## Watch

—

## Back-out

restore the sections from git.
