---
type: "Change"
title: "matches_no_test leaves a runner piped into another command unjudged"
description: "A test runner whose output feeds a later pipe stage (`cargo test <filter> 2>&1 | rg -q ...`) is no longer judged as matching no test; the last stage owns the output and the exit code."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T22:43:01-05:00"}
seq: 74
kind: "fix"
components: ["script/code-step", "script/test-run-output"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_test_run_output.py::MatchesNoTestTest::test_a_runner_piped_into_another_command_is_not_judged"
asked: ""
proof: []
unmeasured: "A verify box that fails on this shape is not logged by shape; no intake number reads it."
---

## Change

`matches_no_test` drops every pipeline stage that feeds a later pipe before it looks for a filtered runner, through the
shared shell pipe parser. A runner after a pipeline is still judged; an unparseable command keeps the old behavior.
Covers cargo, pytest `-k`, vitest `-t`, jest name filters and `|&`.

## Evidence

A plan check `cargo test --lib <filter> 2>&1 | rg -q '... 25 passed ...'` exited 0, but `code_step.py verify` failed the
box because `rg -q` prints nothing, so the phase could not close.

## Result

The piped check passes verify and the criteria dry run; a bare filtered runner with no `passed` line still fails.

## Watch

None.

## Back-out

Revert the commit.
