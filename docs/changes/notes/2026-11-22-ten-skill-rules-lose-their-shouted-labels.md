---
type: "Change"
change_type: "changed"
title: "Ten skill rules lose their shouted labels"
description: "Shouted labels (HARD RULE, NON-NEGOTIABLE, MANDATORY, all-caps phrases) come out of eight skills so Opus 5.5 and Sonnet 5.5 read each rule at its real weight. Every rule stays."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T10:50:53-06:00"}
seq: 10
kind: "user-rule"
components: ["skill/coder-core", "skill/create-ticket", "skill/debug", "skill/deps", "skill/cc", "skill/adr", "skill/brainstorm", "skill/audit"]
evidence: ["user request", "prompt audit"]
watches: []
test: ""
asked: "2026-11-22: asked by the user"
proof: []
unmeasured: "Rule-meter runs pending for each reworded block: until both arms run, this edit stays uncommitted. No intake number reads how strongly a label weights a rule."
overlap: "2026-11-22-five-prompt-files-drop-shouted-labels-and-retired: same kind of change in five other files."
---

## Change

- `coder-core`: ` (HARD RULE)` drops from three headings.
- `create-ticket`: `## Brevity contract — NON-NEGOTIABLE` → `## Brevity contract`.
- `debug`: `## The Iron Law` / `NO FIX BEFORE ROOT CAUSE.` → `## Root cause before fix` / `Find the root cause before
  proposing any fix.`; "STOP and return to phase 1" → "stop and return to phase 1".
- `deps`: `MANDATORY research` → `Research`.
- `cc`: `— MANDATORY, do not skip` drops.
- `adr`: `DECISION WITH ALTERNATIVES` → lower case.
- `brainstorm`: `NOT WRONG` → `correct`.
- `audit`: `read ONLY` → `read only`.

Kept: calibrate's "STOP, loudly" and commit's "NEVER stages", which guard fragile or irreversible steps.

## Evidence

prompt audit against Opus 5.5: each of these rules already gives its reason; capitals on many rules make all read as
critical and push current models toward rigid behavior.

## Result

Pending rule-meter runs.

## Watch

None: see `unmeasured`.

## Back-out

Restore the labels from git.
