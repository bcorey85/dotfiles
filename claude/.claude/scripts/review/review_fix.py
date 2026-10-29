#!/usr/bin/env python3
"""review_fix.py: the fixed steps of /review and /fix as a script. The main session dispatches review-loop, runs
`packet`, and does exactly what the ACTION lines say. The script reads the packet through handback.py, routes on status,
renders the packet, logs the rows, posts the Aikido replies, and prints what the model still judges.

  review_fix.py packet --skill review|fix [options] [< packet]
      --scope branch-exit|standalone   scope of the ask rows (review passes branch-exit when it dispatched with base=)
      --lane <lane>  lane of the ask and escape rows (default none for review, code for fix); `ledger registry` lists
                     the allowed values
      --source conversation|cc|handoff (fix) where the findings came from; escapes log only for conversation
      --escape "file=<p>|class=<c>|severity=<s>|gate_missed=<g>|guard=<r>|desc=<one line>"   (fix, repeatable)
      --aikido "<path>:<line>=<comment_id>"                                                 (fix, repeatable)
      With empty stdin, `packet` reads this session's latest review-loop hand-back, which handback.py's hook stored,
      and refuses when the session has no dispatch on record. When the loop ended without handing back, it prints
      `ACTION: stop-no-handback` and leaves the saved state alone: re-dispatch once, then stop and show the user the
      loop's final text on a second miss. When the loop's latest stop left a background agent or shell running (the
      stop row review_loop_gate.py stores), it prints `ACTION: wait-for-loop` and exits 3: do not re-dispatch, end the
      turn, and run `packet` again when the review-loop's completion notice arrives. That counts no miss. A second
      `packet` on the same stop row (saved per skill in <git dir>/review-fix/waits.json) prints `ACTION: stop`
      and exits 2: show the user, do not re-dispatch. A new stop row waits again.
      A re-run on the same hand-back (the same stored row; the same text, for a packet on stdin) repeats no side
      effect: posted replies, logged escapes and the nvim-jump are kept in the state. Two dispatches that return the
      same text are two runs.
  review_fix.py escape --escape "..."...   log escape rows from the saved packet state (fix, repeatable)
  review_fix.py asks-done [--by <user|session>] [--packet <packet_id>] <outcome>...
                                         one outcome per ask, in order: accepted | rejected | modified, optional
                                         ":<one line note>" after it, accepted and not stored. Logs one row per ask,
                                         once. --by session when the session ruled on the asks itself; default user.
                                         Answers one packet. When a second packet handed back before the first one's
                                         asks were answered, both wait: asks-done then refuses and lists them, and
                                         --packet <packet_id> names the one the outcomes belong to.
  review_fix.py decide <adopt|keep> --by <user|session> --ruling "<the decision in one line>" [--plan <path>]
                                         Only --by user is the user's own word.
  review_fix.py decide discuss          print the decide commands for a plan-impact ruling and record nothing.

State lives in <git dir>/review-fix/state.json. A packet that does not parse stops with exit 2 and an instruction to
mark the gate dirty. Env REVIEW_FIX_CLAUDE_DIR overrides the toolkit folder; REVIEW_FIX_NVIM_JUMP and REVIEW_FIX_GH
override the nvim-jump and gh commands; HANDBACK_STORE_DIR overrides the hand-back store;
CLAUDE_CODE_SESSION_ID names the session."""
import argparse
import datetime
import hashlib
import json
import os
import pathlib
import re
import sys
import time

SIBLING_FOLDERS = (".", "../lib", "../code", "../telemetry")
sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / folder) for folder in SIBLING_FOLDERS]
import code_step_core
import handback
import plan_format
import script_utils
from handback import PacketError, is_plan_impact_ask, item_text
from script_utils import one_line, run_command, split_location

CLAUDE_DIR = pathlib.Path(os.environ.get("REVIEW_FIX_CLAUDE_DIR", pathlib.Path(__file__).resolve().parents[2]))
SOURCES = ["conversation", "cc", "handoff"]
ASK_OUTCOMES = ["accepted", "rejected", "modified"]
PLAN_IMPACT_OPTIONS = ["Adopt plan change", "Keep plan as written", "Discuss"]
DECISION_WORDS = {"adopt": PLAN_IMPACT_OPTIONS[0], "keep": PLAN_IMPACT_OPTIONS[1], "discuss": PLAN_IMPACT_OPTIONS[2]}
DECIDE_SCRIPT = "python3 ~/.claude/scripts/review/review_fix.py"
PLAN_ARG_NOTE = "--plan <the plan path, when the handoff names one>"
DECIDE_USAGE = f'decide <adopt|keep> --by <user|session> --ruling "<the decision in one line>" {PLAN_ARG_NOTE}'
DECIDE_BY_NOTE = ("If the user told you to make the call yourself, or you rule without asking, pass `--by session` in "
                  "place of `--by user`. A session ruling never changes the acceptance criteria.")
MARK_CLEAN = "~/.claude/scripts/review/review-gate-mark clean"
MARK_DIRTY = "~/.claude/scripts/review/review-gate-mark dirty"
KEEP_DIRTY = f"If you ran `{MARK_CLEAN}` alongside this call, run `{MARK_DIRTY}` now as its own Bash command."
NOTHING_OUTSTANDING = "No issues found that warrant auto-fix. Ready for `/commit`."
LOGGED_HEADING = "LOGGED / POSTED (mention failures, never block on them):"
FINISHED_STAGES = ("done", "redispatch")
PLAN_IMPACT = "plan-impact"
NEW_FINDING_ID = "new-finding-id"
# Exit code of `wait-for-loop`: non-zero so no caller reads it as a finished run, and not 2, the code of a real stop.
WAIT_EXIT_CODE = 3


