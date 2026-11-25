---
type: "Change"
change_type: "changed"
title: "Hillclimb queues only Claude toolkit fixes and lists project repo fixes in its report"
description: "Hillclimb defines the toolkit as dotfiles claude/.claude and agent-evals. Toolkit candidates are queued as before; a fix that lands only in the project repo the session worked in goes in a Project repo list in the report and is never queued."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-23T23:12:03-06:00"}
seq: 10
kind: "user-rule"
components: ["skill/hillclimb"]
evidence: ["user request"]
watches: []
test: ""
asked: "2026-11-23: asked by the user"
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`skills/hillclimb/SKILL.md`: the description and intro name the toolkit (`~/dotfiles/claude/.claude/`,
`~/agent-evals/`). The environment read covers toolkit hooks, gates, tests and steering files only, and the "No
guardrail in the repo" fix row is gone. The report gains a `Project repo` list for fixes that land only in the
project repo; `build_queue.py` never runs for them.

## Evidence

- user request: a hillclimb run on a personal planning repo queued three items whose fixes were all in that repo;
  the user had them removed and asked for project fixes to be listed, not queued.

## Result

Skill text changed; no test covers hillclimb output.

## Watch

None.

## Back-out

Revert the commit.

