"""unread_overwrite.py: the deny reason for a Write that would replace a file the writing session has not seen in its
current state. Owner of that check. Standard library, `transcript_time` and `write_gate_name` (both import nothing
of the toolkit) at import; script_utils and session_registry load only when a subagent transcript or a last-writer
name is needed.

A session has seen the current content when its transcript holds a Read, Write or Edit result of the path, or an
@-mentioned file attachment of it, stamped at or after the file's mtime. A Bash command's own edit of the path, which
Claude Code records as `bashEditDiff`, counts as a write.
"""
import json
import math
import mmap
import os
import pathlib
import stat
import sys

import transcript_time
from write_gate_name import GATE_NAME

DENY_TEXT = ("unread-overwrite: {file_path} exists and this session has not read it since it last changed "
             "({writer}). Read it first, then Edit it or Write the merged text, so the other writer's content is kept.")
# A Claude Write or Edit result, or a Bash edit record, names a writer; a change by a process outside any live session
# leaves none.
NO_SESSION_WRITER = ("no live Claude session's Write, Edit or Bash edit of it was found, so it was changed by "
                     "a process outside any live Claude session, such as an editor, a script run outside Claude "
                     "or a session that has ended")


class TranscriptStampError(ValueError):
    """A transcript line that matches the path has no readable timestamp."""


def is_file_attachment_of(attachment, file_path):
    """True when `attachment` is an @-mentioned full file read of `file_path`."""
    if not isinstance(attachment, dict) or attachment.get("type") != "file":
        return False
    content = attachment.get("content")
    if not isinstance(content, dict):
        return False
    attached_file = content.get("file")
    return isinstance(attached_file, dict) and attached_file.get("filePath") == file_path


def is_bash_edit_of(tool_result, file_path):
    """True when a user line's `toolUseResult.bashEditDiff.files` lists `file_path`."""
    bash_edit = tool_result.get("bashEditDiff")
    if not isinstance(bash_edit, dict):
        return False
    edited_files = bash_edit.get("files")
    if not isinstance(edited_files, list):
        return False
    return any(isinstance(entry, dict) and entry.get("filePath") == file_path for entry in edited_files)


def result_stamp(line_object, file_path, kinds, transcript):
    """The timestamp (epoch seconds) of a transcript line that is a tool result or an @-mentioned file of `file_path`,
    else None. `kinds` is the set of result shapes that count: "read" (a user line's `toolUseResult.file.filePath`,
    or an attachment line's `attachment.content.file.filePath`) and "write" (a user line's `toolUseResult.filePath`,
    the Write and Edit results, or a `toolUseResult.bashEditDiff.files[]` entry of the path, a Bash edit).
    Raises TranscriptStampError, naming `transcript`, when a matching line has no readable timestamp."""
    line_type = line_object.get("type")
    if line_type == "attachment":
        is_read = is_file_attachment_of(line_object.get("attachment"), file_path)
        is_write = False
    elif line_type == "user":
        tool_result = line_object.get("toolUseResult")
        if not isinstance(tool_result, dict):
            return None
        read_file = tool_result.get("file")
        is_read = isinstance(read_file, dict) and read_file.get("filePath") == file_path
        is_write = tool_result.get("filePath") == file_path or is_bash_edit_of(tool_result, file_path)
    else:
        return None
    if not (("read" in kinds and is_read) or ("write" in kinds and is_write)):
        return None
    stamp_text = line_object.get("timestamp")
    try:
        return transcript_time.epoch_of_timestamp(stamp_text)
    except (ValueError, AttributeError) as error:
        raise TranscriptStampError(f"{transcript}: a result of {file_path} has an unreadable timestamp {stamp_text!r}; "
                         f"expected an ISO 8601 string such as 2026-11-15T06:22:12.305Z") from error


def milliseconds_of_mtime(mtime):
    """The mtime in whole milliseconds, the precision of a transcript timestamp."""
    return math.floor(mtime * 1000)


def milliseconds_of_stamp(stamp):
    """A transcript timestamp in whole milliseconds."""
    return round(stamp * 1000)


def line_around(mapped, hit):
    """The bytes of the transcript line that holds offset `hit`."""
    start = mapped.rfind(b"\n", 0, hit) + 1
    end = mapped.find(b"\n", hit)
    if end == -1:
        end = len(mapped)
    return mapped[start:end]


def last_result_stamp(transcript, file_path, kinds):
    """The timestamp of the last result of `file_path` in the transcript file (searched from the end), else None.
    A line that is not JSON is skipped: a transcript line can be cut mid-write."""
    needle = b'"filePath":' + json.dumps(file_path, ensure_ascii=False).encode("utf-8")
    with open(transcript, "rb") as handle:
        if os.fstat(handle.fileno()).st_size == 0:
            return None
        with mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as mapped:
            position = len(mapped)
            while True:
                hit = mapped.rfind(needle, 0, position)
                if hit == -1:
                    return None
                position = hit
                try:
                    line_object = json.loads(line_around(mapped, hit))
                except ValueError:
                    continue
                if not isinstance(line_object, dict):
                    continue
                stamp = result_stamp(line_object, file_path, kinds, transcript)
                if stamp is not None:
                    return stamp