class UsageError(Exception):
    pass


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


# ---------- shell helpers ----------

def review_fix_dir():
    found = script_utils.git_output(".", "rev-parse", "--path-format=absolute", "--git-path", "review-fix")
    if found is None:
        raise UsageError("not inside a git repo")
    return pathlib.Path(found)


def state_file():
    return review_fix_dir() / "state.json"


def read_state():
    """The saved state, or None when there is none or it is unreadable."""
    path = state_file()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except ValueError:
        return None


def load_fix_state():
    state = read_state()
    if state is not None:
        return state
    path = state_file()
    if path.exists():
        raise UsageError(f"{path} is not readable JSON")
    raise UsageError(f"no packet was processed in {path.parent} (the state is kept per repo, and this call ran in "
                     f"{pathlib.Path.cwd()}). If `packet` ran in another repo, run this call there; if it ran "
                     "in none, run `packet` first.")


def save_fix_state(state):
    path = state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=1))


# ---------- options ----------

def parse_escape(spec):
    fields = {}
    for part in spec.split("|"):
        name, separator, value = part.partition("=")
        if not separator:
            raise UsageError(f"--escape part {part!r} is not key=value (separate parts with |)")
        fields[name.strip()] = value.strip()
    missing = [name for name in ("file", "class", "severity", "gate_missed", "guard", "desc") if not fields.get(name)]
    if missing:
        raise UsageError(f"--escape {spec!r} lacks {', '.join(missing)}")
    extra = sorted(set(fields) - {"file", "class", "severity", "gate_missed", "guard", "desc", "lane"})
    if extra:
        raise UsageError(f"--escape has unknown keys: {', '.join(extra)}")
    return fields


def parse_aikido(spec):
    target, separator, comment_id = spec.rpartition("=")
    path, line = split_location(target)
    if not separator or not path or not line or not comment_id.strip().isdigit():
        raise UsageError(f"--aikido {spec!r} is not <path>:<line>=<numeric comment id>")
    return {"path": path, "line": line, "comment_id": comment_id.strip()}


def argument_parser(name):
    parser = argparse.ArgumentParser(prog=f"review_fix.py {name}", add_help=False)
    parser.error = lambda message: (_ for _ in ()).throw(UsageError(message))
    return parser


def packet_arguments(argv):
    parser = argument_parser("packet")
    parser.add_argument("--skill", required=True, choices=["review", "fix"])
    parser.add_argument("--scope", default="standalone", choices=["branch-exit", "standalone"])
    parser.add_argument("--lane")
    parser.add_argument("--source", default="handoff", choices=SOURCES)
    parser.add_argument("--escape", action="append", default=[])
    parser.add_argument("--aikido", action="append", default=[])
    options = parser.parse_args(argv)
    options.lane = options.lane or ("code" if options.skill == "fix" else "none")
    options.escapes = [parse_escape(spec) for spec in options.escape]
    options.aikido_targets = [parse_aikido(spec) for spec in options.aikido]
    if options.skill == "review" and (options.escapes or options.aikido_targets):
        raise UsageError("--escape and --aikido belong to /fix only")
    return options


# ---------- actions ----------

def is_outstanding(packet):
    return any(packet[key] for key in ("fixed", "ask", "skipped_fp", "nit", "findings_remaining"))


def print_user_block(text):
    print("-----BEGIN USER TEXT (paste verbatim)-----")
    print(text)
    print("-----END USER TEXT-----")


def print_action(action, *lines):
    print(f"ACTION: {action}")
    for line in lines:
        print(line)


def stop_for_parse_failure(error, raw_message):
    print_action("stop-parse-failure",
                 "The review-loop packet did not parse. Nothing was routed, logged or posted.",
                 *[f"- {problem}" for problem in error.problems],
                 KEEP_DIRTY,
                 "Then show the user the raw packet and the problems above. Do not guess the missing fields.",
                 "Do not re-dispatch to repair the packet unless the user asks.")
    print("RAW PACKET (first 1500 chars):")
    print(raw_message[:1500])


def update_skill_file(name, skill, update):
    """Run `update(saved entry of this caller or None)` on <name> in the review-fix dir. It returns (the entry to save,
    the result). The file is written only when the entry changed. Returns the result."""
    path = review_fix_dir() / name
    try:
        saved = json.loads(path.read_text())
    except (OSError, ValueError):
        saved = {}
    entry, result = update(saved.get(skill))
    if saved.get(skill) != entry:
        saved[skill] = entry
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(saved))
    return result


def count_hand_back_miss(skill, last_hand_back_id):
    """Misses of this caller since the session's last hand-back. /review and /fix each keep their own count; a new
    hand-back starts it again."""
    def count_miss(entry):
        entry = entry or {}
        count = (entry.get("count", 0) if entry.get("since") == last_hand_back_id else 0) + 1
        return {"since": last_hand_back_id, "count": count}, count

    return update_skill_file("misses.json", skill, count_miss)


def stop_for_missing_hand_back(skill, last_hand_back_id):
    """The loop ended without calling SubagentHandback. The saved stage of any earlier run is left alone."""
    misses = count_hand_back_miss(skill, last_hand_back_id)
    if misses < 2:
        print_action("stop-no-handback",
                     "The review-loop ended without calling SubagentHandback, so no packet is stored. Nothing was "
                     "routed, logged or posted, and the earlier run's state is untouched.",
                     "Re-dispatch review-loop once with the same arguments, then run `packet` again.",
                     KEEP_DIRTY)
        return
    print_action("stop-no-handback",
                 f"The review-loop ended {misses} times in a row without calling SubagentHandback. Nothing was routed, "
                 "logged or posted, and the earlier run's state is untouched.",
                 "Stop. Do not re-dispatch again. Show the user the loop's final text as it returned.",
                 KEEP_DIRTY)


