---
type: "Change"
title: "Review-loop stop hook blocks a packet with unlogged finding rows or a plan-file edit"
description: "The review-loop stop check blocks once when the packet lists findings with no per-finding ledger rows or no metrics line, or names the plan file in files_touched."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-26T17:03:29-05:00"}
seq: 63
kind: "fix"
components: ["agent/review-loop", "script/review-loop-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_gate.py::LedgerRowsTest::test_a_packet_with_a_fixed_finding_and_no_finding_row_is_blocked_once"
asked: ""
proof: []
unmeasured: ""
---

## Change

- review_loop_gate.py counts the finding-row and metrics Bash calls in the loop transcript and parses the final packet. It blocks once when the packet lists more findings than rows logged, or no metrics line ran.
- It also blocks once when the packet's files_touched names the caller's plan file. review-loop.md states that a review fix never edits the plan.
## Evidence

- A /code run handed back with only the metrics line and ask row logged, and a review round edited spec.md. The new tests fail on the base script (it never blocks on either).
- review-loop.md Step 0: review-scope exit 3 (no merge base) stops the loop and reports the message; only other failures fall back to `git status`.

## Result

- Gate and hand-back tests and ruff pass.

## Watch

—

## Back-out

Revert the commit.
