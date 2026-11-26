# A Write never replaces a file another session changed since this session read it

Fix the queued defect `shared-decisions-log-can-be-written-over-by-a`: one session wrote a shared, untracked decisions
log over another session's copy, and the entries were lost. Claude Code's Write tool does not refuse to replace an
existing file the session never read (probed on 2.1.332: a Write on a file made by Bash, with no Read, succeeded).
The fix is a check in the existing PreToolUse hook on `Write`, `gates/fork_write_scope.py`, so no hook is registered
and `settings.json` is unchanged.

## Design

- New module `claude/.claude/scripts/lib/unread_overwrite.py`, standard library and `lib/transcript_time.py`
  (standard library only) at import:
  - Return no reason when the target does not exist, is not a regular file, or is empty.
  - Read the writing session's transcript: `transcript_path`, or the subagent transcript of `agent_id`
    (`script_utils.agent_transcript_path`, imported only then).
  - Search it from the end (mmap `rfind`) for `"filePath":"<path>"`. Parse each hit's line. A user line whose
    `toolUseResult` is a Read (`file.filePath`), Write or Edit (`filePath`) result of that path, or a Bash edit record
    (`toolUseResult.bashEditDiff.files[].filePath`), counts; so does an attachment line that @-mentions the file
    (`attachment.content.file.filePath`). The first such
    line from the end decides: its timestamp at or after the file's mtime means the session saw the current content.
  - Otherwise return a deny reason. Name the last writer: the live session or its subagent whose transcript (modified
    since the file's mtime) holds a Write or Edit result, or a Bash edit record
    (`toolUseResult.bashEditDiff.files[].filePath`), of the path at or
    after the mtime, a session by its ListAgents name, else its session id, a subagent by its agent id and parent
    session; with none, say no live Claude session's Write, Edit or Bash edit record of it was found and that a Bash
    command, an editor, a script or an ended session changed it.
- `gates/fork_write_scope.py` `main` runs the check for every Write before the code-fork check. Fail-open: a crash in
  the check writes a stderr line naming the gate and lets the Write through. A deny loads `hook_input` to emit it.
- Measure the hook's median time for a Write of a new file and of an existing, read file against a bare Python start;
  record both in the change file.

## Scope

- In: `lib/unread_overwrite.py`, `lib/transcript_time.py`, `lib/human_turn_lookup.py`, `gates/fork_write_scope.py`,
  `tests/scripts/test_unread_overwrite.py`, one change file in `docs/changes/`.
- Out: `settings.json`; appending in place of the Write (the agent Reads and then Edits or Writes the merged text).

## Phase Status

- [x] Phase 1: the Write hook refuses an unread overwrite and names the last writer (risk: medium)

## Phase 1: the Write hook refuses an unread overwrite and names the last writer

**Files**: `claude/.claude/scripts/lib/unread_overwrite.py`, `claude/.claude/scripts/lib/transcript_time.py`, `claude/.claude/scripts/lib/human_turn_lookup.py`, `claude/.claude/scripts/gates/fork_write_scope.py`
**Test**: `tests/scripts/test_unread_overwrite.py`

## Plan Deviations

- Phase 1: a Bash edit record (`toolUseResult.bashEditDiff.files[].filePath`) counts as a read in the read check and as a write in the last-writer lookup, as well as a Write or Edit result.
- Phase 1: the subagent transcript comes from `script_utils.agent_transcript_path(hook)`, which reads the event's `agent_transcript_path` first.
- Phase 1: a crash in the last-writer lookup keeps the deny and names the error in the deny text; only a crash in the read check fails open.
- Phase 1: the last-writer lookup reads live sessions and their subagents only, not recent ended sessions.
- Phase 1: with no writer found, the deny says no live Claude session's Write, Edit or Bash edit record was found, and names the kinds of cause it can be (another tool, an editor, a script, or a session that ended).
- Phase 1: an @-mentioned file attachment (`attachment.content.file.filePath`) counts as a read.

## Automated Verification

- `bash tests/run.sh`
