---
type: "Change"
change_type: "added"
title: "The coder validates handler input, keeps caught errors, uses the repo error type, sorts lists and writes the failing test first"
description: "Five one-line rules reach the coder: two in its core skill (never drop a caught error; for a bug fix, no source edit until a new test has run and failed) and three in a new path-scoped rules/backend.md (validate handler fields, repo error type, explicit sort)."
generated: {"by": "claude-code/claude-fable-5-2", "at": "2026-11-10T08:49:55-06:00"}
seq: 2
kind: "structured"
components: ["skill/coder-core", "rule/backend"]
evidence: ["rule meter"]
watches: []
test: ""
asked: ""
proof: ["2026-11-10-four-short-coder-rules-hold-on-the-real-coder-file"]
unmeasured: "No intake number reads these behaviors: work escape descriptions are hashed, so no class count maps to a rule. Stacks with no run: Vue (all rules); React for the three backend rules; Django and React for the new test-first wording (the old wording ran there); Django with the three backend rules in the path-scoped file has no same-batch arm without the file. The live globs (`**/*.py`, `**/backend/**`, `**/server/**`, `**/api/**`) are a judgment; the run used `backend/src/**/*.ts`."
---

## Change

`skills/coder-core/SKILL.md` gains two lines. In the readability list: never write a catch block that drops the
error. In "Tests are yours": for a bug fix, do not edit the source file until a new test has run and failed.

New `rules/backend.md`, loaded when a session reads a Python file or a file under a `backend`, `server` or `api`
folder: validate every field a new request handler reads and reject a bad one with a 400 that names the field; throw
the repo's own error type with its error code; sort every list a new endpoint or query returns by an explicit key.
The three sit in a path-scoped file because they fit backend code only.

## Evidence

rule meter: each rule against the same toolkit copy without it, Sonnet coder, plain task prompt, 8 runs per arm,
graded by a script that reads the final code or the order of tool calls.

## Result

With the rule vs without, runs that complied out of 8:

| Rule | TypeScript backend, coder file | Django, coder file | React, coder file | TypeScript backend, path-scoped file |
|---|---|---|---|---|
| Validate handler fields | 8 vs 4 | 8 vs 0 | no run | 8 vs 0 |
| Repo error type | 8 vs 0 | 8 vs 3 | no run | 8 vs 1 |
| Explicit sort | 8 vs 0 | 8 vs 0 | no run | 8 vs 0 |
| Never drop a caught error | 8 vs 0 | 8 vs 0 | 2 vs 0 | not placed there |
| Test first, shipped wording | 7 vs 0 | no run | no run | not placed there |
| Test first, earlier wording | 3 vs 0 | 6 vs 0 | 4 vs 0 | not placed there |

Django with the shipped `rules/backend.md` loaded from the user rules folder and the rules absent from the coder
file, 8 runs per rule, against the earlier Django runs with no rule: validate handler fields 8 vs 0, explicit sort
8 vs 0, repo error type 6 vs 3. The meter could not run a clean arm without the file once it was live, so the
comparison is across two batches.

A user-level path-scoped rule file reached a dispatched coder in 3 of 3 runs when the coder read a matching file, and
in 0 of 3 when it read none.

## Watch

None: see `unmeasured`.

## Back-out

Delete `rules/backend.md` and its two anchor rows, and remove the two added lines from `skills/coder-core/SKILL.md`.
