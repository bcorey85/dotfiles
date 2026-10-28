---
type: "Change"
title: "Fold code_step_restart into code_step_start and inline the one-line resume wrappers"
description: "code_step_restart.py's two functions move into code_step_start.py, their only caller, and the eight resume handlers that only forwarded to a command become entries in RESUME_HANDLERS. No behavior change."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T07:20:53-05:00"}
seq: 173
kind: "user-rule"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: ""
asked: "2026-10-28: lets fan out some workers - see if there are some ways to refactor / simplify code and review scripts"
proof: []
unmeasured: ""
---

## Change

- `reopens_stopped_run` and `drop_open_run` move from `code_step_restart.py` into `code_step_start.py`, the only
  module that calls them. `code_step_restart.py` is deleted and leaves `CODE_STEP_MODULES` in the test paths.
- The eight resume handlers in `code_step.py` that only forwarded to a command (`start`, `done`, `after-coder`,
  `after-review`, `after-plan-edit`, `review-again`, `ask-impact`, `ask-asks`) become lambdas in `RESUME_HANDLERS`.

## Evidence

- A survey of the code-run scripts for simplifications that keep behavior.

## Result

- Net -29 lines (32 added, 61 removed). The code-step tests pass unchanged.

## Watch

- None: no behavior change.

## Back-out

- Revert the commit.