def waited_on_stop(skill, stop_ts):
    """True when this caller already got `wait-for-loop` for the stop row at `stop_ts`; otherwise records it. A new
    stop row has a new ts, so it waits again."""
    return update_skill_file("waits.json", skill, lambda waited_ts: (stop_ts, waited_ts == stop_ts))


def wait_for_loop(skill, stop_ts):
    """The loop stopped while a background agent or shell it started still runs; the harness resumes it when that work
    reports. No miss is counted and no packet state is saved. A second `packet` on the same stop row stops: the work
    has not reported, and the wait must not go on unbounded."""
    if waited_on_stop(skill, stop_ts):
        print_action("stop",
                     f"The review-loop has been waiting since {time.strftime('%H:%M:%S', time.localtime(stop_ts))} "
                     "on an agent or shell it started in the background and has not handed back. Nothing was routed, "
                     "logged or posted.",
                     "Show the user this. Do not re-dispatch review-loop: a second loop would edit the same files as "
                     "the first.")
        return 2
    print_action("wait-for-loop",
                 "The review-loop is waiting on an agent or shell it started in the background. Nothing was routed, "
                 "logged or posted.",
                 "Do not re-dispatch review-loop: a second loop would edit the same files as the first.",
                 "End your turn. Run `packet` again when the review-loop's completion notice arrives.")
    return WAIT_EXIT_CODE


def stop_for_unreviewed(skill, packet, unreviewed_in_a_row):
    """The loop handed back clean with no reviewer run. The first time, the caller re-dispatches it at the same round
    count; the second time in a row, it stops."""
    if unreviewed_in_a_row < 2:
        lines = ("The review-loop handed back clean but dispatched no reviewer. Nothing was routed, logged or posted.",
                 f"Re-dispatch review-loop once with the same arguments plus the line below, in place of any "
                 f"`iter=` line, then run `packet --skill {skill}` again. Do not mark the gate clean.",
                 f"iter={packet['iter']}")
    else:
        lines = (f"The review-loop handed back clean with no reviewer run {unreviewed_in_a_row} times in a row. "
                 "Nothing was routed, logged or posted.",
                 "Stop. Do not re-dispatch again. Tell the user no reviewer ran, so the gate stays dirty.")
    print_action("stop-no-reviewer", *lines, KEEP_DIRTY)
    return 2


def present_plan_impact(packet, state):
    state.update({"stage": "plan-impact", "plan_impact": packet["plan_impact"],
                  "carried_findings": handback.carried_findings(packet)})
    if not plan_format.changes_acceptance_criteria(packet["plan_impact"]):
        print("The plan impact changes no acceptance criterion, so the plan follows the code. No question to the user.")
        return record_plan_ruling(state, "adopt", "session", plan_format.BELOW_CRITERIA_RULING, None)

    save_fix_state(state)
    print_action(
        "ask-user-plan-impact",
        "Call AskUserQuestion now. Without that tool, ask the same question in plain text, list the options numbered, "
        "end the turn and wait for the reply. Do not re-dispatch and do not triage this as an ask. Question: assumed, "
        "then found, then what changes, taken from this block:",
        packet["plan_impact"],
        f"Options, in this order: {' / '.join(PLAN_IMPACT_OPTIONS)}.",
        "Map the answer, picked or typed, to adopt, keep or discuss. For adopt or keep, put the user's words in "
        "--ruling; for discuss, run `decide discuss`.",
        f'Then run: {DECIDE_SCRIPT} decide <adopt|keep> --by user --ruling "<the decision in one line>" '
        f"{PLAN_ARG_NOTE}",
        DECIDE_BY_NOTE,
        f"Counters held for the re-dispatch: iter={packet['iter']} "
        f"spec_iter={packet['spec_iter'] if packet['spec_iter'] is not None else 'absent'}",
    )


def run_nvim_jump(asks):
    command = os.environ.get("REVIEW_FIX_NVIM_JUMP", "nvim-jump")
    arguments = []
    for item in asks:
        if not item.get("file_line"):
            continue
        path, line = split_location(item["file_line"])
        arguments += ["--note", one_line(item["question"], 160), f"{path}:{line}" if line else path]
    if not arguments:
        return "no ask names a file:line: nothing to jump to."
    code, output = run_command([command, *arguments])
    if code == 2 or code == 127:
        return "nvim-jump is not installed: skip jumping."
    if code == 1:
        return "no nvim owns this directory: anchors printed only."
    return "jumped to the first ask: ]k and [k step the rest." if code == 0 else f"nvim-jump exit {code}: {output}"


def gate_mark_line():
    return f"Gate: `{MARK_CLEAN}` as its own Bash command, unless it already ran in parallel with this call."


def save_packet_asks(packet, state):
    """Run nvim-jump once, save the packet's asks with stage `asks`, and return them."""
    asks = packet["ask"]
    if "jumped" not in state:
        state["jumped"] = run_nvim_jump(asks)
    state.update({"stage": "asks", "asks": asks})
    save_fix_state(state)
    return asks


def jumped_line(state):
    return f"The script ran nvim-jump for all asks ({state['jumped']}). Do not run it again."


