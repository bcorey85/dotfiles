---
type: "Change"
change_type: "fixed"
title: "code_wait prints the next step for a fix-removed-change stop"
description: "When the /code review loop ends with fix-removed-change, code_wait.py review prints a STOP line naming stop.md and the resume command, and exits 1."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-12T16:26:52-06:00"}
seq: 7
kind: "fix"
components: ["script/code-wait", "skill/code"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_wait.py::WaitReviewTest::test_a_fix_removed_change_packet_prints_the_stop_step_and_exits_one"
asked: ""
proof: []
unmeasured: ""
---

## Change

`code/code_wait.py`: `phase_stop_line` reads the loop's packet through `handback.parse`. On `fix-removed-change` the
ended-loop output ends with a STOP line: write the packet's blockers to `<run folder>/stop.md`, and `/code resume
<plan path>` runs the phase's review again. The call exits 1, which the /code skill already routes to "do the step its
last line names".

## Evidence

judgment: /code had no route for the `fix-removed-change` stop, so the session worked out the recovery by hand.

## Result

The new test fails on the old tree and passes; `test_code_wait.py` passes (38 tests).

## Watch

None: a fixed stop line.

## Back-out

Revert the commit.
