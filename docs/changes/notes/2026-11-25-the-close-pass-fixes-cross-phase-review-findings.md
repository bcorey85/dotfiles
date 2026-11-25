---
type: "Change"
change_type: "changed"
title: "The close pass fixes cross-phase review findings"
description: "The branch close pass fixes the review findings: an unreadable resume record is denied with its recovery, a put-back pass drops every approval ask it filed, and the asks block has one builder."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T11:58:47-06:00"}
seq: 2
kind: "fix"
components: ["script/review-loop", "script/code-step", "script/gate"]
evidence: ["tests/scripts/test_fork_write_scope.py", "tests/scripts/test_phase_start.py", "tests/scripts/test_review_loop_script.py", "tests/scripts/test_ruling_relay.py", "tests/scripts/test_reviewer_dispatch.py"]
watches: []
test: "tests/scripts/test_review_loop_script.py::test_a_capped_run_lists_its_closure_prose_and_late_repair_read_in_walk_order"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`/close-branch` on the whole branch. `review_asks.asks_done_lines` builds the asks block that `review_fix.py` printed from two copies. The resume stop gate denies an unreadable `resume.json` or an unfingerprintable tree with a text that names the file and the recovery, and its review text names the phase base. `phase_start.py --resume` exits with a named error when it cannot write the resume record. A put-back ruling pass drops every approval ask it filed. `reviewer_dispatch` sorts round files by their round number. `LOOP_DIR_FILE` and `PREVIOUS_LOOP_DIR_FILE` moved to the import-free `lib/stop_file_names.py`, so the resume gate no longer imports `code_wait`. The deny text for an unreadable record names only the review as the way forward, and a started review loop passes the gate before the record is read. A failed resume record write clears a stale `resume.json`. `review_fix.py launch` writes the run folder's `loop-dir` when a `resume.json` is there, so the resume gate sees the loop that applied the accepted asks, and the resume paragraph of the code skill orders `phase_start.py --resume` before that launch and writes the launch line in full. The ruling check refuses a reply that repeats one ruling's verdict, and the put-back docstring says only the approval asks for restored paths are dropped. Seven culled tests are deleted; tests are added for a plan ruling relayed by session id, the four-kind post-cap walk order and the printed stop naming the ruling.

## Evidence

The full check passed on the final tree. The fix-diff gate found no critical or high finding and no missing criterion.

## Result

Before, a corrupt resume record exited the gate with no recovery named, and a put-back pass left its approval asks open.

## Watch

—

## Back-out

Revert the commit.