def asks_done_line(asks, state):
    """The asks-done command for the packet in `state`. It names --packet when another packet still waits, so the
    command runs as printed."""
    packet_flag = f"--packet {state['packet_id']} " if state.get("waiting_packets") else ""
    return (f"After the user answers, run once: python3 ~/.claude/scripts/review/review_fix.py asks-done "
            f"{packet_flag}<outcome> x{len(asks)}  (accepted: make the proposed change | rejected: leave the code as "
            "it stands | modified: make the user's change instead; optional ':<one line note>', accepted and not "
            "stored)")


def ask_listing_lines(asks):
    lines = []
    for number, item in enumerate(asks, 1):
        ask_class = item["class"] + (f" (was {item['class_raw']})" if item.get("class_raw") else "")
        lines.append(f"{number}. {item.get('file_line') or 'no file:line'}  [{item['gate']}/{ask_class}]")
        lines.append(f"   {item['question']}")
        if item.get("change"):
            lines.append(f"   Proposed change: {item['change']}")
    return lines


def present_packet_asks(packet, state):
    asks = save_packet_asks(packet, state)
    lines = [
        jumped_line(state),
        "Present each ask below with its question and its proposed change, and wait for the user's direction. "
        "Never auto-fix an ask. If the repo's CLAUDE.md hands ask decisions to the session, decide each ask "
        "yourself and add `--by session` to asks-done; otherwise wait for the user.",
        asks_done_line(asks, state),
        gate_mark_line(),
        *ask_listing_lines(asks),
    ]
    print_action("present-asks", *lines)


def log_escapes(state, escapes, lane):
    """Escape rows from the saved packet state. A file that was logged already is skipped."""
    if not escapes:
        return []
    if state.get("source") != "conversation":
        return [f"escape rows skipped: findings came from {state.get('source')}, not the conversation."]
    if state.get("status") not in handback.CLEAN_STATUSES:
        return [f"escape rows skipped: the packet status was {state.get('status')}, so no fix was applied."]
    notes = []
    logged = state.setdefault("escapes_logged", [])
    for fields in escapes:
        file = script_utils.normalize_path(fields["file"])
        if file in logged:
            notes.append(f"escape for {file} already logged: skipped.")
            continue
        if file not in state.get("fixed_paths", []):
            notes.append(f"escape for {file} not logged: no fixed[] entry names that file (not applied).")
            continue
        repo = script_utils.repo_name(".")
        code, output = run_command(["bash", str(CLAUDE_DIR / "scripts/telemetry/log-escape"), f"repo={repo}",
                                    "stage_found=walkthrough", f"gate_missed={fields['gate_missed']}",
                                    f"class={fields['class']}", f"severity={fields['severity']}",
                                    f"lane={fields.get('lane') or lane}", f"guard={fields['guard']}",
                                    f"desc={one_line(fields['desc'])}", f"file={file}"])
        if code == 0:
            logged.append(file)
            notes.append(f"escape logged for {file} (guard={fields['guard']})")
        else:
            notes.append(f"escape log FAILED for {file}: {output}. Mention it and continue.")
    save_fix_state(state)
    return notes


def aikido_reply(target, packet):
    where = (script_utils.normalize_path(target["path"]), target["line"])
    named = f"{where[0]}:{where[1]}"
    for item in packet["fixed"]:
        if where in handback.entry_locations(item):
            return f"Fixed — {one_line(item.get('finding', ''), 160)}"
    for item in packet["skipped_fp"]:
        if named in item_text(item, "item", "finding", "file_line") or where in handback.entry_locations(item):
            return f"@AikidoSec ignore: {one_line(item.get('reason', 'no reason given'), 200)}"
    for item in packet["findings_remaining"] + packet["ask"]:
        if where in handback.entry_locations(item):
            reason = item.get("question") or item.get("finding") or "open"
            return f"Not fixed in this pass: {packet['status']} — {one_line(reason, 160)}"
    return f"Not fixed in this pass: {packet['status']} — no matching entry in the packet"


def post_aikido_replies(packet, targets, state):
    """(reply lines for the user text, failure notes). A comment id that got a reply is never posted to again."""
    if not targets:
        return [], []
    posted = state.setdefault("aikido_posted", {})
    pending = [target for target in targets if target["comment_id"] not in posted]
    lines = [
        f"- {posted[target['comment_id']]} (already posted)" for target in targets if target["comment_id"] in posted
    ]
    if not pending:
        return lines, []
    gh = os.environ.get("REVIEW_FIX_GH", "gh")
    code_repo, repo_slug = run_command([gh, "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"])
    code_pr, pr_number = run_command([gh, "pr", "view", "--json", "number", "--jq", ".number"])
    if code_repo != 0 or code_pr != 0:
        return lines, [
            "Aikido replies NOT posted: gh could not name the repo or PR "
            f"({one_line(repo_slug + ' ' + pr_number, 160)}). "
            "Report it and continue."
        ]
    failures = []
    for target in pending:
        reply = aikido_reply(target, packet)
        code, output = run_command([gh, "api", "--method", "POST",
                                    f"repos/{repo_slug}/pulls/{pr_number}/comments/{target['comment_id']}/replies",
                                    "-f", f"body={reply}"])
        where = f"{target['path']}:{target['line']}"
        if code == 0:
            posted[target["comment_id"]] = f"{where}: {reply}"
            lines.append(f"- {where}: {reply}")
        else:
            failures.append(f"{where} reply FAILED: {one_line(output, 160)}")
    save_fix_state(state)
    return lines, failures


# ---------- the packet ----------

