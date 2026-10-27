---
type: "Change"
title: "A busy ledger read waits about 90 s before it gives up"
description: "script_utils.read_ledger retries a ledger read that exits 75 for up to LEDGER_WAIT_SECONDS = 90 (8 tries, 84 s of pauses), and verify_common and the branch-recap deferred read both go through it in place of their own retry loops."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T22:35:21-05:00"}
seq: 89
kind: "fix"
components: ["script/script-utils", "script/verify-common"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_script_utils.py::ReadLedgerTest::test_a_ledger_busy_for_six_tries_is_waited_for_and_its_answer_returned"
asked: ""
proof: []
unmeasured: ""
---

## Change

- New `read_ledger(args)` in `script_utils.py`: runs `ledger <args>`, retries exit 75 and per-call timeouts with a
  growing pause, as many tries as fit in `LEDGER_WAIT_SECONDS = 90` (`attempts_within`), then raises
  `LedgerBusyError` naming the command, the ledger's own last stderr line and the seconds waited. No `ledger` on PATH
  raises `LedgerNotInstalledError`.
- `verify_common.review_ran` reads through it and raises `script_utils.LedgerBusyError`, which `review_state` turns
  into the checkout's-own-record fallback (the verify-prep change of the same day). Its own 6-try, 60 s loop, its
  `LedgerBusyError` and the `VERIFY_LEDGER_*` env names are gone; the test-only env names are
  `LEDGER_READ_BACKOFF_SECONDS` and `LEDGER_READ_CALL_TIMEOUT_SECONDS`.

## Evidence

- Since ledger readers stopped building the cache, a read that is behind exits 75 at once and a worker catches up,
  which takes tens of seconds. Peer reports the same day: verify-prep stalled 8-10 min in three sessions; the
  agent-evals intake's edit-watch step failed after 18 s; branch-recap had no path for exit 75.
- The new test (a ledger busy for six tries) fails under a 6-try budget and passes after.

## Result

- Targeted tests and ruff pass in the worktree; full suite result in the hand-over message.

## Watch

—

## Back-out

Revert the commit.
