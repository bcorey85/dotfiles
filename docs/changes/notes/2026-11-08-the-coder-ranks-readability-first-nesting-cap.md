---
type: "Change"
change_type: "added"
title: "The coder ranks readability first: nesting cap, function size, plain code, why-only comments"
description: "coder-core gains a hard rule that ranks readability above everything but correctness and the acceptance criteria, with four checkable limits: control flow nested at most two levels, one job and at most 40 lines per function, no chained ternaries or packed one-liners, and comments that say why."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-08T18:56:10-06:00"}
seq: 8
kind: "user-rule"
components: ["skill/coder-core", "agent/coder"]
evidence: ["user rule", "work finding census"]
watches: ["coder-readability-first-findings", "coder-readability-first-coder-cost"]
test: ""
asked: "2026-11-08: how do i tune my coder rules so that readability and human maintainability are king / #1 priority bar none ... go hard and solve this"
proof: []
unmeasured: ""
overlap: "coder-updates-stale-docs, coder-guard-make-review-findings, stale-prose-handback-docs-findings, stale-prose-handback-severe-findings, prose-claims-docs-findings: all read review findings per review run, but only coder-readability-first-findings reads the smell, duplication, complexity and naming classes, so a move in those classes is read against this edit. test-sibling-whole-suite-coder-cache-read, stale-prose-handback-coder-cache-read: same coder cache-read metric; a rise is read against all three edits."
---

## Change

`skills/coder-core/SKILL.md` gets `## Readability comes first (HARD RULE)` right after the role line. Readability ranks above brevity, cleverness, line count, speed of writing and a terse style in the brief or the code around it; only correctness and the acceptance criteria rank above it. Four limits follow: nest control flow at most two levels and return early on guards; one job per function and split past 40 lines; one step per statement with no chained ternary or packed one-liner; comments say why, never what.

Naming and code-paragraph rules are not repeated here: on-off meters showed Sonnet already at ceiling on both.

## Evidence

User rule. Work census, `review-findings.jsonl`, code lane, dotfiles and agent-evals excluded: 704 smell, duplication, complexity and naming findings, 444 of them dispositioned `fix`; 281 of 1,449 code-lane findings in November so far (19%). Each one is a reviewer catching after the coder what the coder could have written readably first.

## Result

Pending. Two rule-meter scenarios meter the section and the nesting bullet on the coder, rule on against rule off under a competing prompt.

## Watch

`coder-readability-first-findings`: smell, duplication, complexity and naming findings per review run, good direction down. `coder-readability-first-coder-cost`: Sonnet coder cache read per dispatch, good direction flat.

## Back-out

Delete the section from `skills/coder-core/SKILL.md` and its anchor row.
