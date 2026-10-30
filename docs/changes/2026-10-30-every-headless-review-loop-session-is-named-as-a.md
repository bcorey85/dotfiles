---
type: "Change"
change_type: "fixed"
title: "The disposition retry note no longer refers to a last reply, and a test pins every headless role's child-of-parent name"
description: "The disposition retry note no longer refers to a last reply, and a test now pins that each headless role the review loop launches carries a child-of-parent name."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-30T06:06:40-05:00"}
seq: 327
kind: "fix"
components: ["script/review-loop-script"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_bad_disposition_reply_then_a_good_one_retries_once_and_returns_the_findings"
asked: ""
proof: []
unmeasured: ""
---

## Change

Two tests run the loop through every headless role it launches (check-finder, reviewer, disposition, disposition-retry, fix coder, class closure, class-repair coder) and assert each launched `claude` call carries `--name "child of <parent> (<role>)"`. One runs with a parent that has a display name, one with a parent that has none (label is `session <id>`).

The disposition retry note now reads "A previous reply to this prompt could not be parsed: ...". The retry runs in a fresh session, which has no "last reply".

The retry-role test is renamed to `test_the_disposition_retry_runs_under_its_own_role`, since it checks the role passed to the model step, not a calls.jsonl row.

## Evidence

Judgment. Every `claude_call` site was read to get the real role strings, and the run was checked against the stand-in `claude`, which records the `--name` argument.

## Result

The new per-role tests pass before and after this change: naming already landed, so they pin existing behavior and would fail only if a role lost its name. The wording test, which now expects the new retry note, fails before the change and passes after it.

## Watch

None.

## Back-out

Revert the retry note string in `disposition_call` and the test edits. Nothing else depends on them.
