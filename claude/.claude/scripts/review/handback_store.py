#!/usr/bin/env python3
"""handback_store.py: the per-session store of review-loop rows (dispatch, dispatch-ran, hand-back, stop, step,
asks-logged, plan-ruling, plan-impact-ruled, ask-rejected, ask-rejection-withdrawn, dispatch-repo,
phase-asks-open, phase-asks-ruled, ask-ruling-relayed) and the reads of it that decide whether a hand-back is current
and the open/ruled state of phase review asks (the one read that spans every session's file, by repo). Callers import
these names from handback_store directly; handback.py imports only the ones it uses itself.
The store is one append-only JSON-lines file per session under
$HANDBACK_STORE_DIR (default ~/.claude/state/handback)."""
import hashlib
import json
import os
import pathlib
import sys
import time
from typing import NamedTuple

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / folder) for folder in (".", "../lib")]
import file_lock
import reviewed_tree
import script_utils

STALE_STORE_SECONDS = 7 * 86400
# Each repo has one lock file for its phase-asks read-then-write steps, so a slow step in one repo never holds up
# another. Its name does not end in .jsonl: the store globs *.jsonl.
PHASE_ASKS_LOCK_PREFIX = "phase-asks-"
PHASE_ASKS_LOCK_SUFFIX = ".lock"
PHASE_ASKS_LOCK_TIMEOUT_SECONDS = 30
# Names a shorter wait; a test sets it.
PHASE_ASKS_LOCK_TIMEOUT_ENV = "HANDBACK_LOCK_TIMEOUT_SECONDS"
# The field of a phase-asks-ruled row that names the session that ruled; the row's session_id names the opener.
RULED_BY_KEY = "ruled_by"
DISPATCH_RAN = "dispatch-ran"
PLAN_RULING = "plan-ruling"
# The text of one plan impact a ruling settled. It never clears the gate: only PLAN_RULING does that.
PLAN_IMPACT_RULED = "plan-impact-ruled"
# The field of a PLAN_IMPACT_RULED row that holds the accepted finding's full text.
# A row from `decide` with no packet, or with no accepted finding the impact covers, has none.
RULED_FINDING_TEXT_KEY = "finding_text"
# The text (file:line and question) of one ask the session answered "rejected". Later rounds drop a repeat of it.
ASK_REJECTED = "ask-rejected"
# A correction that turned a rejected ask into an accepted one: it cancels the ASK_REJECTED row of the same text.
ASK_REJECTION_WITHDRAWN = "ask-rejection-withdrawn"
ASKS_LOGGED_ROW = "asks-logged"
# One user ruling on user-only asks that another session relayed: who relayed it, the user's quoted words and the
# timestamp of the user turn that holds them. No other transcript text is stored.
ASK_RULING_RELAYED = "ask-ruling-relayed"
# One user ruling on a held plan impact that another session relayed to `decide`, with the same fields and the
# impact's text.
PLAN_RULING_RELAYED = "plan-ruling-relayed"
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


def session_rows(session_id, kind=None, agent_id=ANY_AGENT):
    """The rows of the session's file in append order, only those of `kind` and of `agent_id` when given. Raises
    ValueError for an empty session id. `agent_id=None` selects the rows that name no agent."""
    return [row for row in script_utils.read_jsonl(session_file(session_id))
            if (kind is None or row.get("kind") == kind)
            and (agent_id is ANY_AGENT or row.get("agent_id") == agent_id)]


def ruled_rows_repo(path):
    """The key the ruled-impact and rejected-ask rows of the repo that holds `path` sit under: its work tree's top
    level, None outside a work tree. Every writer and reader of those rows takes its repo through here."""
    return script_utils.work_tree_top(path)


def record_ruled_impact(session_id, text, repo, finding_text=None):
    """Records the text of a plan impact the user or the session ruled on in `repo` (its top level), so a later fix
    run of that repo leaves a finding on it out. `finding_text` is the full text of the accepted finding the ruling
    came from, when there is one: a later fix run leaves out that exact finding and no other. Does nothing without a
    session id."""
    if not session_id:
        return None
    if finding_text is None:
        return record(session_id, PLAN_IMPACT_RULED, text=text, repo=repo)
    return record(session_id, PLAN_IMPACT_RULED, text=text, repo=repo, **{RULED_FINDING_TEXT_KEY: finding_text})


