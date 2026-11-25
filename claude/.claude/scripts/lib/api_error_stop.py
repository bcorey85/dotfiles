"""api_error_stop.py: whether a Claude session's transcript ends on an API error, what kind, and when a resume
prompt can go to it.

Claude Code writes an API error as an assistant record with `isApiErrorMessage: true`. A usage limit is
`error: rate_limit` with the reset time as epoch seconds in `quotaLimits.resetsAt` (or
`apiErrorParams.rate_limit_info.resetsAt`). An overload or a lost connection is `error: server_error`. Standard
library, `script_utils` and `session_registry` only."""
import datetime

import script_utils
import session_registry

# Words in an API error record that mean the session lost its login and will not go on until someone logs in.
LOGIN_WORDS = ("/login", "401", "authentication", "oauth token")
LOGIN_EXPIRED = "login expired"
API_ERROR = "api error"
RATE_LIMIT_ERROR = "rate_limit"
SERVER_ERROR = "server_error"
# Seconds past the reset before a resume goes out, so the first request does not hit the old limit.
RESET_MARGIN_SECONDS = 60
# Seconds after an overload or a lost connection before a resume goes out.
SERVER_ERROR_WAIT_SECONDS = 300


def agent_transcript(agent):
    """The transcript path of a herdr agent's session, or None when herdr names no session or no transcript matches."""
    agent_session = agent.get("agent_session")
    session_id = agent_session.get("value") if isinstance(agent_session, dict) else None
    if not isinstance(session_id, str) or not session_id:
        return None

    found = sorted(session_registry.projects_dir().glob(f"*/{session_id}.jsonl"))
    if not found:
        return None
    return found[0]


def last_api_error(transcript):
    """The transcript's last record when it is an API error record, else None."""
    record = script_utils.last_transcript_record(transcript)
    if record is None or record.get("isApiErrorMessage") is not True:
        return None
    return record


def error_reason(record):
    """`login expired` for an API error whose text asks for a login, else `api error`. Only the text parts are read:
    the message id is a uuid that can hold `401`."""
    message = record.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    parts = content if isinstance(content, list) else []
    text = " ".join(part.get("text", "") for part in parts if isinstance(part, dict)).lower()
    if any(word in text for word in LOGIN_WORDS):
        return LOGIN_EXPIRED
    return API_ERROR


def reset_epoch(record):
    """The usage-limit reset time in epoch seconds, or None when the record carries none."""
    for limits in (record.get("quotaLimits"), (record.get("apiErrorParams") or {}).get("rate_limit_info")):
        if not isinstance(limits, dict):
            continue
        resets_at = limits.get("resetsAt")
        if isinstance(resets_at, (int, float)) and not isinstance(resets_at, bool):
            return resets_at
    return None


def record_epoch(record):
    """The record's timestamp in epoch seconds, or None when it has none or it does not parse."""
    stamp = record.get("timestamp")
    if not isinstance(stamp, str):
        return None
    try:
        moment = datetime.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment.timestamp()


def resume_epoch(record):
    """When a resume prompt can go to a session stopped on this API error, in epoch seconds. None for an error a
    prompt does not fix (a login, billing or a bad request) and for a usage limit or server error with no time."""
    if error_reason(record) == LOGIN_EXPIRED:
        return None
    error = record.get("error")
    if error == RATE_LIMIT_ERROR:
        resets_at = reset_epoch(record)
        return None if resets_at is None else resets_at + RESET_MARGIN_SECONDS
    if error == SERVER_ERROR:
        stopped_at = record_epoch(record)
        return None if stopped_at is None else stopped_at + SERVER_ERROR_WAIT_SECONDS
    return None