def code_run_at_review(session_id):
    """(state, events) of a /code run of this session at a stage that owns review hand-backs, else None. A run pinned
    to a different session does not count."""
    try:
        code_step = code_step_core.load_state(".")
    except code_step_core.StateFileError:
        return None
    if code_step is None or code_step.get("stage") not in code_step_core.REVIEW_HANDBACK_STAGES:
        return None
    if code_step.get("sessionId") != session_id:
        return None
    events = code_step_core.read_events(".", code_step.get("runId")) if code_step.get("runId") else []
    return code_step, events


def code_step_owner(code_step):
    return code_step_core.state_dir(".") / "state.json", code_step["stage"]


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


def hand_back_id(stored_row, session_id):
    """The run id of a stored hand-back row; `none:<session>` when the session has no hand-back yet, so sessions in
    one repo never share a miss count."""
    if stored_row is None:
        return f"none:{session_id}"
    return f"handback:{stored_row.get('agent_id')}:{stored_row.get('ts')}"


def saved_hand_back(session_id):
    """The latest review-loop hand-back row of this session. Raises NoHandbackError when the loop was dispatched and
    never handed back, and LoopWaitingError when it stopped to wait on a background agent or shell."""
    if not session_id:
        raise PacketError(["the packet on stdin is empty and CLAUDE_CODE_SESSION_ID is not set, so no saved "
                           "hand-back can be looked up"])
    seen = handback.latest(session_id)
    gap = handback.hand_back_gap(seen)
    stored_row = seen["handback"] or {}
    # A pending dispatch (waiting, never handed back, or re-dispatched) is newer than any stored hand-back, so the
    # stored hand-back's owner is not the answer: the run owns it only when the run dispatched it.
    if gap in (handback.LOOP_WAITING, handback.NO_HANDBACK, handback.REDISPATCHED):
        code_step = code_step_pending_review(session_id, seen["handback"])
    else:
        code_step = active_code_step(session_id, stored_row.get("agent_id"))
    if code_step:
        raise PacketError([f"a /code run owns this session's review hand-backs (code-step state {code_step[0]}, stage "
                           f"{code_step[1]}): its packet goes through code_step.py resume, not `packet`"])

    if gap == handback.LOOP_WAITING:
        raise LoopWaitingError(seen["stop"]["ts"])
    if gap in (handback.NO_HANDBACK, handback.REDISPATCHED):
        raise NoHandbackError(hand_back_id(seen["handback"], session_id))
    if gap == handback.NO_DISPATCH:
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
    unreviewed_in_a_row = handback.unreviewed_streak(session_id)
    unreviewed_fix = handback.ended_on_unreviewed_fix(session_id, stored_row.get("agent_id"))
    return stored_row["message"], hand_back_id(stored_row, session_id), unreviewed_in_a_row, unreviewed_fix


def new_state(options, packet, packet_id):
    previous = read_state() or {}
    same_run = previous.get("packet_id") == packet_id
    waiting_packets = [] if same_run else carried_waiting_packets(previous)
    fixed_paths = handback.fixed_paths(packet)
    state = {"skill": options.skill, "scope": options.scope, "lane": options.lane, "iter": packet["iter"],
             "spec_iter": packet["spec_iter"], "status": packet["status"], "repo": script_utils.repo_name("."),
             "branch": script_utils.current_branch(".") or "-", "packet_id": packet_id,
             "source": options.source, "fixed_paths": fixed_paths}
    if same_run:
        for key in (
            "stage",
            "asks",
            "jumped",
            "aikido_posted",
            "escapes_logged",
            "asks_logged",
            "plan_impact",
            "waiting_packets",
        ):
            if key in previous:
                state[key] = previous[key]
    if waiting_packets:
        state["waiting_packets"] = waiting_packets
    return state


def has_unanswered_asks(packet_state):
    asks = packet_state.get("asks") or []
    logged = packet_state.get("asks_logged", [])
    return any(index not in logged for index in range(len(asks)))


def carried_waiting_packets(previous):
    """The packets still waiting for their asks to be answered when a different packet replaces `previous`: the ones
    `previous` already kept, then `previous` itself when it holds unanswered asks. Oldest first, one flat list."""
    carried = list(previous.get("waiting_packets") or [])
    if has_unanswered_asks(previous):
        carried.append({key: value for key, value in previous.items() if key != "waiting_packets"})
    return carried


def print_logged(notes):
    if not notes:
        return
    print(LOGGED_HEADING)
    print("\n".join("- " + note for note in notes))


def blocker_lines(packet):
    return ["- " + one_line(item_text(item, "finding", "item"), 400) for item in packet["blockers"]]


def remaining_lines(packet):
    return ["- " + item_text(item, "disposition", "finding", "file_line") for item in packet["findings_remaining"]]


# The statuses that stop the caller: (the instruction, the packet's entry lines under it).
STOP_STATUSES = {
    "critical-blocker": ("Present these blockers and wait for direction. Do not re-dispatch. Do not run /fix. "
                         "Do not mark the gate.", blocker_lines),
    "setup-fault": ("The full check could not run in this environment. This is a toolkit or environment fault, not a "
                    "code failure. Present these lines and wait for direction. Do not re-dispatch. Do not run /fix. "
                    "Do not mark the gate.", blocker_lines),
    "cap-reached": ("The review cap was reached. Report these findings; the user decides. Do not re-dispatch. Do not "
                    "run /fix. Do not mark the gate: the session stays dirty, so git commit stays blocked.",
                    remaining_lines),
}


