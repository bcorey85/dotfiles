---
type: "Change"
change_type: "fixed"
title: "The review loop stays on the run's own files"
description: "In a tree where another session holds uncommitted edits, the review loop reviews and fixes only the run's own files: a `files:` list holds every other dirty file, `/code` holds the files dirty at the phase start that still hold the same bytes, and a coder's own write to a held file is undone only when no other change landed on it during the call."
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

- `review/review_loop_held.py` (new): the held files of a run are the prompt's `held files:` line, plus, when a `files:` line is given, every dirty file not on it. `review_loop_script.py` leaves them out of the review scope and the finding paths, names them in the fix coder's prompt as never-edit, and saves their bytes before each coder call. After the call it replays the coder's Edit and Write calls (from its session transcript) on the saved bytes; a held file that holds exactly that result goes back to the saved bytes. A held file the coder did not write keeps whatever its owner wrote during the call. One the coder wrote that holds anything else is left as it is. Each put-back or left file, a missing transcript, and a held file too large to save is noted in the packet's `tool_fault`. A held file never counts as changed by the coder.
- `lib/session_edits.py` (new): the Edit and Write calls of a session transcript that did not fail, and their replay.
- `code/phase_start.py` (new): `/code` step 3 runs it in place of `git rev-parse HEAD`. It writes `<git dir>/code-phase/start.json` (HEAD and the hash of each dirty file) and prints the phase base. `code_review_start.py` reads it: a file dirty at the start with the same bytes now is held, left out of the handoff files and named on the `held files:` line. A record for another base stops the start; no record gives a stderr note and holds nothing.
- `skills/code/SKILL.md` step 3 and `skills/_shared/handoff-block.md` say so.

## Evidence

Queue item `review-loop-fixes-files-another-session-left-dirty`: three runs on 2026-11-08 in ~/agent-evals (two `/code`, one `/review --file a --file b` with a brief naming the other files off-limits) fixed a detector and its test in another session's dirty files.

## Result

Against the base scripts both new loop tests fail: the `files:` test leaves the other session's file reflowed, and the `held files:` test runs out of reviewer replies because the held file stays in scope. Two race tests, where the owning session edits the held file during the coder call, fail against the first draft of this change (the put-back erased that edit) and pass now. With the change all pass, with `test_phase_start.py` (4 tests) and `test_session_edits.py` (3). `session_edits.file_writes` parsed 400 of 400 recent real transcripts. Suite: `bash tests/run.sh` passes.

## Watch

None. A held-file put-back shows in the packet's `tool_fault`.

## Back-out

Revert the commit. `/code` step 3 goes back to `git rev-parse HEAD`; a leftover `code-phase/start.json` is then unread.
