---
name: code
description: Dispatch a coder subagent for implementation, then auto-run `/review`. Use for "implement/build/add X" when the task is well-defined or a plan file exists; features needing design decisions go to /eng-spec first.
context: fork
agent: general-purpose
model: sonnet
allowed-tools: [Agent, Bash, Read, Skill]
---

# Code

You route nothing. `code_step.py` decides, and you run what it prints. Run every command from the repo root.

1. If the task text below starts with `asks-done`, `decide`, `verify`, `review-again` or `skill-done`, run `python3 ~/.claude/scripts/code/code_step.py <task text>`. If it starts with `tick`, run `python3 ~/.claude/scripts/code/code_step.py tick <phase>`: the user says a phase is done. If the task text is empty, or is `continue`, `resume` or `after-plan-edit`, run `python3 ~/.claude/scripts/code/code_step.py resume`: it goes on with the open run, or starts the saved plan's next phase. Otherwise run `python3 ~/.claude/scripts/code/code_step.py start <task text>`. For text with no plan file, the script takes it as the task. Run each `code_step.py` verb as its own Bash call, with no pipe, `head`, `sed` or second command: cut output loses the prompt.
2. Read the `ACTION:` line of every output and do exactly that:
   - `dispatch`: make one `Agent` call with the printed AGENT and MODEL and the text between the PROMPT markers, verbatim. The agent runs in the background: do not wait for its result and do not write text. In the next turn run the verb named in NEXT as a Bash call. That verb waits for the agent's report.
   - `wait`: no report had arrived yet. Run the command it prints, exactly as printed.
   - `rerun`: the script refused the command and changed nothing. Run the COMMAND it prints once, exactly as printed. If that is refused too, hand back.
   - `invoke-skill`: invoke that skill. Run `code_step.py skill-done pass` only when the skill reports no open finding. Otherwise run `skill-done fail`.
   - `auto-advance`: run the commit command the output names, then the next-phase command it names.
   - `stop-block-B` / `stop-block-C`: invoke Skill `stage`, then hand back.
   - `ask-user`: hand back.
   - `stop` / `judgment`: hand back.
3. Your hand-back is the contents of `<git dir>/code-step/say.md` verbatim, then the `stage` queue if you ran it, then the lines printed after a `stop` or `judgment` ACTION. Add nothing else.
4. Never write a prompt, a handoff block or a status yourself. Never edit the plan.

## Task

$ARGUMENTS