# A class-closure receipt that says a class is still open. The receipt is free text, so this matches its words.
OPEN_CLASS = re.compile(r"\b(not closed|unclosed|(still|left|remains?|stays?) open|open (class|members?))\b", re.I)
# Words that turn an open-class clause into a closed one: "none left open", "open members: none", "was left open".
NEGATED_CLASS = re.compile(r"\b(none|no|nothing|zero|0|was|were)\b", re.I)
RECEIPT_CLAUSE = re.compile(r"[;,.\n()]")
SCOPED_RERUN = ("The review cap was reached with a class still open. Report these findings. Another full review "
                "would find one more member at a time, so do not offer one: the next run is a scoped review of the "
                "files the capped run's fixes touched. When the user asks to go on, dispatch review-loop "
                "(model: \"sonnet\") with the dispatch lines below. "
                "Do not run /fix. Do not mark the gate: the session stays dirty, so git commit stays blocked.")


def names_an_open_class(receipt):
    """Whether a clause of the class-closure receipt says a class is still open and no word in it negates that."""
    clauses = RECEIPT_CLAUSE.split(receipt)
    return any(OPEN_CLASS.search(clause) and not NEGATED_CLASS.search(clause) for clause in clauses)


def scoped_rerun_lines(packet, skill):
    """The dispatch that reviews only the files the capped run's fixes touched after a cap-reached with an open
    class, or [] when the class is closed or the packet names no file the fix touched."""
    if not names_an_open_class(packet["class_closure"]):
        return []
    fix_files = [str(path) for path in packet["files_touched"]]
    if not fix_files:
        return []

    lines = ["mode: review-first", f"caller: {skill}", "iter=0", "handoff:", "  files:"]
    for path in fix_files:
        lines += [f"    - path: {path}", "      change: touched by the capped run's fixes"]
    lines += ["  tests-run: none", f"  flagged: the open class - {one_line(packet['class_closure'])}",
              "  prior-issues:"]
    for item in packet["findings_remaining"]:
        file_path, _line = split_location(item.get("file_line", ""))
        lines += [f"    - issue: {one_line(item_text(item, 'finding'))}", "      status: partial",
                  f"      file: {file_path or '-'}"]
    return lines


def stop_for_status(packet, options, state):
    save_fix_state(state)
    if packet["ask"]:
        fill_packet_ask_ids(packet, state)
        save_packet_asks(packet, state)
    replies, failures = post_aikido_replies(packet, options.aikido_targets, state)

    instruction, entry_lines = STOP_STATUSES[packet["status"]]
    entries = entry_lines(packet)
    rerun_lines = scoped_rerun_lines(packet, options.skill) if packet["status"] == "cap-reached" else []
    if rerun_lines:
        instruction = SCOPED_RERUN
        entries += ["Dispatch lines (pass exactly these):", *rerun_lines]
    ask_lines = []
    if packet["ask"]:
        ask_lines = [jumped_line(state), asks_done_line(packet["ask"], state), *ask_listing_lines(packet["ask"])]
    print_action("stop", instruction, *entries, *ask_lines)
    if replies:
        print("AIKIDO REPLIES POSTED:")
        print("\n".join(replies))
    print_logged(failures)


def command_packet(argv):
    options = packet_arguments(argv)
    try:
        message, packet_id, unreviewed_in_a_row, unreviewed_fix = read_message()
    except NoHandbackError as error:
        stop_for_missing_hand_back(options.skill, error.last_hand_back_id)
        return 2
    except LoopWaitingError as error:
        return wait_for_loop(options.skill, error.stop_ts)
    packet = handback.load(message)
    if unreviewed_in_a_row:
        return stop_for_unreviewed(options.skill, packet, unreviewed_in_a_row)
    state = new_state(options, packet, packet_id)
    if state.get("stage") in FINISHED_STAGES:
        return print_action("done", f"This packet was already processed (stage {state['stage']}). Nothing was "
                            "logged or posted again. Continue from the step the first output named.")

    if packet["status"] == "plan-impact":
        return present_plan_impact(packet, state)
    if packet["status"] in STOP_STATUSES:
        return stop_for_status(packet, options, state)

    save_fix_state(state)
    notes = log_escapes(state, options.escapes, options.lane)
    replies, failures = post_aikido_replies(packet, options.aikido_targets, state)
    notes += failures
    if packet["ask"]:
        fill_packet_ask_ids(packet, state)
        present_packet_asks(packet, state)
    else:
        print_action("render-and-finish", gate_mark_line())
    sections = packet_sections(packet, replies, unreviewed_fix)
    print_user_block(handback.render(packet, options.skill, sections))
    print_logged(notes)
    if options.skill == "review" and not is_outstanding(packet):
        print(f"Nothing is outstanding: say \"{NOTHING_OUTSTANDING}\"")
    print("MODEL STILL DOES: " + model_duties(packet, options))


def packet_sections(packet, replies, unreviewed_fix):
    sections = [("Aikido replies", replies)] if replies else []
    if unreviewed_fix:
        sections.append(handback.unreviewed_fix_section(packet))
    ledger_warning = script_utils.missing_ledger_warning()
    if ledger_warning:
        sections.append(("Ledger", [ledger_warning]))
    return sections


def model_duties(packet, options):
    duties = []
    if packet["ask"]:
        duties.append("present each ask and judge the user's answer")
    if options.skill == "fix":
        duties.append("recommend /eng-spec if a finding needs architectural rethinking")
        if options.source == "conversation" and not options.escapes:
            duties.append("if a fixed finding was a defect in code /review already passed, run "
                          "`review_fix.py escape --escape ...` (class, severity, gate_missed, guard)")
    duties.append("write the closing line to the user; add nothing the block already says")
    return "; ".join(duties) + "."


