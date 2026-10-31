---
type: "Change"
change_type: "changed"
title: "`code-reviewer` checks each added line against every written rule in the conventions doc, the docs it names and the loaded CLAUDE.md files"
description: "`code-reviewer` checks each added line against each written rule in the conventions doc, the docs it names, and the loaded CLAUDE.md files."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-12T00:00:00-05:00"}
seq: 14
kind: "behavior"
components: ["agent/code-reviewer", "rule/global-claude-md", "skill/fix"]
evidence: ["sealed bench round"]
watches: []
proof: ["2026-10-12-namefix-sealed-8-runs-per-arm"]
impact: {"metric": "quality", "before": 15, "after": 1, "unit": "planted naming breaks not filed as fix (of 64)", "finding": "2026-10-12-namefix-sealed-8-runs-per-arm", "better": "lower"}
---

## Change

`code-reviewer` checks each added line against each written rule in the conventions doc, the docs it names, and the loaded CLAUDE.md files. A broken written rule is a `fix` that quotes the rule, never a `nit`; the naming-is-a-nit line now excludes names that break a written rule. +51 words

## Evidence

sealed bench round

### Anchor reasons

Anchor `agents/code-reviewer.md`, section `### Step 2: Read the Changes` (evidence: removal round, seeded round):

Read every file in scope and the project conventions file. Each added line is checked against each written rule in the conventions doc, the docs it names, and the loaded CLAUDE.md files, and a broken written rule is a fix that quotes the rule: in a seeded round with eight planted naming breaks, eight runs per arm, it raised planted breaks filed as fixes from 49 of 64 to 63 of 64 at no extra Opus tokens. The three required audits and the two guard sentences that followed them are gone: two replicates at opus found the reviewer without them equal on recall and on false findings, at about seven tenths of the tokens.

## Result

Eight runs per arm on one change with eight planted breaks of the user's naming rule. Planted breaks filed as fixes: 63 of 64 against 49 of 64; worst diff 7 of 8 against 3 of 8. The sealed bar of 16 more was missed by 2 and was out of reach once the baseline scored 49; applied on the user's call. Naming fixes on unplanted names: 1. Other fix and ask findings 16 against 11. Opus reviewer median: cache write 33k against 44k, cache read 187k against 211k, output 9.8k against 10.1k; wall 105 s against 107 s.

## Watch

user catches of naming in the work intake (9 before, 7 of them repeats).

## Back-out

restore "read it." and drop "and break no written rule"