def record_relayed_plan_ruling(session_id, repo, ruler, relayed_by, quote, turn_timestamp, text):
    """Records that `ruler` (the user) ruled the plan impact `text` in `repo` through the session `relayed_by`:
    `quote` is the user's own words and `turn_timestamp` the time of the user turn that holds them. Does nothing
    without a session id."""
    if not session_id:
        return None
    return record(session_id, PLAN_RULING_RELAYED, repo=repo, ruler=ruler, relayed_by=relayed_by, quote=quote,
                  turn_ts=turn_timestamp, text=text)


class Rulings(NamedTuple):
    """What a session already ruled on in one repo: the texts of the plan impacts, and the full texts of the accepted
    findings those rulings came from. A `decide` run with no packet, or whose impact covers no accepted finding,
    stores no finding text."""
    impacts: list
    finding_texts: list


NO_RULINGS = Rulings([], [])


def rulings(session_id, repo):
    """The Rulings the PLAN_IMPACT_RULED rows of `repo` hold, in ruling order. NO_RULINGS without a session id."""
    if not session_id:
        return NO_RULINGS
    rows = [row for row in session_rows(session_id, PLAN_IMPACT_RULED) if row.get("repo") == repo]
    impacts = [row["text"] for row in rows]
    finding_texts = [row[RULED_FINDING_TEXT_KEY] for row in rows if row.get(RULED_FINDING_TEXT_KEY)]
    return Rulings(impacts, finding_texts)


def record_rejected_ask(session_id, text, repo):
    """Records the text of an ask the session answered "rejected" in `repo` (its top level), so a later round of that
    repo's review loop drops a repeat of it. Does nothing without a session id, and adds no row for a text the session
    currently holds as rejected there (a rerun after a crash)."""
    if not session_id:
        return None
    if text in rejected_ask_texts(session_id, repo):
        return None
    return record(session_id, ASK_REJECTED, text=text, repo=repo)


def record_relayed_ruling(session_id, repo, ruler, relayed_by, quote, turn_timestamp, finding_ids):
    """Records that `ruler` (the user) ruled the asks `finding_ids` in `repo` through the session `relayed_by`:
    `quote` is the user's own words and `turn_timestamp` the time of the user turn that holds them."""
    return record(session_id, ASK_RULING_RELAYED, repo=repo, ruler=ruler, relayed_by=relayed_by, quote=quote,
                  turn_ts=turn_timestamp, finding_ids=finding_ids)


def record_rejection_withdrawn(session_id, text, repo):
    """Records that the session now accepts the ask it rejected with this text in `repo`, so its repeat is no longer
    dropped. Does nothing without a session id."""
    if not session_id:
        return None
    return record(session_id, ASK_REJECTION_WITHDRAWN, text=text, repo=repo)


def rejected_ask_texts(session_id, repo):
    """The texts of the asks this session rejected in `repo` and has not since withdrawn, in the order they were
    rejected. [] without a session id."""
    if not session_id:
        return []
    texts = []
    for row in session_rows(session_id):
        if row.get("repo") != repo:
            continue
        if row.get("kind") == ASK_REJECTED:
            texts.append(row["text"])
        elif row.get("kind") == ASK_REJECTION_WITHDRAWN:
            texts = [text for text in texts if text != row["text"]]
    return texts


def plan_ruled_since(session_id, handback_row):
    """True when a plan ruling (keep, applied adopt or defer, by the user or the session) was recorded after this
    hand-back: the impacts are settled, not waiting."""
    rulings = session_rows(session_id, PLAN_RULING)
    return any(row["ts"] >= handback_row["ts"] for row in rulings)


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


def prune_stale(keep):
    """Deletes session files older than STALE_STORE_SECONDS, except `keep`, the file the caller is about to append
    to."""
    cutoff = time.time() - STALE_STORE_SECONDS
    directory = store_dir()
    if not directory.is_dir():
        return
    for path in directory.glob("*.jsonl"):
        if path == keep:
            continue
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
        except OSError:
            pass


def record(session_id, kind, **fields):
    """Append one row to `session_id`'s file. A caller may name another session's file: phase_asks.py writes a ruled
    row to the file of the session that opened the asks."""
    row = {"kind": kind, "ts": time.time(), "session_id": session_id, **fields}
    own_file = session_file(session_id)
    prune_stale(keep=own_file)
    script_utils.append_jsonl(own_file, row)
    return row


