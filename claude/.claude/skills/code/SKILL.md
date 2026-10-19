---
name: code
description: Dispatch a coder subagent for implementation, then auto-run `/review`. Use for "implement/build/add X" when the task is well-defined or a plan file exists; features needing design decisions go to /eng-spec first.
context: fork
agent: general-purpose
model: sonnet
allowed-tools: [Agent, Bash, Read, Skill]
---

# Code

You route nothing. `code-step.py` decides, and you run what it prints. Run every command from the repo root.

1. If the task text below starts with `asks-done`, `decide` or `verify`, run `python3 ~/.claude/scripts/code-step.py <task text>`. Otherwise run `python3 ~/.claude/scripts/code-step.py start <task text>`. For text with no plan file, the script takes it as the task.
2. Read the `ACTION:` line of every output and do exactly that:
   - `dispatch`: make one `Agent` call with the printed AGENT and MODEL and the text between the PROMPT markers, verbatim. Wait for its result. Then run the verb named in NEXT.
   - `invoke-skill`: invoke that skill, then run `code-step.py skill-done pass` or `skill-done fail`.
   - `auto-advance`: run the `review-gate-mark clean` command, then `code-step.py start`.
   - `stop-block-B` / `stop-block-C`: run the printed mark-clean command, invoke Skill `stage`, then hand back.
   - `ask-user` / `present-asks-and-wait`: hand back with a `QUESTION` section. Start it with the line `Main session: ask the user this question with these options in plain text, then invoke Skill code with the RESUME args and the user's answer.` Copy the question and its options verbatim. End it with the line `RESUME: <verb> <answer>`, using the verb the script names.
   - `stop` / `judgment`: hand back.
3. After a `converged` or `deferred` packet the script prints a `review-gate-mark clean` line. Run it as its own Bash command, exactly as printed.
4. Your hand-back is the contents of `<git dir>/code-step/say.md` verbatim, then the `stage` queue if you ran it, then the `QUESTION` section if there is one. Add nothing else.
5. Never write a prompt, a handoff block or a status yourself. Never edit the plan.

## Task

$ARGUMENTS
