---
type: "Change"
change_type: "changed"
title: "wait_loop_gate denies background jobs from code-fork"
description: "The wait-loop gate now denies a background Bash job from the code-fork agent, as it does for review-loop, and names the foreground form with a timeout up to 600000 ms, so a fork no longer ends its turn mid-phase waiting on its own job."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-24T04:37:32-06:00"}
seq: 1
kind: "fix"
components: ["script/wait-loop-gate", "agent/code-fork"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_wait_loop_gate.py::WaitLoopGateTest::test_code_fork_background_call_denied_with_the_foreground_form"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

Shape 5 of `gates/wait_loop_gate.py` keys its background-job denial on a table, `BACKGROUND_REASONS`, from agent_type
to deny reason. `review-loop` keeps its reason. `code-fork` gets a reason that says a background job ends the fork's
turn and hands back before the phase ends, and gives the approved path: run in the foreground with a Bash timeout up
to 600000 ms, and split a longer job into steps that each fit. The jobs covered are unchanged: `run_in_background`,
a lone `&`, nohup, setsid, detach and disown. The main session, coder and every other agent type stay exempt.
The `code-fork` key is `FORK_AGENT_TYPE`, moved from `lib/script_utils.py` into a new no-import module,
`lib/agent_names.py`; `script_utils` re-exports it. Importing it from `script_utils` cost the gate 10 to 13 ms.
`claude/.claude/scripts/CLAUDE.md` gains the owner line for `lib/agent_names.py`.

## Evidence

Two queue items from one /code run: the code-fork started its own timing script in the background, ended its turn,
and the harness took an interim hand-back. The caller resumed it by hand twice, and a later blocking report was
refused (one report per result), so the blocker reached the caller only through the transcript.

## Result

Tests: `test_code_fork_background_call_denied_with_the_foreground_form` and `test_code_fork_shell_background_denied`
fail on the old gate and pass now; `test_background_commands_pass_for_a_coder_and_the_main_session` and the existing
review-loop tests pass on both. Full suite: 6253 tests, 0 failed. Lint clean.

Gate median wall time on a matched call (code-fork, `run_in_background: true`), 40 runs each, before and after in
the same run: 34.0 vs 33.0 ms (bare Python start 10.4 ms), and 36.2 vs 36.5 ms (bare 12.8 ms). No added cost.

## Watch

None: no intake number counts interim code-fork hand-backs. Read the next /code runs for a fork that hands back
mid-phase, and for a coder or other agent denied by this shape.

## Back-out

Remove the `code-fork` row from `BACKGROUND_REASONS` in `gates/wait_loop_gate.py`.
