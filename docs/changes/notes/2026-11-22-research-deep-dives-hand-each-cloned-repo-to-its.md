---
type: "Change"
change_type: "added"
title: "Research deep dives hand each cloned repo to its own subagent"
description: "A research deep dive into several cloned repos now starts one subagent per repo and compares their reports, which cuts the main session's cached reads 44% to 78% so a long dive stops compacting mid-task; the whole run spends 2.6 to 3.1 times the tokens on small repos."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T20:58:49-06:00"}
seq: 37
kind: "structured"
components: ["skill/research"]
evidence: ["rule meter", "two fixtures"]
watches: []
test: ""
asked: ""
proof: ["2026-11-22-research-deep-dives-hand-each-repo-to-its-own"]
unmeasured: "No intake number reads it: research sessions run on this machine, and the work logs carry no main-session context size per skill call. Haiku subagents: the bench loads no session-start file, so its Explore subagents ran on Opus; live sessions send read-only lookups to Haiku. Real cloned repos larger than the synthetic plants: the main-session saving grows with repo size, the subagent cost grows with it too."
impact: {"metric": "tokens", "before": 142771, "after": 31053, "unit": "tokens", "finding": "2026-11-22-research-deep-dives-hand-each-repo-to-its-own"}
---

## Change

`skills/research/SKILL.md`, Phase 3: one new line. For a deep dive into several cloned repos, start one subagent
per repo that returns each mechanism with its file path, then compare them in the main session; never read every
repo's files in the main session.

The queue item also asked the skill to name `build_queue.py prior` and the work-log counts. Those are agent-evals
steps, already in that repo's CLAUDE.md, and the research skill runs in every repo, so the line leaves them out
(ruled by the agent-evals session, 2026-11-22).

## Evidence

Rule-meter, line on against line off, Opus, 8 runs per arm on each of two plants and two prompts: three synthetic
agent toolkits, and four synthetic TypeScript web apps.

## Result

| Plant | Prompt | On | Off |
| --- | --- | --- | --- |
| three toolkits | plain | 8/8 | 0/8 |
| three toolkits | "they are small, so be quick" | 8/8 | 0/8 |
| four web apps | plain | 8/8 | 0/8 |
| four web apps | "they are small, so be quick" | 8/8 | 0/8 |

Main session, plain prompt, median cache read: 142,771 → 31,053 (three toolkits), 86,558 → 48,112 (four web apps).
Output 2,243 → 1,399 and 1,796 → 1,130. Whole run cost, subagents included: $0.219 → $0.565 and $0.182 → $0.570,
all on Opus.

## Watch

None; see `unmeasured`.

## Back-out

Delete the line from Phase 3 of `skills/research/SKILL.md`.
