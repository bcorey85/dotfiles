---
type: "Change"
change_type: "fixed"
title: "code-step: start over a closable run offers verify first"
description: "start over an open run that verify may close now names verify first, and a bare start reruns verify. Before, the refusal offered only resume, status or restart."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T13:51:07-05:00"}
seq: 186
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_start_input.py::StartInputTest::test_start_over_a_run_that_verify_may_close_offers_verify_first"
asked: ""
proof: []
unmeasured: ""
---

## Change

- When `verify` may run on the open run, the `start` refusal says to run `verify` first and lists its command before
  the others. With no arguments, `start` prints `verify` as the one rerun command.

## Evidence

- A run stopped on verification while its checks already passed. The next phase's `start` was refused and named no
  way to close the old run.

## Result

- The next `start` leads to `verify`, which closes the old run.

## Watch

—

## Back-out

Revert the commit.
