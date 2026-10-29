---
type: "Change"
change_type: "changed"
title: "The Tools and Tool Use Efficiency sections and the first three Engineering Judgment items of the global"
description: "The Tools and Tool Use Efficiency sections and the first three Engineering Judgment items of the global CLAUDE.md moved into the orchestration file, which only the main session loads."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-27T00:00:00-05:00"}
seq: 4
kind: "behavior"
components: ["rule/global-claude-md", "rule/orchestration"]
evidence: ["removal round"]
watches: []
---

## Change

The Tools and Tool Use Efficiency sections and the first three Engineering Judgment items of the global CLAUDE.md moved into the orchestration file, which only the main session loads. The naming rule stays in CLAUDE.md. The text is unchanged.

## Evidence

removal round

### Anchor reasons

Anchor `orchestration.md`, section `### Tool Use Efficiency` (evidence: removal round):

66 words, moved from CLAUDE.md. Commands: one run of an expensive command to a log, one source per fact, no spot checks of the type checker, runner or linter, chained shell calls. No hook. Without it, the coder stopped writing long output to a log file, with no rise in repeated runs. Without it and the tools and git blocks, the main session ran a full test suite twice where it ran it once with them. Main session only.

## Result

With these parts removed, the coder flagged both false plans in both versions, raised no false stop on the clean plan, and passed the same held-out tests, 25 of 28. Opus tokens per run were inside the run-to-run spread. The one change: the coder stopped writing long command output to a log file, 3 of 3 runs with the sections and 0 of 3 without, and it did not re-run expensive commands more. Subagents stop loading about 605 tokens on every request. At about 550 work subagent runs a week and 25 to 34 tool uses per run, that is about 8M to 11M cache-read tokens a week, about 55% Opus and 45% Sonnet. The main session was not tested and loads the same text as before.

## Watch

—

## Back-out

restore the sections from git.
