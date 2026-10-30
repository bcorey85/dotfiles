#!/usr/bin/env python3
"""handback_store.py: the per-session store of review-loop rows (dispatch, dispatch-ran, hand-back, stop, step) and the
reads of it that decide whether a hand-back is current. Callers import these names from handback_store directly;
handback.py imports only the ones it uses itself. The store is one append-only JSON-lines file per session under
$HANDBACK_STORE_DIR (default ~/.claude/state/handback)."""
import os
import pathlib
import sys
import time

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / folder) for folder in (".", "../lib")]
import script_utils

STALE_STORE_SECONDS = 7 * 86400
DISPATCH_RAN = "dispatch-ran"


def store_dir():
    override = os.environ.get("HANDBACK_STORE_DIR")
    return pathlib.Path(override) if override else pathlib.Path.home() / ".claude" / "state" / "handback"


def session_file(session_id):
    suffix = ".jsonl"
    path = script_utils.state_file_path(store_dir(), session_id, suffix)
    if not path.name[:-len(suffix)].strip("._"):
        raise ValueError("session id is empty")
    return path


ANY_AGENT = object()


def settled_stop(row):
    """True for a stop row the gate did not block. A blocked stop is not a stop: the loop went on."""
    return row.get("kind") == "stop" and not row.get("blocked")


def session_rows(session_id, kind=None, agent_id=ANY_AGENT):
    """The rows of the session's file in append order, only those of `kind` and of `agent_id` when given. Raises
    ValueError for an empty session id. `agent_id=None` selects the rows that name no agent."""
    return [row for row in script_utils.read_jsonl(session_file(session_id))
            if (kind is None or row.get("kind") == kind)
            and (agent_id is ANY_AGENT or row.get("agent_id") == agent_id)]


def dispatch_ran(row, ran_calls):
    """True when the dispatch `row` counts. The dispatch hook writes its row at PreToolUse, before a sibling hook can
    deny the call, so a row that names its call (`tool_use_id`) counts only once a `dispatch-ran` row (PostToolUse,
    after the call ran) names the same call. A row with no call id (a script wrote it) counts: fail-open on purpose,
    since only the hook carries one."""
    return not row.get("tool_use_id") or row["tool_use_id"] in ran_calls


def ran_calls_of(stored_rows):
    """The call ids the `dispatch-ran` rows of `stored_rows` name."""
    return {row.get("tool_use_id") for row in stored_rows if row.get("kind") == DISPATCH_RAN}


def hand_back_dispatch_rows(session_id):
    """The dispatch rows a hand-back reads, in append order: those that ran, plus the session's last dispatch row when
    it has not run yet. A foreground loop hands back before its own call's `dispatch-ran` row lands, so its dispatch
    is that last row; a background loop's row has run by the time it hands back."""
    stored_rows = session_rows(session_id)
    ran_calls = ran_calls_of(stored_rows)
    dispatch_rows = [row for row in stored_rows if row.get("kind") == "dispatch"]

    last_index = len(dispatch_rows) - 1
    return [row for index, row in enumerate(dispatch_rows) if index == last_index or dispatch_ran(row, ran_calls)]


def was_recorded(session_id, agent_id, kind):
    """True when the session's file holds a row of this kind from this agent."""
    return bool(session_rows(session_id, kind, agent_id))


def prune_stale():
    cutoff = time.time() - STALE_STORE_SECONDS
    directory = store_dir()
    if not directory.is_dir():
        return
    for path in directory.glob("*.jsonl"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
        except OSError:
            pass


def record(session_id, kind, **fields):
    """Append one row to the session's own file. Other sessions' files are never touched."""
    row = {"kind": kind, "ts": time.time(), "session_id": session_id, **fields}
    prune_stale()
    script_utils.append_jsonl(session_file(session_id), row)
    return row


def latest(session_id):
    """{"dispatch": last review-loop dispatch row that ran (see dispatch_ran) or None, "handback": last hand-back row
    or None, "stop": the last review-loop stop row after the last dispatch or None, "unanswered": the number of
    dispatches that ran after the last hand-back (all of them when there is none), "pending": unanswered > 0}. A
    hand-back clears every dispatch before it. A dispatch that another hook denied never ran, so it blocks nothing. A
    row holds kind, ts, session_id; a dispatch row also no_review, resolved_plan_impact, repo (the top level of the
    repo it reviews, or None) and tool_use_id; a hand-back row also agent_id, status, problems, message, no_reviewer,
    unreviewed_fix; a stop row also agent_id, open_dispatches (the background agents and shells the loop still waited
    on when it stopped) and ask_rows. A stop the gate blocked is not a stop: the loop went on, so such a row is
    skipped. Rows are ordered by append, not by clock."""
    standing = {"dispatch": None, "handback": None, "stop": None, "unanswered": 0, "pending": False}
    if not session_id:
        return standing
    try:
        stored_rows = session_rows(session_id)
    except ValueError:
        return standing
    ran_calls = ran_calls_of(stored_rows)
    for row in stored_rows:
        if row.get("kind") == "dispatch":
            # Any dispatch ends the last loop's stop, run or not: a foreground loop's dispatch is proven only when
            # the loop returns, and until then an earlier stop is not this loop's.
            standing["stop"] = None
            if dispatch_ran(row, ran_calls):
                standing["dispatch"] = row
                standing["unanswered"] += 1
        elif settled_stop(row):
            standing["stop"] = row
        elif row.get("kind") == "handback":
            standing["handback"] = row
            standing["unanswered"] = 0
    standing["pending"] = standing["unanswered"] > 0
    return standing


NO_DISPATCH = "no-dispatch"
NO_HANDBACK = "no-handback"
REDISPATCHED = "redispatched"
LOOP_WAITING = "loop-waiting"


def hand_back_gap(seen):
    """Why the session has no current hand-back, from a `latest` result: NO_DISPATCH (the session never dispatched a
    review-loop), LOOP_WAITING (the loop's latest stop left a background agent or shell running, so it will resume and
    may still hand back), NO_HANDBACK (dispatched, nothing came back), REDISPATCHED (dispatched again after a
    hand-back), or None when the latest hand-back is current. The one rule that /review, /fix and the commit gate
    share."""
    if seen["dispatch"] is None:
        return NO_DISPATCH
    if seen["handback"] is not None and not seen["pending"]:
        return None
    if seen["stop"] is not None and seen["stop"].get("open_dispatches", 0) > 0:
        return LOOP_WAITING
    if seen["handback"] is None:
        return NO_HANDBACK
    return REDISPATCHED


def unreviewed_streak(session_id):
    """How many of the session's latest hand-backs in a row were clean with no reviewer run. 0 when the latest one had
    a reviewer."""
    hand_backs = session_rows(session_id, "handback")

    streak = 0
    for row in reversed(hand_backs):
        if not row.get("no_reviewer"):
            break
        streak += 1
    return streak


def ended_on_unreviewed_fix(session_id, agent_id):
    """True when the latest stored hand-back of `agent_id` was clean and its last step was a coder after a reviewer."""
    hand_backs = session_rows(session_id, "handback", agent_id)
    return bool(hand_backs) and bool(hand_backs[-1].get("unreviewed_fix"))
