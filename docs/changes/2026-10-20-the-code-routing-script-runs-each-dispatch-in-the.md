---
type: "Change"
title: "The /code routing script runs each dispatch in the background and keeps the run in one session"
description: "code-step.py prints a background dispatch and the next verb waits for the agent's report. Hooks store the hand-backs, keep the fork alive while a dispatch is open and print say.md as the closing text. The run pins to one session."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-20T23:26:15-05:00"}
seq: 19
components: ["script/code-step", "skill/code"]
evidence: ["tests", "judgment"]
watches: []
---

## Change

`scripts/code-step.py` and `skills/code/SKILL.md`:

- A `dispatch` ACTION runs the agent in the background. The fork writes no text and runs the verb in `NEXT` in its next turn. That verb waits for the agent's hand-back (about 570 seconds per wait, at most three waits).
- New ACTION `wait`: no report had arrived. The fork runs the command it prints, exactly as printed.
- New verb `review-again`: dispatches the review loop again on the same diff after its packet did not parse.
- New verb `tick <phase>`: marks a phase done that the user finished outside /code. The skill routes `tick`, `review-again`, `asks-done`, `decide` and `verify` to the script.
- `after-coder` waits for the coder's hand-back and builds the review dispatch. `after-plan-edit` builds the review dispatch after a coder rewrites the plan to an adopted change. `skill-done pass|fail` marks a closing phase done or stops.
- The script now prints the commit command on `auto-advance` and the gate command on `ask-user`. The skill no longer tells the fork to run a gate mark, so steps 3 to 5 of the old skill collapse into one hand-back rule.
- One coder runs per phase. The old two parallel coders for deliverables that share no file are dropped.
- Review-loop packets are read through `handback.py`, not a second parser inside `code-step.py`.
- `start` pins the run to the `CLAUDE_CODE_SESSION_ID` of the Bash call that ran it. A state with no pin claims no hand-backs. A second session that runs `start` in the same checkout while the first session's dispatch, or its wait at asks or a plan-impact ruling, is under two hours old is stopped. `start --take-over` overrides that.

Hooks in `settings.json`, each `python3 ~/.claude/scripts/code-step.py <verb>`:

- PreToolUse `SubagentHandback`, `hook`: stores each coder and review-loop hand-back in `<git dir>/code-step/reports.jsonl`. It denies the fork's own hand-back while a dispatched agent has not handed back.
- SubagentStop, `stop-hook`: blocks the fork from stopping while a dispatch is open, at most two blocks per dispatch.
- Stop, `say-hook`: prints `<git dir>/code-step/say.md` as the turn's closing text.
- PostToolUse `Edit|Write`, `plan-hook`: covered by the plan-grammar change.

## Evidence

Tests: in the full suite run after the install, `test_code_step.py`, `test_code_step_termination.py`, `test_script_utils.py` and `test_plan_format.py` passed against the installed paths. They cover the hooks, the session pin, the wait and the fork stop. `test_fixes.py` failed on the half-applied `decide --by` change, which a later install replaces.

Judgment: a foreground wait in the fork held a model turn open for the whole coder run. A background dispatch with a waiting verb lets the script own the wait. The pin stops a second session from taking another session's hand-backs.

## Result

Installed 2026-10-20 with the `hook`, `stop-hook` and `say-hook` settings entries. No work-log reading yet.

## Watch

None. The two /code watches measure the earlier fork and say.md changes, and no watch measures the background dispatch. A wrong wait or pin shows as a stuck run, not as a metric.

## Back-out

Reinstall the previous `code-step.py` and `skills/code/SKILL.md` from the dotfiles history and remove the `hook`, `stop-hook` and `say-hook` settings entries.
