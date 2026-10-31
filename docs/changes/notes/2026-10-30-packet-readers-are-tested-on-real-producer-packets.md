---
type: "Change"
change_type: "added"
title: "Packet readers are tested on real producer packets"
description: "The hand-back, review-fix, full-check and coder-report readers run in tests on packets captured from real review loops and coders on bench runs, and a capture script refreshes them, so a producer format change fails a test instead of a live run."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T00:00:00-05:00"}
seq: 311
kind: "fix"
components: ["script/handback", "script/review-fix", "script/full-check", "script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_producer_packets.py::ReviewLoopPacketTest::test_handback_reads_the_status_each_capture_was_stored_under"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `tests/scripts/fixtures/packets/` holds 13 captures: review-loop hand-backs (converged clean, fixed and with
  asks, cap reached, critical blocker, plan impact), full-check results (passed, failed, unverified, not run) and
  coder reports (behavior, why, plan impact). Each is kept as captured, with home paths replaced by `/home/captured`.
- `test_producer_packets.py` runs `handback.load`, the review-fix packet route, the full-check result readers and
  the code_step_report readers on them.
- New `tools/capture_packets.py` refreshes the captures from the hand-back store or a bench run tree, keeps the
  shortest packet per category, drops any packet that holds a credential word, token or email, and writes only under
  the fixtures folder. It sorts packets with the readers' own functions. New `lib/redact_text.py` holds the scrub and
  the secret check. Small helpers: `full_check.is_not_run`, `code_step_report.has_plan_impact_block`.

## Evidence

Read of the reader tests: every one hand-wrote its input, so producer and reader could drift apart unseen.

## Result

Readers pass on the captured packets. Targeted tests pass.

## Watch

None; a fix with no intake number.

## Back-out

Revert the commit.
