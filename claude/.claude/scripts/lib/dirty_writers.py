"""dirty_writers.py: which live session wrote the dirty files of a repo. A session is a writer when its transcript, or
one of its subagents' transcripts, holds a write call with an absolute path on a dirty path, recorded after a cutoff
commit (HEAD, or a start record's head). A live session found by working folder alone is only a candidate,
never a holder. A write by the own session vetoes the sole writer (`DirtyWriters.sole_writer`, for
pull_keep_index), while `holder_with_paths` only drops the paths the own session wrote from the candidates (for
phase_start, code_review_start and review_loop_held)."""
import os
import pathlib
import sys
from typing import NamedTuple

import loop_transcript
import script_utils
import session_registry


class DirtyWriters(NamedTuple):
    """The evidence on who wrote the dirty files: whether this session may have (it wrote one, or a transcript of
    its could not be read), the other live sessions' rows that did, and the labels of those whose transcripts were
    not read."""
    own_wrote: bool
    writers: list
    unread: list

    def sole_writer(self):
        """The row of the one other session that wrote a dirty file, when every other session's transcripts were
        read and this session wrote none; else None."""
        if len(self.writers) == 1 and not self.unread and not self.own_wrote:
            return self.writers[0]
        return None


class HolderPaths(NamedTuple):
    """The one other live session that wrote dirty files, and the dirty paths it wrote."""
    row: dict
    paths: list


def dirty_paths_written(repo, transcripts, dirty, since):
    """The set of dirty paths (relative to `repo`) that the transcripts hold a write call on, recorded after `since`
    (epoch seconds), or None when a transcript cannot be read. A call with a relative path is no evidence, because
    the folder it ran in is not recorded."""
    repo_path = pathlib.Path(repo).resolve()
    dirty_paths = set(dirty)
    found = set()
    for transcript in transcripts:
        try:
            written = loop_transcript.written_paths(transcript, since=since)
        except OSError as error:
            sys.stderr.write(f"dirty_writers: could not read the transcript {transcript}: {error}\n")
            return None
        for written_path in written:
            if not os.path.isabs(written_path):
                continue
            relative = script_utils.repo_relative(repo_path, written_path)
            if relative in dirty_paths:
                found.add(relative)
    return found


def own_session_may_have_written(repo, dirty, since, own_session_id):
    """Whether the session `own_session_id` wrote a dirty path, or has a transcript that could not be read. A session
    with no id or no transcript is no evidence."""
    if not own_session_id:
        return False
    paths = own_written_paths(repo, dirty, since, own_session_id)
    return paths is None or bool(paths)


def other_session_paths(repo, row, dirty, since):
    """The dirty paths another live session's transcripts hold a write on; None when it has no transcript or one
    cannot be read."""
    transcripts = session_registry.session_transcripts(row.get("sessionId"))
    if not transcripts:
        return None
    return dirty_paths_written(repo, transcripts, dirty, since)


def dirty_writers(repo, others, dirty, since, own_session_id):
    """The DirtyWriters of `others` (registry rows of the other live sessions in the repo) for the `dirty` paths,
    counting writes recorded after `since` (epoch seconds)."""
    own_wrote = own_session_may_have_written(repo, dirty, since, own_session_id)
    writers = []
    unread = []
    for row in others:
        written = other_session_paths(repo, row, dirty, since)
        if written is None:
            unread.append(session_registry.holder_label(row))
        elif written:
            writers.append(row)
    return DirtyWriters(own_wrote, writers, unread)


def own_written_paths(repo, dirty, since, own_session_id):
    """The dirty paths this session wrote, or None when one of its transcripts cannot be read. No transcript means
    no paths."""
    transcripts = session_registry.session_transcripts(own_session_id)
    if not transcripts:
        return set()
    return dirty_paths_written(repo, transcripts, dirty, since)


def holder_with_paths(repo, dirty, own_session_id, commit="HEAD"):
    """The HolderPaths of the one live session other than `own_session_id` that wrote a dirty path of `repo` after
    the commit `commit` (a start record passes its recorded head), else None: no such session, several, an unreadable
    transcript, a live session with no transcript, every dirty path written by this session, or no readable commit
    time of `commit`. A path this session wrote is left out of the candidates.
    Fails open: no proven writer means no holder."""
    if not own_session_id or not dirty:
        return None
    others = session_registry.other_live_sessions_in(repo, own_session_id)
    if not others:
        return None
    since = script_utils.head_commit_time(repo, commit)
    if since is None:
        return None
    own_paths = own_written_paths(repo, dirty, since, own_session_id)
    if own_paths is None:
        return None
    candidates = [path for path in dirty if path not in own_paths]
    if not candidates:
        return None
    writers = []
    for row in others:
        written = other_session_paths(repo, row, candidates, since)
        if written is None:
            return None
        if written:
            written_paths = sorted(written)
            writers.append(HolderPaths(row, written_paths))
    if len(writers) != 1:
        return None
    return writers[0]