def writing_transcript(hook):
    """The transcript of the writing session, or of its subagent when the hook event names an `agent_id`."""
    if not hook.get("agent_id"):
        return hook["transcript_path"]
    import script_utils
    return script_utils.agent_transcript_path(hook)


def live_session_transcripts():
    """The transcript of each live session and of its subagents. Only live sessions are read: a global scan of every
    transcript is too slow for a hook that runs on every Write."""
    import script_utils
    import session_registry
    subagent_name = script_utils.subagent_transcript_name("*")
    found = []
    for row in session_registry.live_session_rows():
        session_id = row.get("sessionId")
        if not isinstance(session_id, str) or not session_id:
            continue
        found.extend(session_registry.session_transcripts(session_id))
        subagents_dir = session_registry.session_subagents_dir(session_id)
        if subagents_dir is not None:
            found.extend(subagents_dir.glob(subagent_name))
    return found


def candidate_transcripts(mtime):
    """Every live session and subagent transcript modified at or after `mtime`, newest first. A transcript that
    vanishes between the listing and the stat is left out: the lookup only names a writer, and must not cancel the
    deny."""
    found = []
    for candidate in live_session_transcripts():
        try:
            modified = candidate.stat().st_mtime
        except FileNotFoundError:
            continue
        if modified >= mtime:
            found.append((modified, candidate))
    found.sort(key=lambda entry: entry[0], reverse=True)
    return [candidate for _, candidate in found]


def writer_name(candidate):
    """A session's ListAgents name, else its id; a subagent is named by its parent session and its agent id."""
    import script_utils
    import session_registry
    if candidate.parent.name != session_registry.SUBAGENTS_DIR_NAME:
        return session_registry.session_display_name(candidate.stem) or candidate.stem
    session_id = candidate.parent.parent.name
    agent_id = script_utils.subagent_id_from_transcript_name(candidate.name)
    return f"subagent {agent_id} of {session_registry.session_display_name(session_id) or session_id}"


def last_writer(file_path, mtime, own_transcript):
    """The name of the session or subagent whose transcript (modified since `mtime`) holds a Write or Edit result, or
    a Bash edit record, of the path at or after `mtime`. NO_SESSION_WRITER when none does."""
    own_resolved = pathlib.Path(own_transcript).resolve() if own_transcript else None
    mtime_ms = milliseconds_of_mtime(mtime)
    for candidate in candidate_transcripts(mtime):
        if candidate.resolve() == own_resolved:
            continue
        try:
            stamp = last_result_stamp(candidate, file_path, {"write"})
        except FileNotFoundError:
            # The transcript vanished between the listing and the read. Any other OSError (a permission error)
            # reaches writer_description, which reports it on stderr.
            continue
        if stamp is None or milliseconds_of_stamp(stamp) < mtime_ms:
            continue
        return writer_name(candidate)
    return NO_SESSION_WRITER


def unread_overwrite_reason(file_path, hook):
    """The deny text for a Write of `file_path` by the session or subagent that the hook event `hook` names, else
    None. None when the target is missing, not a regular file or empty, when no transcript is named or readable, or
    when the session has seen the current content."""
    if not file_path or not hook.get("transcript_path"):
        return None
    try:
        file_stat = os.stat(file_path)
    except OSError:
        return None
    if not stat.S_ISREG(file_stat.st_mode) or file_stat.st_size == 0:
        return None
    transcript = writing_transcript(hook)
    try:
        seen = last_result_stamp(transcript, file_path, {"read", "write"})
    except OSError as error:
        # Fail-open on purpose: an unreadable transcript must not block every Write, but the skipped check is reported.
        sys.stderr.write(f"{GATE_NAME}: the unread-overwrite check could not read {transcript} "
                         f"({type(error).__name__}: {error}), so the Write goes on\n")
        return None
    if seen is not None and milliseconds_of_stamp(seen) >= milliseconds_of_mtime(file_stat.st_mtime):
        return None
    writer_text = writer_description(file_path, file_stat.st_mtime, transcript)
    return DENY_TEXT.format(file_path=file_path, writer=writer_text)


def writer_description(file_path, mtime, own_transcript):
    """The deny text's account of the writer. A crash in the lookup keeps the deny: the lookup only names the writer,
    so this function writes the error to stderr and the deny text says the writer is unknown."""
    try:
        writer = last_writer(file_path, mtime, own_transcript)
    except Exception as error:
        sys.stderr.write(f"{GATE_NAME}: the unread-overwrite last-writer lookup crashed "
                         f"({type(error).__name__}: {error})\n")
        return f"writer could not be looked up ({type(error).__name__}: {error})"
    if writer == NO_SESSION_WRITER:
        return NO_SESSION_WRITER
    return f"last written by {writer}"
