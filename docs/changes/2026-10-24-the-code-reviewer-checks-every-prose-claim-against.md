---
type: "Change"
title: "The code reviewer checks every prose claim against the code"
description: "The code reviewer gains a prose-claims lens. Every comment, docstring, doc, ADR and run-time description that the diff adds, or that names something the diff changes, must hold for the code after the diff. A false or stale claim is a fix, never a smell or a nit."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-24T15:43:25-05:00"}
seq: 12
kind: "behavior"
components: ["agent/code-reviewer"]
evidence: ["census"]
watches: []
test: ""
unmeasured: "Until this date the escape skills never offered the docs class, so the logged class has no before period for false or stale prose. From this date they file it as docs. Read it once about 40 new review escapes have landed: the docs share of review escapes against the census share of 13 percent."
---

## Change

- `agents/code-reviewer.md`, opening line: the lens list names prose claims (Step 2).
- `agents/code-reviewer.md`, Step 2, new paragraph after the written-rule check. It checks the prose the diff adds, and prose that names a symbol, rule or file whose behavior the diff changes, renames or removes. Each claim must hold for the code after the diff: behavior, return value, applied rule or filter, link and line citations, and agreement with sibling docs. A false, stale or contradicting claim is a `fix` that names what it contradicts.

## Evidence

Census of the review-gate escapes in the work logs. Of 355 escapes past the code review, 101 fit no lens the reviewer's prompt names. A blind second labeler found 109, and both labelers put 90 of the same escapes in that group. The largest group is prose that is false or stale: 46 escapes, 13 percent of all review escapes. The second labeler also put 45 of those 46 under no lens. The escape log filed 36 of the 46 as `other` or `smell`. An outside PR bot caught 20 of them, and the user caught 14.

## Result

Pending. Predicted: the reviewer catches about half of the class, so review escapes fall about 6 percent, and the PR bot's catches of prose claims fall by about half.

## Watch

None. See `unmeasured`. The escape skills' `docs` class is its own change file of the same date; it makes the share readable.

## Back-out

Remove the Step 2 paragraph and the `prose claims (Step 2)` words from the opening line of `agents/code-reviewer.md`.
