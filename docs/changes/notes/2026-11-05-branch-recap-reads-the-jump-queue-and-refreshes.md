---
type: "Change"
change_type: "fixed"
title: "branch-recap reads the jump queue and refreshes the ledger itself"
description: "stage prints the jump queue before the tier report, and ledger_deferred runs the ledger worker once on a busy ledger, then reads once, with no command handed to the user."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-05T17:09:31-06:00"}
seq: 12
kind: "fix"
components: ["skill/branch-recap", "skill/close-branch", "script/ledger-deferred"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_ledger_deferred.py::LedgerDeferredTest::test_a_busy_ledger_gets_a_worker_run_and_then_the_queue_prints"
asked: ""
proof: []
unmeasured: ""
---

## Change

`stage.mjs` prints the jump-queue block before the tier report. `ledger_deferred.py` runs `ledger worker --once` once when the ledger is busy, then reads the queue once. A ledger that stays busy, a failing worker or a hung worker exits 75 and names what happened; no command is handed to the user. The branch-recap and close-branch skill text tell the caller to read the jump queue from the stage output and to leave the ledger refresh to the script. The `read_ledger` `wait_seconds` comment in `script_utils.py` describes the new wait.

## Evidence

judgment: a busy ledger left branch-recap with an empty deferred list and a command for the user to run. The new tests in `test_ledger_deferred.py` and `test_stage_run.py` cover the worker run, the three exit-75 cases and the print order.

## Result

Targeted tests for the changed files pass.

## Watch

—

## Back-out

Revert the worker run in `ledger_deferred.py`, the print order in `stage.mjs`, the two skill texts, the comment in `script_utils.py`, and the tests.
