---
type: "Change"
title: "One resume verb for every /code run that stopped"
description: "`code-step.py resume` replaces `continue`, `after-coder`, `after-review` and `after-plan-edit` as the one way to go on with a stopped /code run. `start` refuses over an open run and names `resume` or `start --restart`. Six stop routes that no run reached are cut, and the /code skill runs `resume` for empty task text."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-24T00:02:51-05:00"}
seq: 2
kind: "behavior"
components: ["script/code-step", "skill/code"]
evidence: ["tests", "judgment"]
watches: ["code-step-stop-share"]
test: ""
unmeasured: ""
---

## Change

- **`code-step.py resume`** reads the saved run and runs its next step: the coder or review hand-back, the plan-edit hand-back, the asks, a restart of the phase, or the next phase when the run is done. With no saved run, it does what a bare `start` does. It takes no arguments.
- **The old verbs stay as aliases** of `resume`: `after-coder`, `after-review` and `after-plan-edit`. Older printed commands still work.
- **`start` refuses over an open run.** It names `resume`, and with arguments also `start --restart <arguments>`. It refuses task text over a plan with open phases, and names `resume` and `start --task`. A refusal prints `ACTION: rerun` with one command, or `ACTION: stop` with a choice.
- **A verb name as the first word of task text** reruns that verb. `status` counts as a verb only when it is the only word. `start` counts only when it is alone or a flag or modifier follows it. Other text that starts with `start` or `status` is task text. Blank task text acts as a bare `start`.
- **A directory or ticket id followed by more words** stops with two choices: that plan, or `start --task` with all of the user's words.
- **Every restart text keeps the run's setup:** `start --restart` with the run's `--phase` and `+fast`/`+deep`. For a run with no plan, the text tells the main session to ask the user for the task text.
- **Cut:** the stop routes for finish-phase, moved, skill-fail, blocker, asks-gate and unknown reasons, and the reader for state files of an older shape. A stop with no route gets one ask that names `status` and `start --restart`.
- **The /code skill** runs `resume` for empty task text, `continue`, `resume` and `after-plan-edit`. It passes `skill-done` to the script unchanged. It runs the command an `ACTION: rerun` prints, once.

## Evidence

Tests: 51 resume tests cover each route and refusal. Judgment: four verbs did the same job for different stages, and the skill picked among them from the task text. One verb moves that choice into the script, which reads the saved stage.

## Result

Built in a lane bundle. The review approved it after five fix rounds. The final diff is +452/-100 lines against a design estimate of +190/-33. Most of the extra lines are review fixes to the refusal texts. This is the last verb added to code-step.py before the split: the script rules forbid a new verb, route or state field in a script over 1000 lines, and the simplify pass comes next.

## Watch

None. See `unmeasured`.

## Back-out

Restore `code-step.py`, its tests and `skills/code/SKILL.md` from the dotfiles history.
