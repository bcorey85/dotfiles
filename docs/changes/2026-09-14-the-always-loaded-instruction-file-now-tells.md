---
type: "Change"
title: "The always-loaded instruction file now tells compaction what to keep — decisions with their reasons"
description: "The always-loaded instruction file now tells compaction what to keep — decisions with their reasons, every measured number, open items in order, commit hashes, file paths, and the rules that bind the next step — and what to drop: tool output and narrative."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-14T00:00:00-05:00"}
seq: 1
components: ["rule/global-claude-md"]
evidence: ["judgment"]
watches: []
---

## Change

The always-loaded instruction file now tells compaction what to keep — decisions with their reasons, every measured number, open items in order, commit hashes, file paths, and the rules that bind the next step — and what to drop: tool output and narrative.

## Evidence

judgment

### Anchor reasons

Anchor `CLAUDE.md`, section `## Compact instructions` (evidence: unproven):

35 words. Tells the compaction summary what to keep and drop. Acts only at compaction. Loads in every main session and subagent.

## Result

An automatic compaction is a reset the user did not choose, and the handoff skill already names what a session needs to resume, so the summary must preserve the same items. Without the line, the summarizer's defaults shape the summary, and those favor code and test output over decisions and numbers. The instruction file is the documented place for compaction guidance. Two lines, paid on every session start. Not yet measured.

## Watch

—

## Back-out

—
