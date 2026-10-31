#!/usr/bin/env python3
"""saved_handback.py: the lookup of this session's saved review-loop hand-back for review_fix.py. It reads the stored
rows through handback_store.py and the open /code run through code_step_core, and decides whether the hand-back is the
session's to take, a miss, or a wait."""
import hashlib
import os
import pathlib
import sys

SIBLING_FOLDERS = (".", "../lib", "../code", "../telemetry")
sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / folder) for folder in SIBLING_FOLDERS]
import code_step_core
import code_step_store
import handback_store
from code_step_routes import STAGE_FACTS, StageFact
from code_step_state import StateFileError
from handback import PacketError


class NoHandbackError(Exception):
    """The review-loop was dispatched and ended without calling SubagentHandback."""
    def __init__(self, last_hand_back_id):
        super().__init__("dispatched, no hand-back since " + last_hand_back_id)
        self.last_hand_back_id = last_hand_back_id


class LoopWaitingError(Exception):
    """The review-loop stopped its turn while an agent or shell it started in the background still runs. `stop_ts` is
    the time of the stop row that showed it."""
    def __init__(self, stop_ts):
        super().__init__(f"waiting since {stop_ts}")
        self.stop_ts = stop_ts


def code_run_at_review(session_id):
    """(state, events) of a /code run of this session at a stage that owns review hand-backs, else None. A run pinned
    to a different session does not count."""
    try:
        code_step = code_step_core.load_state(".")
    except StateFileError:
        return None
    if code_step is None or StageFact.CODE_AGENT_OUT not in STAGE_FACTS[code_step.stage]:
        return None
    if code_step.session_id != session_id:
        return None
    events = code_step_core.read_events(".", code_step.run_id) if code_step.run_id else []
    return code_step, events


def code_step_owner(code_step):
    return code_step_store.state_file("."), code_step.stage


def active_code_step(session_id, hand_back_agent_id):
    """(state path, stage) of a /code run that owns this session's review hand-backs, else None. The run owns only
    the hand-back of an agent it launched, so a hand-back from another review-loop agent (a standalone /review while
    the run is paused or before its launch is logged) is not the run's."""
    code_run = code_run_at_review(session_id)
    if code_run is None:
        return None

    code_step, events = code_run
    launched_agent_ids = {event.get("agent_id") for event in events if event.get("event") == "launch"}
    if not hand_back_agent_id or hand_back_agent_id not in launched_agent_ids:
        return None
    return code_step_owner(code_step)


def code_step_pending_review(session_id, stored_row):
    """(state path, stage) of a /code run that dispatched a review-loop after the stored hand-back (or at all, when
    there is none), else None: the pending dispatch is the run's, so its retry goes through the run."""
    code_run = code_run_at_review(session_id)
    if code_run is None:
        return None

    code_step, events = code_run
    since = stored_row.get("ts", 0) if stored_row else 0
    run_review_dispatches = [event for event in events if event.get("event") == "dispatch"
                             and event.get("agent_type") == "review-loop" and event.get("ts", 0) > since]
    if not run_review_dispatches:
        return None
    return code_step_owner(code_step)


def saved_hand_back(session_id):
    """The latest review-loop hand-back row of this session. Raises NoHandbackError when the loop was dispatched and
    never handed back, and LoopWaitingError when it stopped to wait on a background agent or shell."""
    if not session_id:
        raise PacketError(["the packet on stdin is empty and CLAUDE_CODE_SESSION_ID is not set, so no saved "
                           "hand-back can be looked up"])
    seen = handback_store.latest(session_id)
    gap = handback_store.hand_back_gap(seen)
    stored_row = seen["handback"] or {}
    # A pending dispatch (waiting, never handed back, or re-dispatched) is newer than any stored hand-back, so the
    # stored hand-back's owner is not the answer: the run owns it only when the run dispatched it.
    if gap in (handback_store.LOOP_WAITING, handback_store.NO_HANDBACK, handback_store.REDISPATCHED):
        code_step = code_step_pending_review(session_id, seen["handback"])
    else:
        code_step = active_code_step(session_id, stored_row.get("agent_id"))
    if code_step:
        raise PacketError([f"a /code run owns this session's review hand-backs (code-step state {code_step[0]}, stage "
                           f"{code_step[1]}): its packet goes through code_step.py resume, not `packet`"])

    if gap == handback_store.LOOP_WAITING:
        raise LoopWaitingError(seen["stop"]["ts"])
    if gap in (handback_store.NO_HANDBACK, handback_store.REDISPATCHED):
        raise NoHandbackError(handback_store.hand_back_id(seen["handback"], session_id))
    if gap == handback_store.NO_DISPATCH:
        raise PacketError([f"this session has no review-loop dispatch on record (session {session_id}): a hand-back "
                           "from another session or an older run is never taken as current"])
    return seen["handback"]


def read_message():
    """(packet text, run id, how many hand-backs in a row ended clean with no reviewer run, this one included,
    whether a coder ran after the loop's last reviewer). A saved hand-back is one run per stored row (agent id and
    time), so two dispatches that return the same text are two runs. A packet on stdin has no row: its text hash is
    the run id."""
    stdin_text = "" if sys.stdin.isatty() else sys.stdin.read()
    if stdin_text.strip():
        return stdin_text, "stdin:" + hashlib.sha1(stdin_text.encode("utf-8")).hexdigest(), 0, False
    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    stored_row = saved_hand_back(session_id)
    unreviewed_in_a_row = handback_store.unreviewed_streak(session_id)
    unreviewed_fix = handback_store.ended_on_unreviewed_fix(session_id, stored_row.get("agent_id"))
    packet_id = handback_store.hand_back_id(stored_row, session_id)
    return stored_row["message"], packet_id, unreviewed_in_a_row, unreviewed_fix


def dispatched_repo():
    """The repo this session's last review-loop dispatch reviewed, or None when the session or the dispatch names
    none (a packet on stdin with no dispatch on record)."""
    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    if not session_id:
        return None

    return handback_store.repo_of_latest_dispatch(session_id)


def dispatched_with_ruling():
    """Whether this session's last review-loop dispatch carried a resolved plan_impact line, as a re-dispatch after
    a ruling does. A packet on stdin with no dispatch on record never does."""
    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    if not session_id:
        return False

    last_dispatch = handback_store.latest(session_id)["dispatch"] or {}
    return bool(last_dispatch.get("resolved_plan_impact"))