def command_escape(argv):
    parser = argument_parser("escape")
    parser.add_argument("--escape", action="append", default=[])
    options = parser.parse_args(argv)
    escapes = [parse_escape(spec) for spec in options.escape]
    if not escapes:
        raise UsageError("escape needs at least one --escape")
    state = load_fix_state()
    if state.get("skill") != "fix":
        raise UsageError("escape rows belong to /fix; the saved packet came from /review.")
    print_action("done", *["- " + note for note in log_escapes(state, escapes, state["lane"])])


# ---------- asks ----------

def log_ask_outcome(state, item, outcome, finding_id, decided_by="user"):
    """(exit code, output) of the outcome row's log call."""
    return run_command(["bash", str(CLAUDE_DIR / "skills/review/log-review-finding"), "kind=finding",
                        f"finding_id={finding_id}", *handback.ask_row_fields(state, item), f"ask_outcome={outcome}",
                        f"ask_decided_by={decided_by}"])


def fill_packet_ask_ids(packet, state):
    """Give every ask without a valid finding_id the id of the ask row the loop logged for it, matched on file and
    line, or of an ask row logged here when the loop logged none. A valid id the loop wrote stays. A plan-impact ask
    is not a finding and gets none. An ask whose row cannot be logged gets none, and asks-done reports it. A repeat of
    the same packet keeps the asks saved the first time, so no ask row is logged twice."""
    if state.get("asks"):
        packet["ask"] = state["asks"]
        return

    finding_asks = [item for item in packet["ask"] if not is_plan_impact_ask(item)]
    handback.supply_ask_finding_ids(finding_asks, os.environ.get("CLAUDE_CODE_SESSION_ID", ""),
                                    CLAUDE_DIR / "skills/review/log-review-finding", state)


def read_outcomes(argv, asks):
    """The outcome word of each ask. A note after `:` is accepted and dropped."""
    if len(argv) != len(asks):
        raise UsageError(f"{len(asks)} ask(s) waiting but {len(argv)} outcome(s) given")
    outcomes = [word.partition(":")[0] for word in argv]
    for word, outcome in zip(argv, outcomes, strict=True):
        if outcome not in ASK_OUTCOMES:
            raise UsageError(f"outcome {word!r} is not one of {'|'.join(ASK_OUTCOMES)}")
    return outcomes


def log_fix_ask_outcomes(state, asks, outcomes, decided_by="user"):
    """(ask counts of this call: plan-impact asks skipped, outcomes logged under a new finding_id; failure lines). An
    ask that is logged or skipped joins asks_logged and is never tried again."""
    logged = state.setdefault("asks_logged", [])
    ask_counts = {PLAN_IMPACT: 0, NEW_FINDING_ID: 0}
    failures = []
    for index, (item, outcome) in enumerate(zip(asks, outcomes, strict=True)):
        if index in logged:
            continue
        if is_plan_impact_ask(item):
            ask_counts[PLAN_IMPACT] += 1
            logged.append(index)
            continue

        finding_id, new_finding_id_note = handback.ask_outcome_finding_id(item)
        code, output = log_ask_outcome(state, item, outcome, finding_id, decided_by)
        if code == 0:
            logged.append(index)
            if new_finding_id_note:
                print(f"review-fix: {new_finding_id_note}", file=sys.stderr)
                ask_counts[NEW_FINDING_ID] += 1
            continue
        path, line = split_location(item.get("file_line") or "-")
        failures.append(f"{path}:{line}: {one_line(output, 160)}")
    return ask_counts, failures


def waiting_ask_packets(state):
    """The packets that hold unanswered asks: the current one, then the kept ones, oldest first."""
    waiting = []
    # A stage-asks state with every ask already logged is a retry that asks-done must still accept.
    if has_unanswered_asks(state) or (state.get("stage") == "asks" and state.get("asks")):
        waiting.append(state)
    waiting += [kept for kept in state.get("waiting_packets") or [] if has_unanswered_asks(kept)]
    return waiting


def waiting_packet_lines(waiting):
    lines = []
    for packet_state in waiting:
        asks = packet_state["asks"]
        first = asks[0]
        lines.append(f"- {packet_state['packet_id']}: {len(asks)} ask(s); first: "
                     f"{first.get('file_line') or 'no file:line'} {one_line(first['question'], 120)}")
    return lines


def choose_asks_packet(waiting, packet_id):
    """The one waiting packet the outcomes belong to. Refuses when several wait and none is named."""
    if packet_id is None and len(waiting) == 1:
        return waiting[0]
    if packet_id is None:
        raise UsageError("more than one packet holds unanswered asks. Rerun asks-done with --packet <packet_id> for "
                         "the one you answer:\n" + "\n".join(waiting_packet_lines(waiting)))
    for packet_state in waiting:
        if packet_state["packet_id"] == packet_id:
            return packet_state
    raise UsageError(f"--packet {packet_id!r} is not a packet with unanswered asks. Waiting:\n"
                     + "\n".join(waiting_packet_lines(waiting)))


def asks_done_options(argv):
    """(outcome words, who decided, the named packet_id or None) of an asks-done call."""
    outcome_words, decided_by = script_utils.pop_option(argv, "--by")
    if decided_by is None:
        decided_by = "user"
    if decided_by not in ("user", "session"):
        raise UsageError(f"asks-done --by needs user or session, not {decided_by!r}")

    outcome_words, packet_id = script_utils.pop_option(outcome_words, "--packet")
    if packet_id == "":
        raise UsageError("asks-done --packet needs a packet_id")
    return outcome_words, decided_by, packet_id


