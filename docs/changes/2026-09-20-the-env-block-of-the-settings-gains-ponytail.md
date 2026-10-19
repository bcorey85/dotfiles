---
type: "Change"
title: "The `env` block of the settings gains `PONYTAIL_SUBAGENT_MATCHER` with the pattern `^(?!coder)`"
description: "The `env` block of the settings gains `PONYTAIL_SUBAGENT_MATCHER` with the pattern `^(?!coder)`."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-20T00:00:00-05:00"}
seq: 1
components: ["rule/settings-json"]
evidence: ["removal round"]
watches: []
---

## Change

The `env` block of the settings gains `PONYTAIL_SUBAGENT_MATCHER` with the pattern `^(?!coder)`. The Ponytail plugin then adds its rule text (876 words) to every subagent type but the two coder types. No plugin file, agent file, or skill file changed. The main session and every other subagent type keep the text. The settings gate denies a model write to that file, so the line goes in by hand.

## Evidence

removal round

## Result

On the same plan phase with and without the text, every coder run was good in both sets. Each run on a clean tree passed every held-out test with no false stop, and each run on a tree with a planted mismatch between the plan and the code flagged it. Every run wrote the same two files that the plan names, with the same exported types, and no run wrote a test file or a simplification comment. No report in either set used the plugin's short report pattern, so the coder's own report format governs. Without the text the code came out slightly longer, about ten lines in about 175, and its longest function about eight lines longer. Both values sit inside the spread of earlier runs with the text. The text costs about 1,900 tokens in each coder response, which is about 14 thousand Sonnet tokens per coder dispatch, nearly all cache read. The measured medians lay further apart, about 144 thousand against about 204 thousand, but the spread of these totals is wide, so only the arithmetic is claimed. The plan fixed the files, types, and signatures, so the result says nothing about layout choices that a looser plan leaves open, and few runs sit behind each number. Fed each agent type, the plugin's hook script gave no text to the two coder types and the full text to every other type, and a live session that took the pattern from the settings file alone gave a coder prompt with no rule text. Architects and reviewers still get the text, with no measurement.

## Watch

—

## Back-out

—
