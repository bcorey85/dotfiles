---
type: "Change"
change_type: "fixed"
title: "The hand-back refuses a review packet with missing finding rows"
description: "The hand-back hook denies a review-loop packet, in any mode, whose per-finding rows or metrics line were not logged, before the packet reaches the caller."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T03:09:57-05:00"}
seq: 318
kind: "fix"
components: ["script/handback", "script/review-loop-gate", "agent/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_handback.py::OneCheckedHandBackTest::test_a_fix_first_hand_back_with_fixed_entries_and_no_finding_rows_is_denied_until_the_rows_are_logged"
asked: ""
proof: []
unmeasured: ""
---

## Change

- The ledger rule (rows owed by the packet against rows logged, nit rows, stale or mismatched metrics line) now
  lives in `loop_transcript.packet_ledger_reasons`. The stop gate and the hand-back hook both call it.
- `handback.transcript_gate_reason` adds the ledger check after the full-check and plan-file checks, so a packet
  with missing rows is denied before delivery, in every mode. The stop gate keeps its delivered-tail wording.
- `review-loop.md` Step 5b says fix-first and `no-review` hand-backs run Step 7 and Step 7b first.

## Evidence

- A `/fix` run (fix-first) handed back with only the metrics line and no per-finding rows. The only ledger check
  ran in the stop hook, after the packet had reached the caller, so the caller rebuilt the rows by hand.
- The new test_handback.py test fails on the old scripts: the packet with `fixed[]` entries and no rows was
  delivered.

## Result

- A packet with missing finding rows or metrics line is denied at hand-back with the same reason text the stop gate
  uses, and passes once the rows are logged.

## Watch

—

## Back-out

Revert the commit.