def record_handback(session_id, **fields):
    """Append a review-loop hand-back row with the tree it covered: [top level, reviewed_fingerprint] of the repo its
    dispatch reviewed, as the tree stands now, or None when the dispatch names no repo or git cannot fingerprint it.
    A plan ruling made later credits this tree, not the tree at the time of the ruling. A DISPATCH_REPO_KIND row
    after the last dispatch row replaces the dispatch row's repo."""
    dispatch = hand_back_standing(session_id)["dispatch"] or {}
    repo = dispatch.get("repo")
    tree = reviewed_tree.reviewed_fingerprint(repo) if repo else None
    return record(session_id, "handback", tree=tree, **fields)


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
    row holds kind, ts, session_id; a dispatch row also no_review, repo (the top level of the
    repo it reviews, or None; a later DISPATCH_REPO_KIND row replaces it) and tool_use_id; a hand-back row also
    agent_id, status, problems, message, no_reviewer, unreviewed_fix, tree (the [top, fingerprint] pair, or None);
    a stop row also agent_id and ask_rows. Rows are ordered by append, not by clock."""
    stored_rows = stored_session_rows(session_id)
    return standing_of(stored_rows, ran_calls_of(stored_rows))


def hand_back_standing(session_id):
    """`latest`, read at hand-back time: its dispatch is the session's last dispatch row (see hand_back_dispatch_rows)
    in place of the last one that ran, with the repo of a DISPATCH_REPO_KIND row after it."""
    seen = latest(session_id)
    dispatch_rows = hand_back_dispatch_rows(session_id)
    if not dispatch_rows:
        return seen
    dispatch = dispatch_rows[-1]
    repo_override = None
    for row in session_rows(session_id):
        if row.get("kind") == "dispatch":
            repo_override = None
        elif row.get("kind") == DISPATCH_REPO_KIND:
            repo_override = row
    if repo_override is not None:
        dispatch = {**dispatch, "repo": repo_override.get("repo")}
    return {**seen, "dispatch": dispatch}


def latest_for_repo(session_id, repo_top):
    """`latest` over only the rows of review-loops that reviewed repo_top: each dispatch whose repo, after any
    DISPATCH_REPO_KIND row, is repo_top, and the stop and hand-back rows that follow such a dispatch before the next
    dispatch. A review of another repo then neither answers nor voids this repo's hand-back. A dispatch that names no
    repo yet can be a review of this one, so it stays in and voids the hand-back before it."""
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
        is_unnamed_dispatch = row.get("kind") == "dispatch" and reviewed_repo is None
        if repo_top is None or (reviewed_repo != repo_top and not is_unnamed_dispatch):
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
        elif row.get("kind") == "stop":
            standing["stop"] = row
        elif row.get("kind") == "handback":
            standing["handback"] = row
            standing["unanswered"] = 0
    standing["pending"] = standing["unanswered"] > 0
    return standing


NO_DISPATCH = "no-dispatch"
NO_HANDBACK = "no-handback"
REDISPATCHED = "redispatched"


def hand_back_gap(seen):
    """Why the session has no current hand-back, from a `latest` result: NO_DISPATCH (the session never dispatched a
    review-loop), NO_HANDBACK (dispatched, nothing came back), REDISPATCHED (dispatched again after a
    hand-back), or None when the latest hand-back is current. The one rule that /review, /fix and the commit gate
    share."""
    if seen["dispatch"] is None:
        return NO_DISPATCH
    if seen["handback"] is not None and not seen["pending"]:
        return None
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


def record_asks_logged(session_id, packet_id, repo):
    """Notes that this packet's ask outcomes are logged in `repo`. Ask state is kept per repo, so a
    `review_fix.py packet` run from another repo reads this row instead."""
    record(session_id, ASKS_LOGGED_ROW, packet_id=packet_id, repo=repo)


def repo_that_logged_the_asks(session_id, packet_id):
    """The repo where this session logged this packet's ask outcomes, or None when none did."""
    logged_rows = session_rows(session_id, ASKS_LOGGED_ROW)
    packet_rows = [row for row in logged_rows if row.get("packet_id") == packet_id]
    return packet_rows[-1]["repo"] if packet_rows else None


# A /code phase review handed the session a packet with finding asks (the open row, which names its packets in
# `packet_keys`); the ruled row settles them. The ruled row is written to the file of the session that wrote the open
# row, so the file that holds the open row also holds its ruling, whichever session ruled.
PHASE_ASKS_OPEN = "phase-asks-open"
PHASE_ASKS_RULED = "phase-asks-ruled"
# The field of a ruled row that holds the `ts` of the open row it answered.
RULED_OPEN_TS_KEY = "open_ts"
# Both kinds start with this, so a line without it as a kind value is no phase-asks row.
PHASE_ASKS_KIND_PREFIX = "phase-asks-"


