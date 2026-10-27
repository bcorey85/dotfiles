---
type: "Change"
title: "code_step phase start carries trailing text to the coder as run notes"
description: "Text after `<plan> --phase <id>` (or `Phase <id>`) reaches the coder brief as run notes, `start --help` matches the parser, and a closing phase stops on notes it cannot pass on."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T22:50:59-05:00"}
seq: 79
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_start_input.py::StartInputTest::test_text_after_a_plan_and_a_phase_flag_reaches_the_coder_as_run_notes"
asked: ""
proof: []
unmeasured: "Run-note refusals are not logged; no intake number reads them."
---

## Change

Trailing text after a plan or ticket and its phase is added to the coder prompt under "Run notes from the user. They bind
this run; the plan stays the spec:". A closing phase stops with "takes no run notes". Help and docstring name run notes
and `--task-file`. The printed same-run restart command does not carry the notes.

## Evidence

A phase run with build limits and log rules was refused as task text while `--help` said text after the plan is task
text; the workaround cost a plan edit, a commit and a fork round trip.

## Result

Run constraints reach the coder without a plan edit; help and parser agree.

## Watch

None.

## Back-out

Revert the commit.
