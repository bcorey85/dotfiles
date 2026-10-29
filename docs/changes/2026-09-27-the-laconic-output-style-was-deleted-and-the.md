---
type: "Change"
change_type: "removed"
title: "The Laconic output style was deleted, and the settings no longer name an output style"
description: "The Laconic output style was deleted, and the settings no longer name an output style."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-27T00:00:00-05:00"}
seq: 5
kind: "behavior"
components: ["rule/laconic-output-style", "rule/global-claude-md"]
evidence: ["removal round", "judgment"]
watches: []
---

## Change

The Laconic output style was deleted, and the settings no longer name an output style. The global CLAUDE.md pointer to it was deleted. The per-turn style line from the user prompt hook stays: verdict first, under 100 words, plain words, short sentences. The main session now gets the default coding instructions plus that line.

## Evidence

removal round, judgment

### Anchor reasons

Anchor `rules/testing.md`, section `# Testing` (evidence: unproven):

25 words. Three test style commands. Loads when a matching test file is read.

Anchor `rules/frontend-style.md`, section `# Frontend Style` (evidence: unproven):

110 words. Eleven style commands. The brace rule says that lint fails CI without it, so lint enforces that half. Loads when a matching file is read.

## Result

On this machine, not the work machine, four versions answered the same 10 questions. With the hook line alone, the median answer was 100 words and 607 output tokens, against 105 words and 599 tokens with the style and the line. A hand-read found 22 of 24 key facts in both. The style added only grammar: 2 contractions and weak modals over 10 answers with it, 14 without it. With neither the style nor the line, answers ran 280 words and 1,452 output tokens. The style cost 1,157 tokens on every main-session request, about 10M Opus cache-read tokens a week at the work request rate.

## Watch

—

## Back-out

restore the style file from git and set `outputStyle` to `Laconic`.
