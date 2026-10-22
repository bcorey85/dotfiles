---
type: "Change"
title: "verify-branch retries a busy ledger before it reads the review state"
description: "verify_common.review_ran runs `ledger yield --review-trees` with a 60 s timeout and up to 4 tries when the ledger exits 75 (busy). If the ledger stays busy, it fails with a message that says to run the step again."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-22T09:51:55-05:00"}
seq: 7
components: ["script/verify-common", "script/script-utils"]
evidence: ["work incident"]
watches: []
---

## Change

- `scripts/script_utils.py`: new `run_retrying(argv, retryExitCodes, attempts, backoffSeconds, timeoutSeconds)`. It tries a run again after a retry exit code or a timeout, with a longer pause each time.
- `scripts/verify_common.py`, `review_ran`:
  - It calls `ledger yield --review-trees` through `run_retrying`: retry on exit 75 only, 4 tries, a 3 s backoff step and a 60 s timeout for each call.
  - If the last try is still busy or times out, it fails with "the ledger is busy … run this step again in a minute".
  - Exit 1 and other exit codes fail at once, as before.
  - The environment variables `VERIFY_LEDGER_TIMEOUT_SECONDS` and `VERIFY_LEDGER_BACKOFF_SECONDS` exist for tests.
- Tests: `test_script_utils.py` and `test_verify_common_review_ran.py` under `tests/scripts/`.

## Evidence

- Work incident: verify-prep on a busy ledger printed only "ledger yield: database is locked". The second run hung past 110 s, and the third run passed. The ledger now waits at most 10 s on a lock, then exits 75.

## Result

A busy ledger costs a short wait, not a failed or hung branch-end step. A busy ledger never reads as "no review ran".

## Watch

None. The intake does not count verify-prep failures by cause.

## Back-out

Restore the plain `run(["ledger", "yield", "--review-trees"])` call in `verify_common.py` from git. `run_retrying` can stay.
