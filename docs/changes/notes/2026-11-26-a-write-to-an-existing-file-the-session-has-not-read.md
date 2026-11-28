---
type: "Change"
change_type: "fixed"
title: "A Write to an existing file the session has not read is refused"
description: "The Write hook denies replacing an existing file the writing session has not read since it last changed, and names the last session that wrote it, so a shared untracked log keeps another session's entries."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-26T09:00:00-06:00"}
seq: 1
kind: "fix"
components: ["script/fork-write-scope", "script/unread-overwrite"]
evidence: ["test"]
watches: []
test: "tests/scripts/test_unread_overwrite.py::UnreadOverwriteTest::test_a_second_session_write_to_an_unread_file_is_refused_with_the_last_writer_named"
asked: ""
proof: []
unmeasured: "No intake number counts overwrites of a shared log; the hook times are under Result."
---

## Change

`gates/fork_write_scope.py` runs `lib/unread_overwrite.py` on every Write before the code-fork check. For an existing, non-empty regular file it looks in the writing session's transcript (or the subagent's) for the last Read, Write or Edit result of the path, or @-mentioned file attachment of it. A result stamped before the file's mtime, or none, denies the Write. The deny names the last session or subagent whose transcript holds a Write or Edit result, or a Bash edit record, of the path at or after the mtime (a session by its ListAgents name, else its session id; a subagent by its agent id and its parent session), or says no live Claude session's Write, Edit or Bash edit record of it was found, and that a Bash command (this session's included), an editor, a script or an ended session changed it. A crash in the read check writes a stderr line naming the gate and lets the Write through; a crash in the last-writer lookup keeps the deny and names the error in the deny. `epoch_of_timestamp` moves from `lib/human_turn_lookup.py` to the standard-library `lib/transcript_time.py`, so the hook does not load human_turn_lookup's imports. `session_registry.session_transcripts` owns the transcript glob. `claude/.claude/scripts/CLAUDE.md` Owners names all three. `script_utils` no longer defines `epoch_of_timestamp`, so it stays free of toolkit imports; `api_error_stop`, `loop_transcript`, `fork_children` and `human_turn_lookup` import it from `transcript_time`.

## Evidence

One session replaced a shared untracked decisions log that another session had written, without reading it. The new test has a second session Write the shared log with no Read and gets a deny that names the first session. It also covers a read at or after the mtime, a read before it, an @-mentioned file, a new file, an empty file, a directory, a subagent transcript and a missing transcript.

## Result

Median of 40 hook runs on a new-file payload, before and after runs interleaved, twice: the hook before the change 15.6 and 15.5 ms, after it 16.2 and 16.2 ms, under 1 ms more. For context, a bare Python start takes about 7.6 ms on this machine. An existing file the session Wrote, with a 3.5 MB transcript, passes in a median 16.5 ms (15 runs). A deny over a 139 MB transcript with no record of the file, last-writer lookup over the live sessions included, takes a median 467 ms (5 runs).

## Watch

Read the next Write denies for false denies, such as a file the session read through a path spelled another way.

## Back-out

Remove `unread_overwrite_denied` and its call from `gates/fork_write_scope.py`, delete `lib/unread_overwrite.py` and `tests/scripts/test_unread_overwrite.py`, and restore the module docstring and the `__main__` comment of `gates/fork_write_scope.py`.
