---
type: "Change"
change_type: "added"
title: "orchestration names the Agent model values the hook passes"
description: "The Delegation section tells the main session to leave model out when the agent's file pins one, else set sonnet or haiku, and says the model guard denies opus and inherit at the call site."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-22T19:20:31-06:00"}
seq: 36
kind: "structured"
components: ["rule/orchestration"]
evidence: ["rule meter"]
watches: []
test: ""
asked: ""
proof: ["2026-11-22-the-agent-model-line-sends-no-opus-or-inherit-pin"]
unmeasured: "No intake number counts Agent calls by call-site model value."
---

## Change

One new bullet under `### Delegation` in `orchestration.md`, after the Explore line: on an Agent call leave `model` out when the agent's file pins one (every file under `agents/` does), else set `sonnet` or `haiku`; the hook denies `opus` and `inherit` at the call site, so opus runs only from an agent file's frontmatter; a `fork` call skips the hook and runs on the parent model.

## Evidence

Rule meter scenario AM01 on an Opus main session, one general-purpose dispatch per run, graded on every Agent call's `input.model`. A walk of `agent-model-guard.sh` over a general-purpose call with `model` `sonnet`, `haiku`, absent, `opus` and `inherit` passed the first three and denied the last two. AM01 metered the line before the fork clause was added (W5); AM02 metered it with the clause.

## Result

Per cell, VIOLATED / COMPLIED / NO_TEST, on arm then off arm: supportive 0/1/0 and 0/1/0; neutral 0/8/0 and 0/8/0; competing 0/1/0 and 0/1/0. No AM01 run pinned opus or inherit in either arm, so the line shows no measured effect on this task; it records what the guard enforces.

## Watch

None.

## Back-out

Delete the bullet from `orchestration.md` and its rehashed row in `docs/rule-anchors.md`.
