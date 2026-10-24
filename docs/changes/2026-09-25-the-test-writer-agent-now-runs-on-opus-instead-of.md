---
type: "Change"
title: "The test-writer agent now runs on Opus instead of Sonnet"
description: "The test-writer agent now runs on Opus instead of Sonnet."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-25T00:00:00-05:00"}
seq: 2
components: ["agent/test-writer"]
evidence: ["seeded round"]
watches: ["test-writer-on-opus"]
---

## Change

The test-writer agent now runs on Opus instead of Sonnet. The prompt and tools do not change.

## Evidence

seeded round

## Result

On the same fixed code, over 11 trees and 3 runs per tree, Opus killed 10.0 points more seeded defects (2SE 3.6) and 3.3 points more contract defects (2SE 2.5). False failures on correct code fell by 0.13 per run, and tests red on a second correct build fell by 0.03. Cost per dispatch, median, Sonnet against Opus: fresh 38k against 57k, cache read 177k against 460k, output 10k against 28k. Wall per plan phase: 21 s against 78 s, 54 s more when paired. Opus wrote 2.5 times the test lines, at 5.2 kills per 100 lines against 11.6. Part of the gain can come from sight of the code under test: Opus printed non-test source through the shell in 18 of 33 runs, against 2 of 33. The bench is this machine, a guide only. The runs had no acceptance-criteria file, which live use always has. A second seeded round with the criteria file present, stopped after 3 trees, kept the gain: Opus killed 13.3 points more seeded defects (2SE 3.7), with no rise in false failures. Live check: test-writer tokens by model and wall per phase in the census, and review findings per phase, before and after.

## Watch

Read 2026-10-24 on work logs through 2026-10-21: test-gap and weak-assertion findings per code-reviewer run 0.35 after, against a median of 0.39 (range 0.21 to 0.55) before. No change. The test-writer agent was deleted on 2026-10-02, when the coder took over its tests, so the edit ran one week. Watch closed as reverted.

## Back-out

restore `model: sonnet`.
