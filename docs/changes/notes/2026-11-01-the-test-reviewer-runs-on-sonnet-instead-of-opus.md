---
type: "Change"
change_type: "changed"
title: "The test-reviewer runs on Sonnet instead of Opus"
description: "The test-reviewer agent now runs on Sonnet. On the bench this cut its list cost 79% per review ($1.74 → $0.37 median) and its wall time 63% (198 s → 73 s), while it caught a median 9 of 11 seeded test-suite gaps against Opus's 10 of 11, inside the one-gap bar set before the runs."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-01T04:32:19-06:00"}
seq: 428
kind: "structured"
components: ["agent/test-reviewer"]
evidence: ["bench"]
watches: ["test-reviewer-sonnet-findings", "test-reviewer-sonnet-cache-read"]
test: ""
asked: ""
proof: ["2026-11-01-running-the-test-reviewer-on-sonnet-cuts-its-cost"]
unmeasured: ""
overlap: "The open cost guard on test-reviewer cache-read tokens per dispatch for the whole-suite sibling search (2026-10-23) reads the same agent and metric; this edit moves it by construction, so that watch's reading after 2026-11-01 cannot be told apart from this one."
---

## Change

`agents/test-reviewer.md` frontmatter: `model: opus` → `model: sonnet`. The prompt is unchanged. Every caller
(/test-review, /refactor, review-loop) omits `model`, so the frontmatter decides.

## Evidence

Bench, 8 runs per arm, blind-graded: the test-reviewer reviewed three phases of a TypeScript billing web app, each
phase diff on its own tree as review-loop dispatches it, with 11 seeded test-suite gaps (deleted cases and weakened
assertions; suite, typecheck and lint green). The plan's per-case test checklists were removed so the gaps could not be
found by reading the plan.

Work: `agent-tokens.txt` week 202644 shows the test-reviewer on Opus at 57 dispatches and 43.0M cache-read tokens.

## Result

- Seeded gaps caught: Opus 10 in every run → Sonnet median 9, range 8 to 10. 80 of 88 vs 74 of 88.
- Sonnet's losses sit in two gaps: a fixture built in creation order that hides an oldest-first bug (8 of 8 → 4 of 8)
  and a length-only assertion on a reversal (8 of 8 → 6 of 8). Every other gap: same count in both.
- Per review run, median: list $1.74 → $0.37; wall 198 s → 73 s. Opus tokens: fresh 46, cache write 155k, cache read
  665k, output 16.4k → none. Sonnet tokens: fresh 26, cache write 71k, cache read 176k, output 7.3k.

This trades about 0.75 seeded gaps per three-phase review for the cost cut.

## Watch

`test-reviewer-sonnet-findings` (findings per test-reviewer run, flat): a drop means Sonnet checks less at work.
`test-reviewer-sonnet-cache-read` (cache-read tokens per dispatch, down).

## Back-out

Set `model: opus` again in `agents/test-reviewer.md`.
