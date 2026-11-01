---
type: "Change"
change_type: "fixed"
title: "A stray parse failure leaves a finished packet finished"
description: "A bad packet piped to `review_fix.py` after a packet finished no longer marks the saved state parse-failed, so rerunning the finished packet prints done instead of rendering and asking again."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-01T02:03:59-06:00"}
seq: 436
kind: "fix"
components: ["script/review-fix"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest::test_a_stray_parse_failure_leaves_a_finished_packet_finished"
asked: ""
proof: []
unmeasured: "A fix with a failing-before test; no intake number counts finished packets reopened by a parse failure."
---

## Change

The `PacketError` handler in `review_fix.main` calls the new `mark_parse_failed`, which leaves a state whose stage is in `FINISHED_STAGES` alone. An open packet's state still gets stage `parse-failed`.

## Evidence

judgment: a bug hunt showed route a plan-impact packet, `decide keep`, then pipe garbage to `packet`. The handler overwrote stage `done` with `parse-failed`, so the `FINISHED_STAGES` guard missed and the finished packet rendered and asked for a plan ruling again.

## Result

The rerun prints `ACTION: done`.

## Watch

—

## Back-out

Revert the commit.
