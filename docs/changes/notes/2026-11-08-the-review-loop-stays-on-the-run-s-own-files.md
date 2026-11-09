---
type: "Change"
change_type: "fixed"
title: "The review loop stays on the run's own files"
description: "In a tree where another session holds uncommitted edits, a review loop given a `files:` list reviews and fixes only those files: every other dirty file is held, kept out of the review and the findings, named never-edit in the fix coder's prompt, and never written back; a held file that changes during a coder call is named in the hand-back's tool fault."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-08T20:06:04-06:00"}
seq: 13
kind: "fix"
components: ["script/review-loop-script", "script/handback"]
evidence: ["review-loop-fixes-files-another-session-left-dirty"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_files_line_holds_every_other_dirty_file_from_the_fix_coder"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `review/review_loop_held.py` (new): when the prompt has a `files:` line, every dirty file not on it is held. `review_loop_script.py` leaves held files out of the review scope and the finding paths, and names them in the fix coder's prompt as never-edit. One helper, `skip_held_items`, records every item on a held file (a reviewer's fix, a caller's fix-first finding, a class-closure member) in the packet's `skipped_fp` once, with the reason "the file is held by another session", and counts it in the skipped tally. A held class member never goes to `open_classes`, so it never gates clean status. A nit on a held file goes to the packet's nits. The fix coder gets none of them.
- The loop takes a digest of each held file before each coder call. A held file that changed during the call is left as it is, never counts as changed by the coder, and is named in the packet's `tool_fault`. The loop never writes a held file.
- `review/handback.py` `render` prints the packet's `tool_fault` as a `Tool fault:` line, so the user reads the held-file note.
- `review/review_loop_coder.py` (new): the fix-coder call and its tree snapshots, moved out of `review_loop_script.py` so that script stays under 1000 lines. `script_utils.without_paths` drops the held paths from a snapshot.

## Evidence

Queue item `review-loop-fixes-files-another-session-left-dirty`: three runs on 2026-11-08 in ~/agent-evals (two `/code`, one `/review --file a --file b` with a brief naming the other files off-limits) fixed a detector and its test in another session's dirty files.

## Result

Only a run with a `files:` line holds files. `/code` runs pass no `files:` line, so they hold nothing: two of the three cited incidents are not covered, and the queue item stays open for `/code`. Against the base script the `files:` test fails: the reviewer's finding on the other session's file reaches the fix coder, which rewrites it. With the change it passes: the file stays byte-equal and the finding is skipped. A finding on an owned nested file that shares a basename with a held root file still reaches the coder. New loop tests for a held-file finding, a fix-first finding, a class member, a nit, and a held file that changes during the coder call (left as it is and named in the rendered hand-back) pass. Suite: `bash tests/run.sh` passes.

## Watch

None. A held file that changed during a coder call shows as a `Tool fault:` line in the hand-back.

## Back-out

Revert the commit.
