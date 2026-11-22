---
name: toolkit-writing
description: Checks for writing or judging toolkit text an agent reads. Use when creating or editing a skill, agent, rules file, AGENTS.md or CLAUDE.md.
---

# Toolkit writing

Every line in a skill, agent, rules file or CLAUDE.md is read on each load. A line ships only when it changes what the agent does.

## Terms

- **No-op**: a line the agent would follow without it, or that changes nothing it does.
- **Duplicate**: a rule stated twice, in one file or across files. Keep one owner; point to it from the rest.
- **Cache**: a copy of a fact the agent can read from its source before it acts (a file list, a flag table, a version). Point to the source instead. A fact the agent learns only after the wrong move, such as a hook's approved path, is not a cache.
- **Sprawl**: one topic split across files that each load alone. Co-locate it with the step that uses it.
- **Weak pointer**: a reference that does not say when to follow it ("see X"). Name the trigger: "Before you push, read X."
- **Sediment**: a line kept for an incident, a date, a measurement or a retired feature. It belongs in the commit message or `~/agent-evals/`.
- **Dense rule**: one paragraph or sentence that holds more than one branch, or more than three conditions. Split it into a list, one branch per item.

## Checks

1. **Description is the trigger.** Only the description is always loaded. It names what the skill does and the words or situations that call it. A skill with `context: fork` keeps in its description every instruction the main session needs, since the main session never reads the body.
2. **User-invoked or model-invoked.** Before you set `disable-model-invocation: true`, `rg` the toolkit for callers: an agent's `skills:` preload, another skill that loads it. Set it only when the user is the sole caller.
3. **Done when.** Every step or phase ends with a check the agent can run or observe.
4. **Lead with the action.** Write "do X". Use "never Y", caps or bold only on a line where the wrong move is the likely one, at most a few per file.
5. **Order by use.** The step the agent takes first comes first. Reference that only one branch reaches moves into that branch, or into a sibling file the branch reads on a named trigger.
6. **Prune.** Cut each no-op, duplicate, cache and sediment line. Fix each weak pointer, sprawl and dense rule.

## Cutting a rule

A no-op or duplicate flag on an existing rule is a candidate. Test it with `~/agent-evals/bin/rule_meter.py` before you cut it. A new or reworded rule follows the agent-evals rule workflow.

Done when every line of the changed text passes the six checks, or carries a rule-meter candidate note in your report.