class PhaseAskRowError(Exception):
    """A phase-asks row of the store is damaged: where it is and the form it should have."""

    def __init__(self, store_file, line_number, expected):
        super().__init__(f"{store_file}:{line_number}: expected {expected}")


class PhaseAsks(NamedTuple):
    """The phase-ask state of one repo: its latest open row, and the ruled row that answered that very row (None
    while unruled). Only a newer open row of the repo replaces an open row; a newer hand-back does not."""
    open_row: dict
    ruled_row: dict | None


class PhaseAskRows(NamedTuple):
    """Every phase-asks row of one repo from every session's file, each list ordered by `ts`."""
    open_rows: list
    ruled_rows: list


def phase_ask_row_form_problem(row):
    """What the phase-asks `row` lacks, as the form it should have, or None when it is well formed."""
    if not isinstance(row.get("ts"), (int, float)) or isinstance(row.get("ts"), bool):
        return '"ts" a number'
    if row["kind"] == PHASE_ASKS_RULED:
        rulings_list = row.get("rulings")
        if not isinstance(rulings_list, list) or not all(isinstance(item, dict) for item in rulings_list):
            return f'a {PHASE_ASKS_RULED} row with "rulings" a list of objects'
        return None
    asks = row.get("asks")
    if not isinstance(asks, list) or not all(isinstance(item, dict) for item in asks):
        return f'a {PHASE_ASKS_OPEN} row with "asks" a list of objects'
    contexts = row.get("contexts")
    if not isinstance(contexts, list) or len(contexts) != len(asks):
        return f'a {PHASE_ASKS_OPEN} row with "contexts" a list, one object per ask'
    if not isinstance(row.get("packet_keys"), list):
        return f'a {PHASE_ASKS_OPEN} row with "packet_keys" a list'
    return None


def torn_line_repo(line):
    """The repo a line that is not JSON names in full (`"repo": "<path>"` with its closing quote), or None when the
    line holds no complete repo value."""
    key = '"repo": '
    key_at = line.find(key)
    if key_at == -1:
        return None
    try:
        value, _ = json.JSONDecoder().raw_decode(line[key_at + len(key):])
    except ValueError:
        return None
    return value if isinstance(value, str) else None


def phase_ask_rows_of_file(store_file, repo):
    """The open and ruled phase-asks rows of `repo` in one session file, in append order. Raises PhaseAskRowError
    for a line that names a phase-asks row of `repo` but is not JSON, or a row of `repo` that is not well formed."""
    open_rows, ruled_rows = [], []
    text = store_file.read_text(encoding="utf-8", errors="replace")
    # The serialized form json.dumps writes, so prompt text that merely names a phase-asks branch is no row.
    kind_mark = f'"kind": "{PHASE_ASKS_KIND_PREFIX}'
    for line_number, line in enumerate(text.splitlines(), 1):
        if kind_mark not in line:
            continue
        try:
            row = json.loads(line)
        except ValueError as error:
            torn_repo = torn_line_repo(line)
            if torn_repo == repo:
                raise PhaseAskRowError(store_file, line_number, "one JSON object per line") from error
            if torn_repo is None:
                sys.stderr.write(f"handback_store: skipped damaged phase-asks line {store_file}:{line_number}: "
                                 "it names no complete repo\n")
            # A line that names another repo in full is skipped silently, as script_utils.read_jsonl skips it.
            continue
        if not isinstance(row, dict) or row.get("kind") not in (PHASE_ASKS_OPEN, PHASE_ASKS_RULED):
            continue
        if row.get("repo") != repo:
            continue
        problem = phase_ask_row_form_problem(row)
        if problem:
            raise PhaseAskRowError(store_file, line_number, problem)
        (open_rows if row["kind"] == PHASE_ASKS_OPEN else ruled_rows).append(row)
    return open_rows, ruled_rows


def read_phase_ask_rows(repo):
    """The PhaseAskRows of `repo` across every session's file: a /clear, a compaction or a resume starts a session
    with a new id, and the asks stay open. A store entry that cannot be read is skipped and named on stderr; the
    rest is read. Raises PhaseAskRowError."""
    open_rows, ruled_rows = [], []
    for store_file in sorted(store_dir().glob("*.jsonl")):
        try:
            file_open, file_ruled = phase_ask_rows_of_file(store_file, repo)
        except OSError as error:
            sys.stderr.write(f"handback_store: skipped unreadable hand-back store entry {store_file}: {error}\n")
            continue
        open_rows += file_open
        ruled_rows += file_ruled
    return PhaseAskRows(sorted(open_rows, key=lambda row: row["ts"]), sorted(ruled_rows, key=lambda row: row["ts"]))


