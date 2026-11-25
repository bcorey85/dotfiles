"""api_error_stop.py: for an API error record (found by `script_utils.last_api_error`) its kind and when a resume
prompt can go to it.

Claude Code writes an API error as an assistant record with `isApiErrorMessage: true`. A usage limit is
`error: rate_limit` with the reset time as epoch seconds in `quotaLimits.resetsAt` (or
`apiErrorParams.rate_limit_info.resetsAt`). An overload or a lost connection is `error: server_error`. Standard
library and `script_utils` only."""
import script_utils

# Words in an API error record that mean the session lost its login and will not go on until someone logs in.
LOGIN_WORDS = ("/login", "401", "authentication", "oauth token")
LOGIN_EXPIRED = "login expired"
API_ERROR = "api error"
AUTHENTICATION_FAILED = "authentication_failed"
RATE_LIMIT_ERROR = "rate_limit"
SERVER_ERROR = "server_error"
# Seconds past the reset before a resume goes out, so the first request does not hit the old limit.
RESET_MARGIN_SECONDS = 60
# Seconds after an overload or a lost connection before a resume goes out.
SERVER_ERROR_WAIT_SECONDS = 300
# Seconds past the resume time after which a stopped session is left alone: its error is old news.
MAX_RESUME_AGE_SECONDS = 24 * 60 * 60


def error_reason(record):
    """`login expired` for an API error whose error kind is `authentication_failed` or whose text asks for a login,
    else `api error`. Only the text parts are read: the message id is a uuid that can hold `401`."""
    if record.get("error") == AUTHENTICATION_FAILED:
        return LOGIN_EXPIRED
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
        return script_utils.epoch_of_timestamp(stamp)
    except ValueError:
        return None


def resume_epoch(record, now=None):
    """When a resume prompt can go to a session stopped on this API error, in epoch seconds. None for an error a
    prompt does not fix (a login, billing or a bad request), for a usage limit or server error with no time, and,
    when `now` is given, for an error whose resume time passed more than MAX_RESUME_AGE_SECONDS ago."""
    if error_reason(record) == LOGIN_EXPIRED:
        return None
    error = record.get("error")
    resume_at = None
    if error == RATE_LIMIT_ERROR:
        resets_at = reset_epoch(record)
        resume_at = None if resets_at is None else resets_at + RESET_MARGIN_SECONDS
    elif error == SERVER_ERROR:
        stopped_at = record_epoch(record)
        resume_at = None if stopped_at is None else stopped_at + SERVER_ERROR_WAIT_SECONDS
    if resume_at is None:
        return None
    if now is not None and now > resume_at + MAX_RESUME_AGE_SECONDS:
        return None
    return resume_at
