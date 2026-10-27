---
type: "Change"
title: "branch-recap reads the deferred queue through a script that waits out a cache behind"
description: "branch-recap Step 2 runs scripts/tools/ledger_deferred.py, which waits the shared 90 s for a ledger that is behind and otherwise prints deferred: not read with the command to run, never an empty queue."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T22:35:21-05:00"}
seq: 90
kind: "fix"
components: ["skill/branch-recap", "script/ledger-deferred"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_ledger_deferred.py::LedgerDeferredTest::test_a_ledger_that_stays_busy_exits_75_with_the_command_to_run"
asked: ""
proof: []
unmeasured: ""
---

## Change

- New `scripts/tools/ledger_deferred.py` runs `ledger yield --deferred` through `read_ledger`. Outcomes: the queue
  (exit 0); `deferred: not tracked (ledger not installed)` (exit 0); ``deferred: not read (<reason>). Run
  `ledger worker --once`, then `<the script's own path>` to read the queue.`` (exit 75); on any
  other ledger failure the ledger's stderr and exit code, plus `deferred: not read (<last stderr line, or "exited
  <code>">)` on stdout.
- branch-recap Step 2 calls the script in place of its inline bash block and names the unread outcomes, in the step and
  in the recap's Deferred findings line. /code's recap phase runs /branch-recap, so it gets the same path.

## Evidence

- 2026-10-26: one branch-recap run hit exit 75 twice and invented a "not read" line; one /code recap failed 6 retries
  and reported deferred items as "not tracked". An unread queue that reads as empty loses deferred findings.
- The new busy test fails on the base commit (no script) and passes after.

## Result

- Targeted tests and ruff pass in the worktree; full suite result in the hand-over message.

## Watch

—

## Back-out

Revert the commit.
