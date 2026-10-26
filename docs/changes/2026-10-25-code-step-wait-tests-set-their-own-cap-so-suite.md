---
type: "Change"
title: "Code-step wait tests set their own cap so suite load cannot reach it"
description: "The code-step hand-back cap now reads an optional CODE_STEP_WAIT_MULTIPLE, which defaults to the same three waits; the tests that expect a wait set it to 60, so a slow setup under suite load no longer turns their wait into a cap stop."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-25T18:55:03-05:00"}
seq: 10
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_a_wait_on_a_launched_dispatch_keeps_waiting"
asked: ""
proof: []
unmeasured: ""
---

## Change

`code/code_step_core.py` `wait_for_handback`: the total wait cap is `limit * CODE_STEP_WAIT_MULTIPLE`, read from the
environment like `CODE_STEP_WAIT_SECONDS`, with the default `HANDBACK_TOTAL_WAIT_MULTIPLE` (3). No run sets it, so
the cap a session sees is unchanged.

`tests/scripts/test_code_step.py` `wait_env` takes `waits=60` and sets the variable. The tests of the stop at the cap
pass `waits=3`, the script's own multiple.

## Evidence

The cap counts from the dispatch time that the test setup writes. With `wait_env(1, ...)` the cap was 3 seconds, and
the step stopped once 2 had passed. Under suite load, setup alone took longer, so a test that expected `ACTION: wait`
got `ACTION: stop`. Seen in four full runs on 2026-10-24, each test passing alone. Moving the dispatch time forward
instead was tried and rejected: it also moves the window that decides which hand-back rows count, so a row the test
wrote before the step stopped counting.

## Result

Three full suite runs in a row under `nice -n 19`: 2049 of 2051 passed each time, with no wait-test failure. With
the cap check removed, the tests of the stop at the cap failed. After merging master: 2116 of 2118 passed. The two
failures in every run are `test_plan_format.RealPlansTest` and `test_verify_branch_script.RealPlansTest`. They fail
the same way on master, because a live plan in another worktree has a level-5 heading.

## Watch

None. Test-suite timing has no intake number.

## Back-out

Revert the commit.
