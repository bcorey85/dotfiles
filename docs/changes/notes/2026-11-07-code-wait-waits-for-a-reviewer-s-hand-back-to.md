---
type: "Change"
change_type: "fixed"
title: "code_wait waits for a reviewer's hand-back to reach its transcript"
description: "The /code fork's wait now writes a reviewer's report even when the harness marks the reviewer finished before the hand-back's result line is on disk, so the fork no longer re-dispatches reviewers or has coders hand-write report files."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-07T23:32:16-06:00"}
seq: 13
kind: "fix"
components: ["script/code-wait"]
evidence: ["defect report", "tests"]
watches: []
test: "tests/scripts/test_code_wait.py::ReviewerRequestTest::test_a_hand_back_result_flushed_after_the_finished_meta_still_writes_the_report"
asked: ""
proof: []
unmeasured: ""
---

## Change

`code_wait.agent_report` re-reads a finished agent's transcript for up to 3 seconds while a SubagentHandback call has
no result yet or the read holds no report. `loop_transcript.LoopTranscript` gains `handback_pending`, true while a
hand-back call has no result line. A hook-denied hand-back still never counts as the report.

## Evidence

On a live ledger run the reviewer's `.meta.json` turned finished 45 ms before its last transcript line (the
hand-back's result) reached disk. `code_wait.py review` read in between, found no report, and exited 1 with "The
agent finished with no report", so the fork re-dispatched the reviewer. The new test appends the result line 0.3 s
after a finished meta: it fails before the fix (the pre-hand-back text was written as the report) and passes after.

## Result

Over 12854 finished subagent transcripts on this machine, every one yields a report and none is left with a pending
hand-back. The script suite passes.

## Watch

None: the intake does not count reviewer re-dispatches after a no-report wait.

## Back-out

Revert `agent_report` in `scripts/code/code_wait.py` to one read, and drop `handback_results` and `handback_pending`
from `scripts/lib/loop_transcript.py`, with the test.
