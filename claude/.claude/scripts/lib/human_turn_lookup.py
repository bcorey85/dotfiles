"""human_turn_lookup.py: finds a turn the user typed into another live Claude Code session.

A session id, or a session name that one live row holds, maps to one live row in the sessions folder (`<pid>.json`,
fields `name`, `sessionId`); its transcript is the one `<sessionId>.jsonl` in a folder under the projects folder
(the folder need not match the row's cwd); `session_registry` owns both folders. A real user turn is a transcript
row that `user_prompts.prompt_text` reads as typed text and whose `origin` is exactly `{"kind": "human"}`; its words
are `user_prompts.user_words` of that text. Peer messages (origin kind `peer`), task notifications, tool results and
compact summaries are never a user turn.
`verified_human_turn` returns the relaying session and the turn's time, never its words, or raises
HumanTurnRefusedError naming the failed lookup. Standard library, `script_utils`, `session_registry`,
`transcript_time` and `user_prompts` only."""
from typing import NamedTuple

import user_prompts
from script_utils import transcript_record
from session_registry import live_session_rows, projects_dir, row_for_session_id, session_transcripts, sessions_dir
from transcript_time import epoch_of_timestamp

HUMAN_ORIGIN = {"kind": "human"}


class HumanTurnRefusedError(Exception):
    """No real user turn backs the relay. The message names the failed lookup."""


class HumanTurn(NamedTuple):
    """A user turn: its ISO timestamp as the transcript wrote it, and the same moment in epoch seconds."""
    timestamp: str
    epoch: float


class RelayingSession(NamedTuple):
    """The live session that relays a ruling: its session id and the name its registry row holds."""
    session_id: str
    name: str


def relaying_row(word):
    """The RelayingSession that `word` names: the live row whose session id is `word`, else the one live row named
    `word`. Raises HumanTurnRefusedError for a row with no name, for none, or for several rows of one name."""
    id_row = row_for_session_id(word)
    if id_row is not None:
        name = id_row.get("name")
        if not isinstance(name, str) or not name:
            raise HumanTurnRefusedError(f"the live row of session id {word} holds no name; name the session, "
                                        "then relay")
        return RelayingSession(word, name)
    matches = [row for row in live_session_rows() if row.get("name") == word]
    if not matches:
        raise HumanTurnRefusedError(f"no live session has the id or the name {word!r} in {sessions_dir()}")
    if len(matches) > 1:
        raise HumanTurnRefusedError(f"{len(matches)} live sessions are named {word!r} in {sessions_dir()}; relay "
                                    "by the session id of one of them instead: --relayed-by <sessionId>")
    session_id = matches[0].get("sessionId")
    if not isinstance(session_id, str) or not session_id:
        raise HumanTurnRefusedError(f"the registry row of {word!r} holds no sessionId")
    return RelayingSession(session_id, word)


def transcript_of_session(session_id):
    """The one `<projects folder>/*/<session_id>.jsonl`. Raises HumanTurnRefusedError for none or several."""
    found = session_transcripts(session_id)
    if not found:
        raise HumanTurnRefusedError(f"no transcript {session_id}.jsonl under {projects_dir()}")
    if len(found) > 1:
        raise HumanTurnRefusedError(f"{len(found)} transcripts named {session_id}.jsonl under {projects_dir()}: "
                                    f"{', '.join(str(transcript) for transcript in found)}")
    return found[0]


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


def verified_human_turn(word, after_epoch):
    """(RelayingSession, HumanTurn): the session `word` names (a live session id or name) and its latest real user
    turn with text, typed after `after_epoch`. Raises HumanTurnRefusedError naming the lookup that failed: no
    registry row, several rows, a live id row with no name, no transcript, no human turn, or only turns older than
    `after_epoch`."""
    session = relaying_row(word)
    transcript = transcript_of_session(session.session_id)
    typed = [turn for turn, text in human_turns(transcript) if text.strip()]
    if not typed:
        raise HumanTurnRefusedError(f"no human turn in session {session.name!r}")
    recent = [turn for turn in typed if turn.epoch > after_epoch]
    if not recent:
        raise HumanTurnRefusedError(f"every human turn of session {session.name!r} is older than the ask it would "
                                    "rule: ask the user there, then relay")
    return session, recent[-1]
