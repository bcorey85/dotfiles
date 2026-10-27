---
type: "Change"
title: "Skills and scripts never need the ledger to finish; verify-branch falls back on any unread ledger"
description: "New rule in toolkit-script-rules.md: no skill, agent or script needs the ledger to finish. verify_common now treats a missing or failing ledger like a busy one, so verify-prep and verify-log fall back to the checkout's own record of the logged review."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T07:16:43-05:00"}
seq: 2
kind: "user-rule"
components: ["script/script-utils", "script/verify-common", "script/verify-log", "script/verify-prep", "skill/audit", "skill/verify-branch"]
evidence: ["judgment"]
watches: []
test: ""
asked: "2026-10-27: my claude skills can never have a hard dependency on ledger"
proof: []
unmeasured: ""
---

## Change

- `docs/toolkit-script-rules.md` gets a section, "The ledger is optional": read through `script_utils.read_ledger`;
  when the ledger is not installed, stays busy or fails, go on without its answer and say what was not read; never
  read an unread ledger as an empty answer; write rows through `telemetry/ledger-write`.
- `script_utils.LedgerUnreadError` is the base of `LedgerNotInstalledError` and `LedgerBusyError`.
  `verify_common.review_ran` raises it for every ledger read with no answer: not installed, busy, an OSError, or
  any other non-zero exit. `review_state` catches it and falls back to `reviewLoggedTree`, as it already did for a
  busy ledger.
- verify-prep's skipped-input line to the plan-verifier no longer says "it stayed busy"; the reason names the cause.
- The /audit review lane runs `ledger worker --once` and repeats a read that exits 75 once (user sign-off,
  2026-10-27). A read that still exits non-zero is reported as `not read (<reason>)` and never counted as no rows.
  It had handled only a missing ledger, so a busy read could print "no escapes logged yet". The skills lane does the
  same for its `review_scope` count, so no other ledger read in /audit gets taken as empty.
- An audit of every other `ledger` call in skills, agents and scripts found no other one that stops a run: writers go
  through `ledger-write`, and their callers go on when a row is not written.

## Evidence

- Before: with no ledger installed, `review_ran` returned "not ran", so verify-prep asked for the review step on every
  run and verify-log refused the verifier rows. /verify-branch could never finish. Any other ledger failure raised
  `VerifyError` and stopped prep and log.
- `tests/scripts/test_verify_branch_script.py::PrepTest::test_a_failing_ledger_read_never_blocks_the_run` and
  `tests/scripts/test_verify_common_review_ran.py::ReviewStateWithoutLedger` cover the two paths.

## Result

- Touched tests and ruff pass in the worktree. `tests/run.sh` on 2026-10-27: 2909 tests in 78 files; the only
  failures are the RealPlansTest cases from the LED-46 and LED-48 plan files under `~/dev`, which fail on master too.

## Watch

—

## Back-out

Revert the commit.