def ruled_row_of(open_row, ruled_rows):
    """The ruled row that answered `open_row`, or None. A ruled row names its open row by `ts`."""
    for ruled_row in ruled_rows:
        if ruled_row.get(RULED_OPEN_TS_KEY) == open_row["ts"]:
            return ruled_row
    return None


def ruled_packet_keys(rows):
    """The packet keys of every open row of `rows` that a ruling answered, so a packet that was ruled is not opened
    again, whichever open row came after it."""
    keys = []
    for open_row in rows.open_rows:
        if ruled_row_of(open_row, rows.ruled_rows) is not None:
            keys += open_row["packet_keys"]
    return keys


def phase_asks_lock_path(repo):
    """The lock file of `repo`'s phase-asks steps, named by a digest of the repo path."""
    digest = hashlib.sha1(repo.encode("utf-8"), usedforsecurity=False).hexdigest()[:16]
    return store_dir() / f"{PHASE_ASKS_LOCK_PREFIX}{digest}{PHASE_ASKS_LOCK_SUFFIX}"


def phase_asks_lock(repo):
    """Holds the phase-asks lock of `repo` for a `with` block, so a read of the repo's open and ruled rows and the
    write that follows it are one step across processes. Fails closed: raises file_lock.LockTimeoutError (an OSError
    naming the lock file) when the lock stays held for the timeout, and nothing in the block runs."""
    timeout_seconds = float(os.environ.get(PHASE_ASKS_LOCK_TIMEOUT_ENV) or PHASE_ASKS_LOCK_TIMEOUT_SECONDS)
    lock_path = phase_asks_lock_path(repo)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    return file_lock.hold_exclusive(lock_path, timeout_seconds)


def record_phase_asks_open(session_id, repo, asks, context, packet_key):
    """Records that the packet named by `packet_key` (its loop folder and iteration) holds these finding asks for the
    session to rule on, once per packet of `repo`. A newer hand-back of the repo from another review does not make
    the same packet new. `context` is the ask rows' run fields.
    While the latest open row is unruled, the new row carries its asks first, each with its own context, so one
    ruling settles them all; after a ruling the new row holds only the new asks. A packet that any earlier ruling
    answered adds no row. The read and the append run under phase_asks_lock. Raises what read_phase_ask_rows and
    phase_asks_lock raise."""
    with phase_asks_lock(repo):
        rows = read_phase_ask_rows(repo)
        state = phase_asks_state_of(rows)
        carried_asks, carried_contexts, packet_keys = [], [], []
        if state is not None and state.ruled_row is None:
            if packet_key in state.open_row["packet_keys"]:
                return
            carried_asks = state.open_row["asks"]
            carried_contexts = state.open_row["contexts"]
            packet_keys = state.open_row["packet_keys"]
        elif packet_key in ruled_packet_keys(rows):
            return
        record(session_id, PHASE_ASKS_OPEN, repo=repo, asks=carried_asks + asks,
               contexts=carried_contexts + [context] * len(asks), packet_keys=[*packet_keys, packet_key])


def phase_asks_state_of(rows):
    """The PhaseAsks of `rows`, or None when they hold no open row."""
    if not rows.open_rows:
        return None
    open_row = rows.open_rows[-1]
    return PhaseAsks(open_row, ruled_row_of(open_row, rows.ruled_rows))


def phase_asks_state(repo):
    """The PhaseAsks of `repo` across every session's file, or None when no open row names it (a store from before
    these rows, and a repo of None included). Raises what read_phase_ask_rows raises."""
    return phase_asks_state_of(read_phase_ask_rows(repo))


def unruled_open_rows(repo):
    """Every open row of `repo` that no ruled row answers, oldest first: the latest one and the older ones its asks
    were carried from. Raises what read_phase_ask_rows raises."""
    rows = read_phase_ask_rows(repo)
    return [open_row for open_row in rows.open_rows if ruled_row_of(open_row, rows.ruled_rows) is None]


def unruled_phase_asks(repo):
    """The open row of `repo` whose asks nobody has ruled on, else None. Raises what read_phase_ask_rows raises."""
    state = phase_asks_state(repo)
    if state is None or state.ruled_row is not None:
        return None
    return state.open_row
