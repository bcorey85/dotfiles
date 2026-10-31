---
type: "Change"
change_type: "removed"
title: "/code runs as plain prompt steps with no code-step script"
description: "Running /code as plain prompt steps in its Sonnet fork cuts cost 15% ($7.86 → $6.66 a run, mean) with 13 of 13 checks passing in all 16 bench runs. The code-step script and its state, hooks and tests are removed; small standalone scripts keep the plan check, the concentration gate, the coder-report parse, the review start and the waits."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-31T15:13:42-05:00"}
seq: 1
kind: "structured"
components: ["skill/code", "script/code-step", "agent/code-fork", "skill/eng-spec", "agent/spec-criteria", "script/review-loop-script", "script/handback"]
evidence: ["removal bench", "tests"]
watches: ["code-plain-steps-review-escapes", "code-plain-steps-main-cache-read"]
test: "tests/scripts/test_code_review_start.py"
asked: ""
proof: ["2026-10-31-code-skill-without-the-code-step-script-8-runs-per"]
impact: {"metric": "cost", "before": 7.86, "after": 6.66, "unit": "$", "finding": "2026-10-31-code-skill-without-the-code-step-script-8-runs-per"}
unmeasured: ""
overlap: "The plan-impact rule rides in the same skill text: a plan impact never stops a phase mid-run. One with no criterion change is adopted as a Plan Deviations line; one that changes a criterion waits, unapplied, for sign-off at the phase end. The user ruled it on 2026-10-31. The review loop's own plan-impact routing changes in a separate lane, so the escapes watch reads both."
---

## Change

`/code` runs its steps as plain prompt text in the `code-fork` Sonnet fork. The fork dispatches the coder, waits with `code_wait.py agent <id>`, starts the review with `code_review_start.py <lane> <plan> <N> <handoff> --base <phase base> --detach`, and waits on it with `code_wait.py review`. Run files (`stop.md`, `review.out`, the pid) live in the git-path `code-phase` folder, so worktrees work.

Removed: every `code_step*.py` module, `code_guidance.py`, their 15 test files, the keyed coder gate, the herdr `--headless` insert and `--watched` flag, and the saved-packet refusal for a packet a /code run owned.

Kept as small scripts under `scripts/code/`:

- `plan_check.py` (eng-spec and spec-criteria call it in place of `code_step.py plan check`).
- `plan_verification.py`.
- `concentration.py` (the Refactor pass gate).
- `coder_report.py` (the review packet reads coder reports through it).
- `gate_commands.py`: derives the scoped lint and test commands from the plan phase. `code_review_start.py` adds the stale-prose check from `--base` and passes each one to the review loop as `--gate-command`.

Plan impacts never stop a phase mid-run. They collect on a phase-end list. One with no criterion change becomes a `## Plan Deviations` line, written by a coder, with no question. One that changes a criterion stays unapplied and shows under "Plan changes awaiting sign-off", and the phase ends on a stop.

Closing phases invoke their named skill, and a coder writes the evidence lines.

## Evidence

The removal bench ran 8 slots on one structured phase, each with one run per arm, live script against plain steps. Plain steps cut mean list cost 15% ($7.86 → $6.66) and Opus cost 24% ($5.73 → $4.35). All 16 runs passed 13 of 13 checks and finished the phase. Median review rounds went 3 → 2. Every gap sits inside the run-to-run spread. The script missed the user's bar of a 30% win, so it goes.

## Result

The touched test files pass: `test_code_review_start`, `test_gate_commands`, `test_code_wait`, `test_plan_check`, `test_plan_verification`, `test_concentration`, `test_coder_report`, `test_review_loop_script` and `test_handback`. Lint is clean on the touched files.

## Watch

- `code-plain-steps-review-escapes`: review escapes per review run, flat.
- `code-plain-steps-main-cache-read`: main-session cache-read tokens per `/code` turn, flat.

## Back-out

Revert the branch's merge commit. That restores `code_step*.py`, its tests, the settings.json hooks, the keyed coder gate and the herdr `--headless` insert together.
