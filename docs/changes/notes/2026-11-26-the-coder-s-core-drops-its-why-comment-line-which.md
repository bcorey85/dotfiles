---
type: "Change"
change_type: "removed"
title: "The coder's core drops its why-comment line, which the comment gate now enforces"
description: "The coder-core line that asked for why-comments is deleted: the per-edit comment gate blocks those comments, and without the line the coder wrote 51 unkept comment lines in 12 runs against 62 with it."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-26T15:48:35-06:00"}
seq: 20
kind: "structured"
components: ["skill/coder-core"]
evidence: ["rule meter", "removal round"]
watches: []
test: ""
asked: ""
proof: ["2026-11-26-the-coder-s-why-comment-line-adds-unkept-comments"]
unmeasured: "No intake number reads comment kinds the coder writes; the comment gate blocks them per edit. The opencode code-reviewer keeps its why-comment lines: opencode runs no Claude hooks, so those lines are its only guard."
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

- `coder-core`, `Readability comes first`: the bullet "A comment says why the code makes a choice it cannot show.
  Never restate what the code does." comes out. The comment gate keeps only license headers, lint or tool directives,
  doc comments on public symbols and lines with a URL, so the bullet asked for comments the gate blocks.

## Evidence

Rule meter scenario CG02 (Sonnet coder, no comment gate in either arm, 4 runs per framing, 12 per arm). Added comment
lines that are no keep kind, per run:

| framing | line on | line off |
|---|---|---|
| supportive | 3, 3, 0, 2 | 2, 1, 2, 2 |
| neutral | 1, 2, 1, 4 | 1, 2, 1, 1 |
| competing | 9, 14, 12, 11 | 10, 9, 8, 12 |
| total | 62 | 51 |

Clean runs: 1 of 12 with the line, 0 of 12 without. With the line off the coder wrote no more unkept comments. CG01 shows the gate itself holds the behavior: 0 unkept
lines in 6 of 6 runs with the gate, 2 to 13 per run without it.

## Result

Every coder load is one bullet shorter, and the prompt no longer asks for comments the gate then blocks.

## Watch

None: see `unmeasured`.

## Back-out

Restore the bullet from git.