def command_asks_done(argv):
    state = load_fix_state()
    waiting = waiting_ask_packets(state)
    if not waiting:
        if state.get("stage") == "done" and state.get("asks"):
            return print_action("done", "The ask outcomes were already logged. Run nothing more.")
        raise UsageError("no asks are waiting. `asks-done` follows a packet that carried ask[] entries.")

    outcome_words, decided_by, packet_id = asks_done_options(argv)
    target = choose_asks_packet(waiting, packet_id)
    asks = target["asks"]
    outcomes = read_outcomes(outcome_words, asks)

    ask_counts, failures = log_fix_ask_outcomes(target, asks, outcomes, decided_by)
    if not failures and target is state:
        state["stage"] = "done"
    if not failures and target is not state:
        state["waiting_packets"] = [kept for kept in state["waiting_packets"] if kept is not target]
    save_fix_state(state)

    rows_logged = sum(1 for index in target["asks_logged"] if not is_plan_impact_ask(asks[index]))
    summary = f"Logged {rows_logged} of {len(asks)} ask outcome row(s)."
    if decided_by == "session":
        summary += " The session ruled, not the user."
    if ask_counts[PLAN_IMPACT]:
        summary += f" {ask_counts[PLAN_IMPACT]} plan-impact ask(s) are not logged as findings."
    if ask_counts[NEW_FINDING_ID]:
        summary += (f" {ask_counts[NEW_FINDING_ID]} ask(s) without a valid finding_id are logged under a new "
                    "finding_id.")
    if failures:
        summary += " Failures (mention, never block; run the same asks-done again to retry only these):"
    print_action("done", summary, *["- " + failure for failure in failures])
    print("MODEL STILL DOES: act on accepted/modified asks as the user directed (dispatch a coder, or edit in scope).")


# ---------- plan-impact ruling ----------

def discuss_commands():
    commands = []
    for by, words in (("user", "the decision in one line"), ("session", "your reason")):
        for decision in ("adopt", "keep"):
            commands.append(f'{DECIDE_SCRIPT} decide {decision} --by {by} --ruling "<{words}>" {PLAN_ARG_NOTE}')
    return commands


def command_decide(argv):
    parser = argument_parser("decide")
    parser.add_argument("decision", choices=sorted(DECISION_WORDS))
    parser.add_argument("--ruling", default="")
    parser.add_argument("--plan", default="")
    parser.add_argument("--by", nargs="?", const="", default=None)
    options = parser.parse_args(argv)
    state = load_fix_state()
    if state.get("stage") != "plan-impact":
        raise UsageError("no plan-impact is waiting.")
    if options.decision == "discuss":
        return print_action("discuss", "Discuss the plan impact with the user, then run one of these. Do not "
                            "re-dispatch yet.", *discuss_commands(), DECIDE_BY_NOTE)
    if options.by not in ("user", "session"):
        raise UsageError(f"decide {options.decision} needs --by user or --by session. Usage: `{DECIDE_USAGE}`. "
                         f"{DECIDE_BY_NOTE}")
    if not options.ruling.strip():
        raise UsageError(f"decide {options.decision} needs --ruling. Usage: `{DECIDE_USAGE}`.")
    plan_path = pathlib.Path(options.plan) if options.plan else None
    if plan_path is not None and not plan_path.exists():
        raise UsageError(f"--plan {options.plan} does not exist")

    record_plan_ruling(state, options.decision, options.by, options.ruling, plan_path)


def record_plan_ruling(state, decision, by, ruling, plan_path):
    """Log a plan-impact ruling under ## Plan Deviations (in plan_path, else as lines the session adds) and print the
    re-dispatch."""
    choice = DECISION_WORDS[decision]
    owner = plan_format.ruling_owner(".", by)
    ruled_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = plan_format.ruling_deviation(None, choice, owner, ruled_at, ruling, state["plan_impact"])
    if plan_path is not None:
        plan_format.append_deviation(plan_path, entry)

    spec = state.get("spec_iter")
    session_note = " The session ruled, not the user." if by == "session" else ""
    lines = [f"plan_impact: RESOLVED - {choice}.{session_note} Ruling: {one_line(ruling)}",
             f"iter={state['iter']}"]
    if spec is not None:
        lines.append(f"spec_iter={spec}")
    carried = state.get("carried_findings") or []
    if carried:
        lines.append("carried-findings:  # left open by the round the plan impact stopped; review them too")
        lines += [f"  - {finding}" for finding in carried]

    state["stage"] = "redispatch"
    save_fix_state(state)
    print_action(
        "redispatch",
        (
            f"Recorded in {plan_path} under ## Plan Deviations."
            if plan_path is not None
            else "No --plan was given: add these lines under ## Plan Deviations in the plan yourself, then continue:"
        ),
        *entry,
        'Re-dispatch review-loop (same Agent call, model: "sonnet") with the same arguments as the first dispatch '
        "and these lines added, both counters kept:",
        *lines,
    )


def main():
    arguments = sys.argv[1:]
    handlers = {"packet": command_packet, "escape": command_escape, "asks-done": command_asks_done,
                "decide": command_decide}
    if not arguments or arguments[0] not in handlers:
        print(__doc__)
        return 2
    command = arguments[0]
    try:
        return handlers[command](arguments[1:]) or 0
    except PacketError as error:
        stop_for_parse_failure(error, error.raw)
        try:
            if state_file().exists():
                save_fix_state({**load_fix_state(), "stage": "parse-failed"})
        except UsageError:
            pass
        return 2
    except UsageError as error:
        print_action("stop-usage", f"review_fix.py {command}: {error}",
                     f"If you ran `{MARK_CLEAN}` alongside this call, run `{MARK_DIRTY}` now. Fix the call and run "
                     "it again.")
        return 2


if __name__ == "__main__":
    sys.exit(main())
