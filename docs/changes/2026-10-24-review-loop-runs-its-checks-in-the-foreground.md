---
type: "Change"
change_type: "changed"
title: "Review-loop runs its checks in the foreground"
description: "The wait-loop hook now refuses every background job review-loop starts: run_in_background, a lone &, nohup, setsid and disown. The refusal tells it to run the same command in the foreground with a Bash timeout up to 600000 ms."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-24T16:25:18-05:00"}
seq: 15
kind: "behavior"
components: ["agent/review-loop"]
evidence: ["census", "judgment"]
watches: ["review-loop-foreground-checks"]
test: ""
unmeasured: ""
---

## Change

`claude/.claude/scripts/gates/wait_loop_gate.py` gets a fifth shape. When the PreToolUse payload's `agent_type` is `review-loop` and the Bash call starts a background job, the hook denies it. A background job is `run_in_background: true`, a lone `&` outside quotes and heredocs (`&&`, `|&`, `2>&1` and `&>` are not one), or a statement that starts with `nohup`, `setsid` or `disown`. Every other agent and the main session keep background jobs.

A hook, not a prompt line: the agent cannot skip it, and the refusal names the foreground form to use.

## Evidence

Work-log census: review-loop started 282 `run_in_background` Bash calls and about 20 shell-backgrounded ones on 16 work days from 2026-09-22 to 2026-10-22. One run spent 27 of its 39 minutes waiting on 5 background jobs whose results never came back. On this machine's 2425 distinct Bash commands, the detached-job check fires on 21, and all 21 are real background jobs.

Test: `tests/scripts/test_wait_loop_gate.py::WaitLoopGateTest::test_review_loop_background_call_denied` fails on the old gate and passes on the new one. Full suite 1991 tests, 0 failed. Ruff is not installed on this machine, so lint did not run.

## Result

Pending the watch.

## Watch

`review-loop-foreground-checks`: review-loop (sonnet) wall-clock seconds per dispatch, good direction down. The quality guard is the same day's review-findings-per-run guard on the coder make refusal. The two cannot be separated on that metric, so no second guard was added.

## Back-out

Revert the fifth shape in `wait_loop_gate.py`: the `starts_detached_job` function, the `BACKGROUND_*` constants and the branch in `main`.
