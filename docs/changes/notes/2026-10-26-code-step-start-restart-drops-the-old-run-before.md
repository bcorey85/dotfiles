---
type: "Change"
change_type: "fixed"
title: "code_step start --restart drops the old run before any check that can stop it"
description: "`start --restart` drops the old run before the gate and phase checks, so a start they stop leaves no open run for the next `start` to refuse."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T22:50:59-05:00"}
seq: 78
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_start_input.py::StartInputTest::test_a_restart_that_stops_on_a_phase_check_leaves_no_open_run"
asked: ""
proof: []
unmeasured: "Restart attempts are not logged; no intake number reads them."
---

## Change

`command_start` drops the open run right after the fresh-start preparation when `--restart` is given or the stopped run is
the same session's. A later gate or phase stop leaves no state behind. A plan-edit coder still out stops before the
drop, as before.

## Evidence

A `start --restart` stopped on a gated phase and kept a two-day-old stopped run open, so the next /code was refused
again and a third dispatch was needed.

## Result

A restart that stops on a check leaves nothing open.

## Watch

None.

## Back-out

Revert the commit.
