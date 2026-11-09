---
type: "Change"
change_type: "fixed"
title: "The review loop stays on the run's own files"
description: "In a tree where another session holds uncommitted edits, the review loop reviews and fixes only the run's own files: a `files:` list holds every other dirty file, `/code` holds the files dirty at the phase start that still hold the same bytes, and any coder edit to a held file is put back."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-08T20:06:04-06:00"}
seq: 13
kind: "fix"
components: ["script/review-loop-script", "script/code-review-start", "skill/code", "skill/handoff"]
evidence: ["review-loop-fixes-files-another-session-left-dirty"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_files_line_holds_every_other_dirty_file_from_the_fix_coder"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `review/review_loop_held.py` (new): the held files of a run are the prompt's `held files:` line, plus, when a `files:` line is given, every dirty file not on it. `review_loop_script.py` leaves them out of the review scope and the finding paths, names them in the fix coder's prompt as never-edit, saves their bytes before each coder call and puts back any change after it. A put-back, or a held file too large to save, is noted in the packet's `tool_fault`.
- `lib/file_backup.py`: `restore_changed`.
- `code/phase_start.py` (new): `/code` step 3 runs it in place of `git rev-parse HEAD`. It writes `<git dir>/code-phase/start.json` (HEAD and the hash of each dirty file) and prints the phase base. `code_review_start.py` reads it: a file dirty at the start with the same bytes now is held, left out of the handoff files and named on the `held files:` line. A record for another base stops the start; no record gives a stderr note and holds nothing.
- `skills/code/SKILL.md` step 3 and `skills/_shared/handoff-block.md` say so.

## Evidence

Queue item `review-loop-fixes-files-another-session-left-dirty`: three runs on 2026-11-08 in ~/agent-evals (two `/code`, one `/review --file a --file b` with a brief naming the other files off-limits) fixed a detector and its test in another session's dirty files.

## Result

Against the base scripts both new loop tests fail: the `files:` test leaves the other session's file reflowed, and the `held files:` test runs out of reviewer replies because the held file stays in scope. With the change both pass, with `test_phase_start.py` (4 tests). Suite: `bash tests/run.sh` passes.

## Watch

None. A held-file put-back shows in the packet's `tool_fault`.

## Back-out

Revert the commit. `/code` step 3 goes back to `git rev-parse HEAD`; a leftover `code-phase/start.json` is then unread.
