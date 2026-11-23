---
type: "Change"
change_type: "removed"
title: "Four rules the coder and reviewer already follow are deleted, 198 fewer words per load"
description: "Four rules the meter found the coder and code-reviewer already follow without them are deleted, 198 fewer words on every coder and code-reviewer load, with no change in behavior."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T23:02:37-06:00"}
seq: 40
kind: "structured"
components: ["skill/coder-core", "agent/code-reviewer"]
evidence: ["rule meter", "removal round"]
watches: []
test: ""
asked: ""
proof: ["2026-11-22-deleting-four-rules-the-coder-and-reviewer-already"]
unmeasured: "No intake number reads these four rules; the removal is read by the rule-meter trials. Not run: a Django or Vue coder fixture for the search-before-writing, red-test and nesting rules, and a Sonnet reviewer run for the nesting line."
---

## Change

- `coder-core`: the nesting bullet (two levels, early return), the `Extend, never copy` section, and the red-test
  sentence in `Tests are yours` come out. About 168 words.
- `code-reviewer`: the nesting, 40-line, chained-ternary and one-liner items come out of the list of structure breaks
  that are a `fix`. About 30 words.

Kept after the check: the async-view rule (same text moves 7/8 and 8/8 vs 0/8 on Opus in two other fixtures), the
named-return-type bullet (a second fixture moves 7/8 vs 0/8), and the unindexed-column rule (moves 8/8 vs 1/8 and 8/8
vs 0/8 on the TypeScript fixtures; only the Django fixture was already caught).

## Evidence

Rule trials G, J, K2 (coder, Sonnet, TypeScript backend fixtures) and AE (code-reviewer, Opus), 8 runs per arm each, 8 of 8 with the rule and 8 of 8 without. Rule meter: with the rule off, the agent already did what the rule asks on every run.

## Result

Coder loads shrink by about 168 words and code-reviewer loads by about 30. The rule meter showed no behavior gain from
any of the four lines.

## Watch

None: see `unmeasured`.

## Back-out

Restore the lines from git.
