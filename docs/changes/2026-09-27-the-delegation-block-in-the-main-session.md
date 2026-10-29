---
type: "Change"
change_type: "changed"
title: "The delegation block in the main-session orchestration file was trimmed from 283 to 111 words"
description: "The delegation block in the main-session orchestration file was trimmed from 283 to 111 words."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-27T00:00:00-05:00"}
seq: 2
kind: "behavior"
components: ["rule/orchestration", "skill/code", "script/review-commit-gate", "script/agent-model-guard"]
evidence: ["removal round", "judgment"]
watches: []
---

## Change

The delegation block in the main-session orchestration file was trimmed from 283 to 111 words. It keeps three rules: dispatch design work through `/code` with its direct-edit exceptions, disjoint scopes for parallel writers, and web search before slow-feedback config or CI. It drops the review-before-commit bullet and the agent-model bullet. The review-commit gate and the agent model guard enforce those two. The user chose to accept that the guard does not block fable.

## Evidence

removal round, judgment

### Anchor reasons

Anchor `orchestration.md`, section `### Delegation` (evidence: removal round, census):

259 words by `wc -w`. The bullet that stops a finished agent that still runs background work rests on judgment: a worker whose command timed out handed back its report, kept an open shell, and stayed in the agent panel as if it still worked. The bullet stops only an agent whose report names no work it waits on, because an agent with real background work resumes and reports again when that work ends. The bullet that sends a path, not a main-session read, to a subagent that will read the file rests on a work census: 47% of main-session file-read tokens were files a later subagent read again. Unproven on outcomes; the main-growth census on the next intakes shows whether the re-read share falls. Earlier text: 145 words, trimmed from 283. When the main session codes directly and when it dispatches, read-only lookups to Explore on haiku, disjoint scopes for parallel writers, and web search before config. The lookup routing is unproven on work outcomes: it rests on general-purpose Sonnet token sums, and the work census will show whether most of those runs were lookups. Without the dispatch rule, the main session edited every design change itself. With the trimmed text, it sent every one through the code skill. Without the web-search rule, it wrote CI config with no search every time, and with it, never. The review-before-commit and agent-model bullets left, because the review-commit gate and the agent model guard enforce them. The guard does not block fable. The parallel-scope rule is unproven. Main session only.

## Result

With the block removed, the main session edited all 4 design changes itself. With the trimmed text, it sent all 8 through the code skill, the same as the full text. Trivial, mechanical, CLAUDE.md and lookup requests got the same action in every version. On a CI workflow request, it wrote the file with no web search in 5 of 5 runs without the block, and in 0 of 5 with the trimmed text or the full text. The trim cuts 441 tokens from every main-session request, about 3.8M Opus cache-read tokens a week.

## Watch

—

## Back-out

restore the block from git.
