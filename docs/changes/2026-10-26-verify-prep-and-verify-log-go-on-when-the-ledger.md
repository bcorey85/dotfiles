---
type: "Change"
title: "verify-prep and verify-log go on when the ledger stays busy"
description: "A ledger that stays busy or behind no longer stops /verify-branch: the retries wait about a minute, the message names the wait and the ledger's own line, and a review that verify-log logged from this checkout for the same tree stands in for the ledger's answer."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T22:32:31-05:00"}
seq: 74
kind: "fix"
components: ["script/verify-prep", "script/verify-log", "skill/verify-branch"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_verify_branch_script.py::PrepTest::test_a_busy_ledger_reads_the_review_this_checkout_logged_and_the_verifier_prompt_names_the_skip"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `verify_common.review_ran` raises `LedgerBusyError` when `ledger yield --review-trees` still exits 75 or times out
  after its last try. The message names the tries, the seconds of pauses and the ledger's last stderr line.
- The retries go from 4 tries with a 3 s step (18 s of pauses) to 6 tries with a 4 s step (60 s of pauses).
- `verify_common.review_state` wraps it. On a busy ledger the review counts as ran only when the branch's saved context
  holds `reviewLoggedTree` equal to the current tree fingerprint. `verify-log review` saves that key after it writes
  the review rows, and `verify-prep` carries it forward.
- `verify-prep` exits 0 on a busy ledger. It prints the review step when no review of this tree was logged from this
  checkout, and otherwise the plan-verifier step with a line that tells the verifier to name the skipped ledger read.
- `verify-log --rows` logs on a busy ledger when this checkout logged the review of this tree, and says so on stderr.
  It still exits 2 when none was logged. `verify-log review` refuses a second review row for a tree the local record
  covers, so a busy ledger cannot lead to a duplicate.

## Evidence

- Three sessions on 2026-10-26 had verify-prep exit 2 on a busy or behind ledger, 8 to 10 times over 8 to 10 minutes
  each. Each one hand-built the verifier payload through a scratch wrapper. A /code run escalated it to its
  orchestrator.
- Ledger writes go through while the read cache is behind, so a local record of the logged review is safe to read in
  place of the cache.
- The new prep and log tests fail on the base commit (prep exits 2 on the busy stub) and pass after.

## Result

- The two verify test files pass: 116 and 10 tests. Full suite: 2395 tests, 0 failed; lint passes.

## Watch

—

## Back-out

Revert the commit. A context saved with `reviewLoggedTree` is read by nothing once reverted.
