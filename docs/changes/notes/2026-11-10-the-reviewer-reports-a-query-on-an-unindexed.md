---
type: "Change"
change_type: "added"
title: "The reviewer reports a query on an unindexed column as a fix"
description: "The code reviewer now reports a new query that filters or sorts on a column with no index as a fix, where it used to stay silent or raise it as a question or a nit on TypeScript backends."
generated: {"by": "claude-code/claude-fable-5-2", "at": "2026-11-10T17:51:41-06:00"}
seq: 5
kind: "structured"
components: ["agent/code-reviewer"]
evidence: ["rule meter"]
watches: []
test: ""
asked: ""
proof: ["2026-11-10-a-reviewer-rule-to-flag-queries-on-unindexed"]
unmeasured: "No intake number reads it: the work logs do not tag a review finding as an index finding. Measured on a TypeScript backend and Django only; Django shows no gain because the reviewer already reports it there. No run on any other stack, on a diff with several queries, or on a small lookup table where an index would not matter."
---

## Change

`agents/code-reviewer.md`, in the step that reads the changes, gains one line: "Flag a new query that filters or
sorts on a column with no index as a fix."

## Evidence

rule meter: both arms ran with the line in the reviewer's file of a toolkit copy, on an Opus reviewer with a plain
review prompt, graded by a script that looks for the unindexed column under Fix.

## Result

Runs that reported the missing index as a fix, 8 runs per arm:

| Stack and case | With the line | Without |
|---|---|---|
| TypeScript backend, new filter on an unindexed column | 8/8 | 1/8 |
| TypeScript backend, new sort on an unindexed column | 8/8 | 0/8 |
| Django, new filter on an unindexed column | 8/8 | 8/8 |

No run in any arm flagged an index problem on a column that has an index. Without the line, the TypeScript misses
were silence, a question or a nit. `bash tests/run.sh` passes.

## Watch

None: see `unmeasured`.

## Back-out

Delete the line from `agents/code-reviewer.md` and restore the anchor row for the step that reads the changes.
