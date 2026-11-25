"""human_turn_lookup.py: finds a turn the user typed into another live Claude Code session.

A session name maps to one live row in the sessions folder (`<pid>.json`, fields `name`, `sessionId`); its
transcript is the one `<sessionId>.jsonl` in a folder under the projects folder (the folder need not match the row's
cwd); `session_registry` owns both folders. A real user turn is a transcript row that `user_prompts.prompt_text`
reads as typed text and whose `origin` is exactly `{"kind": "human"}`; its words are `user_prompts.user_words` of
that text. Peer messages (origin kind `peer`), task notifications, tool results and compact summaries are never a
user turn.
`verified_human_turn` returns the turn's time, never its words, or raises HumanTurnRefusedError naming the failed
lookup. Standard library, `script_utils`, `session_registry` and `user_prompts` only."""
from datetime import datetime, timezone
from typing import NamedTuple

import user_prompts
from script_utils import transcript_record
from session_registry import live_session_rows, projects_dir, sessions_dir

HUMAN_ORIGIN = {"kind": "human"}


class HumanTurnRefusedError(Exception):
    """No real user turn backs the relay. The message names the failed lookup."""


class HumanTurn(NamedTuple):
    """A user turn: its ISO timestamp as the transcript wrote it, and the same moment in epoch seconds."""
    timestamp: str
    epoch: float


def session_id_of_name(session_name):
    """The session id of the one live session named `session_name`. Raises HumanTurnRefusedError for none or several."""
    matches = [row for row in live_session_rows() if row.get("name") == session_name]
    if not matches:
        raise HumanTurnRefusedError(f"no live session named {session_name!r} in {sessions_dir()}")
    if len(matches) > 1:
        raise HumanTurnRefusedError(f"{len(matches)} live sessions are named {session_name!r} in "
                                    f"{sessions_dir()}; name a session that exactly one live row holds")
    session_id = matches[0].get("sessionId")
    if not isinstance(session_id, str) or not session_id:
        raise HumanTurnRefusedError(f"the registry row of {session_name!r} holds no sessionId")
    return session_id


def transcript_of_session(session_id):
    """The one `<projects folder>/*/<session_id>.jsonl`. Raises HumanTurnRefusedError for none or several."""
    found = sorted(projects_dir().glob(f"*/{session_id}.jsonl"))
    if not found:
        raise HumanTurnRefusedError(f"no transcript {session_id}.jsonl under {projects_dir()}")
    if len(found) > 1:
        raise HumanTurnRefusedError(f"{len(found)} transcripts named {session_id}.jsonl under {projects_dir()}: "
                                    f"{', '.join(str(transcript) for transcript in found)}")
    return found[0]


def epoch_of_timestamp(timestamp):
    """Epoch seconds of an ISO 8601 timestamp such as `2026-11-15T06:22:12.305Z`. Raises ValueError for any other."""
    # Python 3.10's fromisoformat does not read a trailing Z.
    moment = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.timestamp()


def human_text(row):
    """The words the user typed in a transcript row that is a real user turn (see the module docstring), else None.
    `user_prompts.prompt_text` decides what a typed prompt is; this adds the exact human origin."""
    if row.get("origin") != HUMAN_ORIGIN:
        return None
    prompt = user_prompts.prompt_text(row)
    if prompt is None:
        return None
    return user_prompts.user_words(prompt)


def human_turns(transcript):
    """(HumanTurn, text) of each real user turn in `transcript`, in file order. A line that is not JSON, or a user
    turn with no readable timestamp, is not a turn. Raises HumanTurnRefusedError when the file cannot be read."""
    turns = []
    try:
        # A byte that is not UTF-8 is replaced: it can only spoil its own line, never hide a turn on another.
        with open(transcript, encoding="utf-8", errors="replace") as handle:
            for line in handle:
                turn = human_turn_of_line(line)
                if turn is not None:
                    turns.append(turn)
    except OSError as error:
        raise HumanTurnRefusedError(f"cannot read the transcript {transcript}: {error}") from error
    return turns


def human_turn_of_line(line):
    """(HumanTurn, text) of a transcript line that is a real user turn with a readable timestamp, else None."""
    if HUMAN_ORIGIN["kind"] not in line:
        return None
    row = transcript_record(line)
    if row is None:
        return None
    text = human_text(row)
    if text is None:
        return None
    timestamp = row.get("timestamp")
    try:
        epoch = epoch_of_timestamp(timestamp)
    except (AttributeError, ValueError):
        return None
    return HumanTurn(timestamp, epoch), text


def verified_human_turn(session_name, after_epoch):
    """The latest real user turn with text in the live session `session_name`, typed after `after_epoch`. Raises
    HumanTurnRefusedError naming the lookup that failed: no registry row, several rows, no transcript, no human
    turn, or only turns older than `after_epoch`."""
    session_id = session_id_of_name(session_name)
    transcript = transcript_of_session(session_id)
    typed = [turn for turn, text in human_turns(transcript) if text.strip()]
    if not typed:
        raise HumanTurnRefusedError(f"no human turn in session {session_name!r}")
    recent = [turn for turn in typed if turn.epoch > after_epoch]
    if not recent:
        raise HumanTurnRefusedError(f"every human turn of session {session_name!r} is older than the ask it would "
                                    "rule: ask the user there, then relay")
    return recent[-1]
