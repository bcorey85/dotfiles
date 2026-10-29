---
type: "Change"
change_type: "fixed"
title: "herdr-phase-change sends the next phase's prompt only after /clear takes effect"
description: "A new herdr-phase-change script sends /clear, waits for herdr to report a new session id for the pane, and only then sends the prompt. If the id does not change in time it sends nothing more and exits 1. The orchestration rules name the script for every phase change. Before, an orchestrator sent a worker /clear and then /code as two herdr agent prompt calls with a wait between them. The worker was already done, so the wait returned at once, and the pane got one input, /clear/code ..., which ran on the full eng-spec context."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T04:20:34-05:00"}
seq: 172
kind: "fix"
components: ["script/herdr-phase-change", "rule/orchestration"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_herdr_phase_change.py::HerdrPhaseChangeTest::test_a_clear_that_never_takes_effect_stops_before_the_prompt"
asked: ""
proof: []
unmeasured: ""
---

## Change

- New `scripts/.local/bin/herdr-phase-change [--timeout <seconds>] <agent> <prompt>`:
  - It sends nothing unless the agent is `idle` or `done` and reports a session id.
  - It sends `/clear`, then polls `herdr agent get` until the pane's session id changes. Claude's SessionStart hook reports the new id once `/clear` has run.
  - It then waits for the pane to settle and sends the prompt.
  - If the id has not changed by the timeout (30 s by default), it sends nothing more and exits 1 with a message to read the pane first.
- `orchestration.md`: to move a herdr worker to its next phase, run `herdr-phase-change`. Never send `/clear` and the prompt as two `herdr agent prompt` calls.
- Closes the queue item orchestrator-phase-change-can-merge-clear-and-code.

## Evidence

- In one orchestrated run, `herdr agent wait --until done` returned at once on a pane that was already done. Both prompts reported success, but the pane showed one input, `/clear/code docs/plans/...`. It ran as a plain message with 144k tokens of eng-spec context, 1% short of auto-compact.
- The stop test fails before the change: with no barrier, the prompt goes out even though `/clear` never took effect.

## Result

- The five herdr-phase-change tests pass against a stub pane in `done` state. `/clear` and the prompt land as two separate submissions, and the prompt goes out only after the session id changes. shellcheck and ruff are clean.

## Watch

—

## Back-out

Revert the commit. Orchestrators send `/clear` and the prompt as two `herdr agent prompt` calls again, and a done pane can merge them into one input.
