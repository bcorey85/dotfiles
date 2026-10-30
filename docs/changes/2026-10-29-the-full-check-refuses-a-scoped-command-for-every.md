---
type: "Change"
change_type: "fixed"
title: "the full check refuses a scoped command for every caller"
description: "full_check.py's refusal of a command that names files or tests, or whose scope cannot be read, now runs inside run(), so the review-loop script and other direct callers can no longer count a scoped run as a full check."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T17:27:29-05:00"}
seq: 282
kind: "fix"
components: ["script/full-check"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_full_check.py::FullCheckTest::test_run_refuses_a_scoped_command_for_a_caller_that_does_not_go_through_main"
asked: ""
proof: []
unmeasured: ""
---

## Change

`full_check.py` refused a scoped or unresolved check command only in `main()`. Callers that import the module and call `run()` directly, such as the review-loop script, ran the command, and a pass counted as a full check. The refusal now lives in `run()`, and `main()` calls `run()`. The CLAUDE.md `Quality check:` command and a `Full suite: CI` repo keep their exceptions.

## Evidence

judgment: found by review of the change that added the scope refusal; `main()` held the only call to it.

## Result

A scoped command passed to `run()` returns `not run (scoped command: ...)` and does not run.

## Watch

None.

## Back-out

Move the `scope_refusal` call from `run()` back to `main()`.
