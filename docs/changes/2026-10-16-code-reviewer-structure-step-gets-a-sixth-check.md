---
type: "Change"
title: "`code-reviewer` structure step gets a sixth check, helper placement"
description: "`code-reviewer` structure step gets a sixth check, helper placement."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-16T00:00:00-05:00"}
seq: 2
components: ["agent/code-reviewer", "skill/fix"]
evidence: ["seeded round"]
watches: ["share-first-placement"]
---

## Change

`code-reviewer` structure step gets a sixth check, helper placement. It flags logic in a feature module whose inputs and output are plain values and that reads no module type, table or rule, for each new helper and inline block, whatever its caller count. The fix moves it to the shared utility directory. A mixed helper is flagged only for its generic steps, and the rule, its error codes and its limits stay in the module. Disposition `fix`. +88 words

## Evidence

seeded round

## Result

Same tickets. On 12 diffs from coders without the placement rule, each with a buried generic step, the reviewer caught it in 4 of 12 runs without the check and 11 of 12 with it. False flags: 2 of 12 without the check and 1 of 12 with it, and 1 of 12 on the diffs from coders with the rule. Opus reviewer tokens, median: cache read 1.05M against 1.04M, output 29.5K against 27.4K.

## Watch

shared with the coder row.

Reading, 2026-10-28 intake: NO CHANGE, kept. Duplication escapes per code-reviewer run read 0.04 (3 of 79) after against a 0.02 median, inside the 0.00 to 0.11 before range. Three escapes cannot tell this check from the twelve edits that share the window. The seeded catch gain (4 to 11 of 12) stands; read again when the after window reaches 20 escapes.

## Back-out

delete item 6.
