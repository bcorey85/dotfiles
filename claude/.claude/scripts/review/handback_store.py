#!/usr/bin/env python3
"""handback_store.py: the per-session store of review-loop rows (dispatch, dispatch-ran, hand-back, stop, step,
asks-logged) and the reads of it that decide whether a hand-back is current. Callers import these names from
handback_store directly; handback.py imports only the ones it uses itself. The store is one append-only JSON-lines
file per session under $HANDBACK_STORE_DIR (default ~/.claude/state/handback)."""
import os
import pathlib
import sys
import time

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / folder) for folder in (".", "../lib")]
import script_utils

STALE_STORE_SECONDS = 7 * 86400
DISPATCH_RAN = "dispatch-ran"
ASKS_LOGGED_ROW = "asks-logged"
# A row that replaces the repo of the latest dispatch with the one its loop's ROOT= line named.
DISPATCH_REPO_KIND = "dispatch-repo"


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


def repo_of_latest_dispatch(session_id):
    """The repo the session's last review-loop dispatch reviewed, or None when the session or the dispatch names
    none."""
    last_dispatch = latest(session_id)["dispatch"] or {}
    return last_dispatch.get("repo")


def latest(session_id):
    """{"dispatch": last review-loop dispatch row that ran (see dispatch_ran) or None, "handback": last hand-back row
    or None, "stop": the last review-loop stop row after the last dispatch or None, "unanswered": the number of
    dispatches that ran after the last hand-back (all of them when there is none), "pending": unanswered > 0}. A
    hand-back clears every dispatch before it. A dispatch that another hook denied never ran, so it blocks nothing. A
    row holds kind, ts, session_id; a dispatch row also no_review, resolved_plan_impact, repo (the top level of the
    repo it reviews, or None; a later DISPATCH_REPO_KIND row replaces it) and tool_use_id; a hand-back row also
    agent_id, status, problems, message, no_reviewer, unreviewed_fix; a stop row also agent_id, open_dispatches (the
    background agents and shells the loop still waited on when it stopped) and ask_rows. A stop the gate blocked is
    not a stop: the loop went on, so such a row is skipped. Rows are ordered by append, not by clock."""
    stored_rows = stored_session_rows(session_id)
    return standing_of(stored_rows, ran_calls_of(stored_rows))


def latest_for_repo(session_id, repo_top):
    """`latest` over only the rows of review-loops that reviewed repo_top: each dispatch whose repo, after any
    DISPATCH_REPO_KIND row, is repo_top, and the stop and hand-back rows that follow such a dispatch before the next
    dispatch. A review of another repo then neither answers nor voids this repo's hand-back."""
    stored_rows = stored_session_rows(session_id)

    dispatch_repos = []
    for row in stored_rows:
        if row.get("kind") == "dispatch":
            dispatch_repos.append(row.get("repo"))
        elif row.get("kind") == DISPATCH_REPO_KIND and dispatch_repos:
            dispatch_repos[-1] = row.get("repo")

    repo_rows = []
    dispatch_count = 0
    for row in stored_rows:
        if row.get("kind") == "dispatch":
            dispatch_count += 1
        if row.get("kind") == DISPATCH_REPO_KIND or dispatch_count == 0:
            continue
        reviewed_repo = dispatch_repos[dispatch_count - 1]
        if repo_top is None or reviewed_repo != repo_top:
            continue
        repo_rows.append({**row, "repo": reviewed_repo} if row.get("kind") == "dispatch" else row)

    # A background dispatch's `dispatch-ran` row can land after a later dispatch, so the ran calls come from every row.
    return standing_of(repo_rows, ran_calls_of(stored_rows))


def stored_session_rows(session_id):
    """The session's rows, or none for an empty or unusable session id."""
    if not session_id:
        return []
    try:
        return session_rows(session_id)
    except ValueError:
        return []


def standing_of(stored_rows, ran_calls):
    """The `latest` result of these rows, read in order; ran_calls are the call ids known to have run."""
    standing = {"dispatch": None, "handback": None, "stop": None, "unanswered": 0, "pending": False}
    last_dispatch_ran = False
    for row in stored_rows:
        if row.get("kind") == "dispatch":
            # Any dispatch ends the last loop's stop, run or not: a foreground loop's dispatch is proven only when
            # the loop returns, and until then an earlier stop is not this loop's.
            standing["stop"] = None
            last_dispatch_ran = dispatch_ran(row, ran_calls)
            if last_dispatch_ran:
                standing["dispatch"] = row
                standing["unanswered"] += 1
        elif row.get("kind") == DISPATCH_REPO_KIND and last_dispatch_ran:
            standing["dispatch"] = {**standing["dispatch"], "repo": row.get("repo")}
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


def hand_back_id(stored_row, session_id):
    """The run id of a stored hand-back row; `none:<session>` when the session has no hand-back yet, so sessions in
    one repo never share a miss count."""
    if stored_row is None:
        return f"none:{session_id}"
    return f"handback:{stored_row.get('agent_id')}:{stored_row.get('ts')}"


def agent_hand_back_id(session_id, agent_id):
    """The run id of the agent's latest stored hand-back, or None when it stored none."""
    hand_backs = session_rows(session_id, "handback", agent_id)
    return hand_back_id(hand_backs[-1], session_id) if hand_backs else None


def record_asks_logged(session_id, packet_id, repo):
    """Notes that this packet's ask outcomes are logged in `repo`. Ask state is kept per repo, so a
    `review_fix.py packet` run from another repo reads this row instead."""
    record(session_id, ASKS_LOGGED_ROW, packet_id=packet_id, repo=repo)


def repo_that_logged_the_asks(session_id, packet_id):
    """The repo where this session logged this packet's ask outcomes, or None when none did."""
    logged_rows = session_rows(session_id, ASKS_LOGGED_ROW)
    packet_rows = [row for row in logged_rows if row.get("packet_id") == packet_id]
    return packet_rows[-1]["repo"] if packet_rows else None
