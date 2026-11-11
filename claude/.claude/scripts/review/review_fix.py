#!/usr/bin/env python3
"""review_fix.py: the fixed steps of /review and /fix as a script. Both skills run `launch`, which runs the review
loop as a script, then `packet`, and do exactly what the ACTION lines say. The script reads the packet through
handback.py, routes on status, renders the packet, logs the rows, posts the Aikido replies, and prints what the model
still judges.

  review_fix.py packet --skill review|fix [options] [< packet]
      --scope branch-exit|standalone   scope of the ask rows (review passes branch-exit when it dispatched with base=)
      --lane <lane>  lane of the ask and escape rows (default none for review, code for fix); `ledger registry` lists
                     the allowed values
      --source conversation|cc|handoff (fix) where the findings came from; escapes log only for conversation
      --escape "file=<p>|class=<c>|severity=<s>|gate_missed=<g>|guard=<r>|desc=<one line>"   (fix, repeatable)
      --aikido "<path>:<line>=<comment_id>"                                                 (fix, repeatable)
      --pr <number>  (fix) the PR the Aikido comments are on; without it gh asks the current branch
      --launch <launch.json>  the run's launch record, which `launch` adds to the packet command it prints; asks-done
                     reads the fix run's flags from it
      With empty stdin, `packet` reads this session's latest review-loop hand-back: the loop script stores it
      itself (write_handback_rows) after `launch`, and handback.py's hook stores it for a dispatched agent. It
      refuses when the session has no dispatch on record. When the loop ended without handing back, it prints
      `ACTION: stop-no-handback` and leaves the saved state alone: re-dispatch once, then stop and show the user the
      loop's final text on a second miss.
      A re-run on the same hand-back (the same stored row; the same text, for a packet on stdin) repeats no side
      effect: posted replies, logged escapes and the nvim-jump are kept in the state. Two dispatches that return the
      same text are two runs.
  review_fix.py launch [--repo <abs path>] [--fix <findings file> [--no-review]] [--base <ref>] [--file <path>]...
                       [--handoff <file>] [--fast|--deep] [--iter N] [--lane <lane>] [--detach]
                                         start the scripted review loop as a detached process (review_launch.py; `launch
                                         --help` lists the flags). It returns when the loop asks for reviewers
                                         (`ACTION: dispatch-reviewer`, see reviewer_dispatch.py) or when the loop
                                         script exits, and then names the packet command to run. --detach returns
                                         once the loop started and names the code_wait.py wait. Exits 2 when
                                         CLAUDE_CODE_SESSION_ID is not set, on a bad flag or findings file, and on a
                                         review-first run with nothing to review.
  review_fix.py escape --escape "..."...   log escape rows from the saved packet state (fix, repeatable)
  review_fix.py asks-done [--by <user|session>] [--packet <packet_id>] [--correct] <outcome>...
                                         one outcome per ask, in order: accepted | rejected | modified, optional
                                         ":<one line note>" after it; modified needs the note, the user's change.
                                         Logs one row per ask, once. With an ask accepted or modified it writes them
                                         to <git dir>/review-fix/ask-findings.md and prints `ACTION: redispatch`
                                         with the fix run's launch line (review_fix_asks.py). `ACTION: done` when
                                         all are rejected, when only plan-impact asks were accepted (they write no
                                         findings), and on a retry after the launch line printed (it prints the
                                         stored launch line again). A retry with outcomes that differ from the ones
                                         already logged is refused (exit 2); --correct changes an answer while the
                                         printed fix run of the current packet has not launched and every ask of the
                                         first asks-done has logged.
                                         `ACTION: launch-fix-run` when the run has no
                                         launch flags on record: the findings file is written and the line is
                                         `review_fix.py launch --fix <file> --iter <n> --repo <repo> --detach`.
                                         An accepted or rejected outcome on an ask whose proposed change is conditional
                                         ("if not confirmed, revert X") is refused with exit 2 and nothing logged:
                                         answer it with 'modified:<the change to make, with no condition>'.
                                         --correct <outcome>... re-answers the asks while the printed fix run has
                                         not launched: it logs a row for each changed ask, rewrites the findings file
                                         and prints the launch line again (`ACTION: done` when no ask is left to
                                         apply). It refuses after the launch, while the first asks-done still has
                                         unlogged asks, and for a packet other than the current one.
                                         --by session when the session ruled on the asks itself; default user.
                                         Answers one packet. When a second packet handed back before the first one's
                                         asks were answered, both wait: asks-done then refuses and lists them, and
                                         --packet <packet_id> names the one the outcomes belong to.
  review_fix.py decide <adopt|keep> --by <user|session> --ruling "<the decision in one line>" [--plan <path>]
                                         Only --by user is the user's own word. adopt prints `ACTION: redispatch`;
                                         when the run has launch flags on record, it writes the first handoff plus
                                         the RESOLVED lines to <git dir>/review-fix/adopt-handoff.md and prints the
                                         ready launch line (`launch --iter <n> <the first run's flags> --handoff
                                         <that file> --detach`); otherwise it prints the lines to build it by hand.
                                         With no saved state (no `packet` ran), it reads the held plan impacts from
                                         this session's hand-back: keep records the ruling; adopt logs the deviation
                                         and stops, since the caller must rerun its own review loop.
  review_fix.py decide discuss          print the decide commands for a plan-impact ruling and record nothing.
  review_fix.py defer <handoff file>    /code's phase-end deferral of held plan impacts. The handoff file must hold
                                         `plan_impact: RESOLVED: deferred to phase end by the session, <date>:
                                         <summary>`; records the ruling so the commit gate counts the review as clean.

State lives in <git dir>/review-fix/state.json. A packet that does not parse stops with exit 2. Env
REVIEW_FIX_CLAUDE_DIR overrides the toolkit folder; REVIEW_FIX_NVIM_JUMP and REVIEW_FIX_GH override the nvim-jump
and gh commands; REVIEW_FIX_LOOP_SCRIPT overrides the loop script `launch` runs; HANDBACK_STORE_DIR overrides the
hand-back store; CLAUDE_CODE_SESSION_ID names the session."""
import json
import os
import pathlib
import shlex
import sys

SIBLING_FOLDERS = (".", "../lib", "../code", "../telemetry")
sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / folder) for folder in SIBLING_FOLDERS]
import capped_review
import handback
import handback_store
import handoff_files
import plan_format
import review_asks
import review_launch
import script_utils
from capped_review import CAP_REACHED
from handback import FIX_REMOVED_CHANGE, PLAN_IMPACT_STATUS, PacketError, item_text
from review_fix_asks import command_asks_done, relaunch_line
from review_fix_state import (
    ADD_DEVIATIONS_LINE,
    ASK_LOGGER,
    CLAUDE_DIR,
    CORRECT_OPEN_KEY,
    PENDING_LAUNCH_KEY,
    REVIEW_FIX_COMMAND,
    UsageError,
    argument_parser,
    has_unanswered_asks,
    load_fix_state,
    print_action,
    print_user_block,
    read_state,
    repo_that_logged_packet_asks,
    review_fix_dir,
    review_fix_state_file,
    save_fix_state,
)
from saved_handback import NoHandbackError, dispatched_repo, read_message
from script_utils import one_line, run_command, split_location

SOURCES = ["conversation", "cc", "handoff"]
PLAN_ARG_NOTE = "--plan <the plan path, when the handoff names one>"
DECIDE_USAGE = f"{plan_format.DECIDE_USAGE_STEM} {PLAN_ARG_NOTE}"
NOTHING_OUTSTANDING = "No issues found that warrant auto-fix. Ready for `/commit`."
LOGGED_HEADING = "LOGGED / POSTED (mention failures, never block on them):"
FINISHED_STAGES = ("done", "redispatch")
ADOPT_HANDOFF_NAME = "adopt-handoff.md"
DEFER_LINE_PREFIX = "plan_impact: RESOLVED: deferred to phase end"
DEFER_LINE = f"{DEFER_LINE_PREFIX} by the session, <date>: <summary>"
LOOP_SCRIPT = pathlib.Path(os.environ.get("REVIEW_FIX_LOOP_SCRIPT",
                                          pathlib.Path(__file__).resolve().parent / "review_loop_script.py"))

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


def packet_arguments(argv):
    parser = argument_parser("packet")
    parser.add_argument("--skill", required=True, choices=["review", "fix"])
    parser.add_argument("--scope", default="standalone", choices=["branch-exit", "standalone"])
    parser.add_argument("--lane")
    parser.add_argument("--source", default="handoff", choices=SOURCES)
    parser.add_argument("--escape", action="append", default=[])
    parser.add_argument("--aikido", action="append", default=[])
    parser.add_argument("--pr")
    parser.add_argument("--launch")
    options = parser.parse_args(argv)
    options.relaunch_args = []
    if options.launch:
        try:
            options.relaunch_args = review_launch.read_relaunch_args(options.launch)
        except review_launch.LaunchError as error:
            raise UsageError(str(error)) from error
    if options.pr is not None and not options.pr.isdigit():
        raise UsageError(f"--pr {options.pr!r} is not a PR number")
    options.lane = options.lane or ("code" if options.skill == "fix" else "none")
    options.escapes = [parse_escape(spec) for spec in options.escape]
    options.aikido_targets = [parse_aikido(spec) for spec in options.aikido]
    if options.skill == "review" and (options.escapes or options.aikido_targets or options.pr):
        raise UsageError("--escape, --aikido and --pr belong to /fix only")
    return options


# ---------- actions ----------

def is_outstanding(packet):
    findings_left = any(packet[key] for key in ("fixed", "ask", "skipped_fp", "nit", "findings_remaining"))
    return findings_left or bool(handback.held_plan_impacts(packet))


def stop_for_parse_failure(error, raw_message):
    print_action("stop-parse-failure",
                 "The review-loop packet did not parse. Nothing was routed, logged or posted.",
                 *[f"- {problem}" for problem in error.problems],
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
        script_utils.write_text_atomically(path, json.dumps(saved))
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
                     "Run `launch` once more with the same flags, then run `packet` again.")
        return
    print_action("stop-no-handback",
                 f"The review-loop ended {misses} times in a row without calling SubagentHandback. Nothing was routed, "
                 "logged or posted, and the earlier run's state is untouched.",
                 "Stop. Do not re-dispatch again. Show the user the loop's final text as it returned.")


def stop_for_unreviewed(skill, packet, unreviewed_in_a_row):
    """The loop handed back clean with no reviewer run. The first time, the caller re-dispatches it at the same round
    count; the second time in a row, it stops."""
    if unreviewed_in_a_row < 2:
        lines = ("The review-loop handed back clean but dispatched no reviewer. Nothing was routed, logged or posted.",
                 f"Run `launch` once more with the same flags plus `--iter {packet['iter']}` in place of any "
                 f"`--iter`, then run `packet --skill {skill}` again.")
    else:
        lines = (f"The review-loop handed back clean with no reviewer run {unreviewed_in_a_row} times in a row. "
                 "Nothing was routed, logged or posted.",
                 "Stop. Do not re-dispatch again. Tell the user no reviewer ran, so the commit gate stays closed.")
    print_action("stop-no-reviewer", *lines)
    return 2


def plan_impact_question_lines(plan_impact, packet):
    """The lines that tell the session to put one plan-impact question to the user and what to run on the answer."""
    return [
        "Call AskUserQuestion now. Without that tool, ask the same question in plain text, list the options numbered, "
        "end the turn and wait for the reply. Do not re-dispatch and do not triage this as an ask. Question: assumed, "
        "then found, then what changes, taken from this block:",
        plan_impact,
        f"Options, in this order: {' / '.join(plan_format.PLAN_IMPACT_OPTIONS)}.",
        "Map the answer, picked or typed, to adopt, keep or discuss. For adopt or keep, put the user's words in "
        "--ruling; for discuss, run `decide discuss`.",
        f'Then run: {REVIEW_FIX_COMMAND} decide <adopt|keep> --by user --ruling "<the decision in one line>" '
        f"{PLAN_ARG_NOTE}",
        plan_format.DECIDE_BY_NOTE,
        f"Counters held for the re-dispatch: iter={packet['iter']} "
        f"spec_iter={packet['spec_iter'] if packet['spec_iter'] is not None else 'absent'}",
    ]


def plan_impact_deviation_lines(adopted):
    """The `## Plan Deviations` lines for the plan impacts adopted by rule, no question asked."""
    owner = plan_format.SESSION_RULING_OWNER
    ruled_at = plan_format.ruled_at_now()
    choice = plan_format.DECISION_WORDS["adopt"]
    lines = []
    for impact in adopted:
        ruling = plan_format.below_criteria_ruling(impact["text"])
        lines += plan_format.ruling_deviation(None, choice, owner, ruled_at, ruling, impact["text"])
    return lines


APPLIED_IMPACT_LINE = ("A plan impact that changes an acceptance criterion came from a coder whose edits are already "
                       "in the tree. Keeping the plan as written means reverting those edits; adopting the change "
                       "keeps them.")
APPLIED_KEEP_LINE = ("The plan stays as written: the coder's edits for the held plan impact are in the tree, so revert "
                     "them, and nothing is re-dispatched.")


def present_plan_impacts(packet, state):
    """Prints the packet's plan impacts once, after the review result. The loop never stopped for them. An adopted one
    prints as a plan deviation line to add, with no question. A toolkit-cause one prints as a toolkit fault, with no
    question. The ones that change an acceptance criterion go to the user in one closing question; the fix waits for the
    answer."""
    impacts = packet["plan_impacts"]
    if not impacts:
        return

    adopted = [impact for impact in impacts if impact["adopted"]]
    toolkit = handback.toolkit_plan_impacts(packet)
    held = handback.held_plan_impacts(packet)
    lines = []
    if adopted:
        lines += ["Plan impacts adopted by rule (no acceptance criterion changes, so the code wins; no one was asked). "
                  + ADD_DEVIATIONS_LINE,
                  *plan_impact_deviation_lines(adopted)]
    for impact in toolkit:
        lines += [f"Toolkit fault, not a plan change (the {impact['gate']} {plan_format.cause_stop(impact['cause'])}):",
                  impact["text"]]
    if not held:
        print_action("show-plan-impacts", *lines)
        return

    held_text = handback.held_plan_impact_text(held)
    applied = any(impact["applied"] for impact in held)
    state.update({"plan_impact": held_text, "plan_impact_held": True, "plan_impact_applied": applied,
                  "carried_findings": [*handback.carried_findings(packet),
                                       *[f"plan impact: {one_line(impact['text'], 800)}" for impact in held]]})
    if state.get("stage") != "asks":
        state["stage"] = "plan-impact"
    save_fix_state(state)
    if applied:
        lines += [APPLIED_IMPACT_LINE, "Ask once, now that the review is done."]
    else:
        lines += ["Plan impacts that change an acceptance criterion stay unapplied until the user signs off. Ask once, "
                  "now that the review is done."]
    lines.append(f"Gate: do not commit yet: {len(held)} plan impact(s) wait for a ruling, so the commit gate counts "
                 "the review as dirty until `decide` records one.")
    print_action("ask-user-plan-impact", *lines, *plan_impact_question_lines(held_text, packet))


def save_packet_asks(packet, state):
    """Run nvim-jump once, save the packet's asks with stage `asks`, and return them."""
    asks = packet["ask"]
    if "jumped" not in state:
        state["jumped"] = review_asks.run_nvim_jump(os.environ.get("REVIEW_FIX_NVIM_JUMP", "nvim-jump"), asks)
    state.update({"stage": "asks", "asks": asks})
    save_fix_state(state)
    return asks


def jumped_line(state):
    return f"The script ran nvim-jump for all asks ({state['jumped']}). Do not run it again."


def asks_done_line(asks, state):
    """The asks-done command for the packet in `state`. It names --packet when another packet still waits, so the
    command runs as printed."""
    packet_flag = f"--packet {state['packet_id']} " if state.get("waiting_packets") else ""
    outcome_slots = " ".join(f"<outcome-{number}>" for number in range(1, len(asks) + 1))
    return (f"After the user answers, run once: {REVIEW_FIX_COMMAND} asks-done "
            f"{packet_flag}{outcome_slots}  (one outcome per ask, in order; accepted: {review_asks.ACCEPT_MEANS} | "
            f"rejected: {review_asks.REJECT_MEANS} | 'modified:<the user's change in one line>', quoted as one shell "
            "word: make that change instead; an optional ':<one line note>' after accepted or rejected is not stored)")


def present_packet_asks(packet, state):
    asks = save_packet_asks(packet, state)
    lines = [
        jumped_line(state),
        "Present each ask below with its question and its proposed change, and wait for the user's direction. "
        "Never auto-fix an ask. If the repo's CLAUDE.md hands ask decisions to the session, decide each ask "
        "yourself and add `--by session` to asks-done; otherwise wait for the user.",
        asks_done_line(asks, state),
        *review_asks.numbered_ask_lines(asks, detail=True),
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
        named_file = script_utils.normalize_path(fields["file"])
        fixed_files = handback.touched_paths_named(named_file, state.get("fixed_paths", []))
        if not fixed_files:
            notes.append(f"escape for {named_file} not logged: no fixed[] entry names that file (not applied).")
            continue

        file = fixed_files[0] if len(fixed_files) == 1 else named_file
        if file in logged:
            notes.append(f"escape for {file} already logged: skipped.")
            continue
        repo = script_utils.repo_name(".")
        code, output = run_command(["bash", str(CLAUDE_DIR / "scripts/telemetry/log-escape"), f"repo={repo}",
                                    "stage_found=walkthrough", f"gate_missed={fields['gate_missed']}",
                                    f"class={fields['class']}", f"severity={fields['severity']}",
                                    f"lane={fields.get('lane') or lane}", f"guard={fields['guard']}",
                                    "miss_reason=unknown", f"desc={one_line(fields['desc'])}", f"file={file}"])
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


def pr_number_from_gh(gh):
    """(exit code, output) of `gh pr view` for the current branch's PR number."""
    return run_command([gh, "pr", "view", "--json", "number", "--jq", ".number"])


def post_aikido_replies(packet, targets, state, pr_number=None):
    """(reply lines for the user text, failure notes). A comment id that got a reply is never posted to again.
    `pr_number` (from --pr) names the PR; without it gh asks the current branch, which fails on a detached HEAD."""
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
    code_pr = 0
    if pr_number is None:
        code_pr, pr_number = pr_number_from_gh(gh)
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

# State keys a repeat of the same packet keeps from the previous state.
SAME_RUN_STATE_KEYS = (
    "stage",
    "asks",
    "jumped",
    "aikido_posted",
    "escapes_logged",
    "asks_logged",
    "asks_redispatched",
    "asks_launch_line",
    "ask_outcomes",
    "ask_notes",
    CORRECT_OPEN_KEY,
    "last_asks_launch_line",
    "last_ask_outcomes",
    "last_ask_notes",
    "asks_deviations_printed",
    "plan_impact",
    "plan_impact_held",
    "plan_impact_applied",
    "carried_findings",
    "waiting_packets",
    "relaunch_args",
)


def new_state(options, packet, packet_id):
    previous = read_state() or {}
    same_run = previous.get("packet_id") == packet_id
    waiting_packets = [] if same_run else carried_waiting_packets(previous)
    fixed_paths = handback.fixed_paths(packet)
    state = {"skill": options.skill, "scope": options.scope, "lane": options.lane, "iter": packet["iter"],
             "review_round": packet["review_round"], "spec_iter": packet["spec_iter"], "status": packet["status"],
             "branch": script_utils.current_branch(".") or "-", "packet_id": packet_id,
             "source": options.source, "fixed_paths": fixed_paths,
             "files_touched": [str(path) for path in packet["files_touched"]]}
    if options.relaunch_args:
        state["relaunch_args"] = options.relaunch_args
    if same_run:
        for key in SAME_RUN_STATE_KEYS:
            if key in previous:
                state[key] = previous[key]
    if waiting_packets:
        state["waiting_packets"] = waiting_packets
    # A pending launch outlives any packet: only the launch clears it.
    if PENDING_LAUNCH_KEY in previous:
        state[PENDING_LAUNCH_KEY] = previous[PENDING_LAUNCH_KEY]
    return state


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


def plan_impact_lines(packet):
    return ["- " + one_line(packet["plan_impact"], 400)]


# The statuses that stop the caller: (the instruction, the packet's entry lines under it).
STOP_STATUSES = {
    "critical-blocker": ("Present these blockers and wait for direction. Do not re-dispatch. Do not run /fix.",
                         blocker_lines),
    "setup-fault": ("The full check could not run in this environment. This is a toolkit or environment fault, not a "
                    "code failure. Present these lines and wait for direction. Do not re-dispatch. Do not run /fix.",
                    blocker_lines),
    FIX_REMOVED_CHANGE: ("The fix passes removed half or more of the change under review. Present these lines "
                         "and wait for direction. Do not re-dispatch. Do not run /fix.",
                         blocker_lines),
    PLAN_IMPACT_STATUS: ("The review loop no longer emits plan-impact; present the plan_impact text and wait for "
                         "direction. Do not re-dispatch.",
                         plan_impact_lines),
    CAP_REACHED: ("The review cap was reached. Report these findings; the user decides. Do not re-dispatch. Do not "
                    "run /fix. The session stays dirty, so git commit stays blocked.",
                    remaining_lines),
}


SCOPED_RERUN = ("The review cap was reached with a class still open. Report these findings. Another full review "
                "would find one more member at a time, so do not offer one: the next run is a scoped review of the "
                "files the capped run's fixes touched. When the user asks to go on, Write the handoff lines below to a "
                "file and run the launch line below with `--handoff <that file>` added, in the background. "
                "Do not run /fix. The session stays dirty, so git commit stays blocked.")


def scoped_rerun_lines(packet):
    """The launch line and handoff of the next scoped review after a cap-reached with an open class, or [] when the
    packet's open_classes is empty, it names no file the fix touched, or git shows no change. The files are the ones
    git shows changed against HEAD in the dispatched repo (the packet names no start commit, and the loop reviews the
    working tree against HEAD); a file the fixes touched keeps its own change text."""
    if not packet["open_classes"]:
        return []
    fix_files = [str(path) for path in packet["files_touched"]]
    if not fix_files:
        return []

    repo = dispatched_repo() or pathlib.Path.cwd()
    changed = script_utils.changed_files(repo, "HEAD")
    if not changed:
        return []

    touched_text = dict.fromkeys(fix_files, "touched by the capped run's fixes")
    file_flags = " ".join(f"--file {shlex.quote(path)}" for path in changed)
    lines = [f"Launch line: {REVIEW_FIX_COMMAND} launch --repo {shlex.quote(str(repo))} --iter 0 {file_flags}",
             "Handoff lines (write exactly these):", "handoff:", "  files:",
             *handoff_files.file_entry_lines(changed, touched_text, "changed in the working tree against HEAD")]
    lines += ["  tests-run: none", f"  flagged: the open class - {one_line('; '.join(packet['open_classes']))}",
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
    replies, failures = post_aikido_replies(packet, options.aikido_targets, state, options.pr)

    instruction, entry_lines = STOP_STATUSES[packet["status"]]
    entries = entry_lines(packet)
    rerun_lines = scoped_rerun_lines(packet) if packet["status"] == CAP_REACHED else []
    if rerun_lines:
        instruction = SCOPED_RERUN
        entries += rerun_lines
    ask_lines = []
    if packet["ask"]:
        ask_lines = [jumped_line(state), asks_done_line(packet["ask"], state),
                     *review_asks.numbered_ask_lines(packet["ask"], detail=True)]
    print_action("stop", instruction, *entries, *ask_lines)
    present_plan_impacts(packet, state)
    if replies:
        print("AIKIDO REPLIES POSTED:")
        print("\n".join(replies))
    print_logged(failures)


def commit_credit_refusal(packet):
    """Why the commit gate does not credit a clean packet's review, as a line for the session, or None. The loop
    records the credit when it hands back, so a refusal there would otherwise surface only as a denied commit."""
    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    if not session_id or packet["status"] not in handback.CLEAN_STATUSES:
        return None
    reason = handback.false_clean_reason(session_id)
    if not reason:
        return None
    return f"COMMIT CREDIT: the commit gate does not credit this review yet: {reason}."


def command_packet(argv):
    options = packet_arguments(argv)
    try:
        message, packet_id, unreviewed_in_a_row, unreviewed_fix = read_message()
    except NoHandbackError as error:
        stop_for_missing_hand_back(options.skill, error.last_hand_back_id)
        return 2
    packet = handback.load(message)
    handback.print_dropped_asks(packet)
    stored_status = packet["status"]
    packet["scoped_tests"] = review_launch.unrun_scoped_tests_note(
        options.relaunch_args, stored_status, packet["scoped_tests"])
    packet["status"] = capped_review.effective_status(packet, dispatched_repo())
    capped_defer = packet["status"] != stored_status
    if unreviewed_in_a_row:
        return stop_for_unreviewed(options.skill, packet, unreviewed_in_a_row)
    state = new_state(options, packet, packet_id)
    if state.get("stage") in FINISHED_STAGES:
        return print_action("done", f"This packet was already processed (stage {state['stage']}). Nothing was "
                            "logged or posted again. Continue from the step the first output named.")
    logged_in_repo = repo_that_logged_packet_asks(packet_id)
    if logged_in_repo:
        return print_action("done", f"This packet's ask outcomes were already logged in "
                            f"{logged_in_repo}. Nothing was logged or posted again. Run any later step there.")

    if packet["status"] in STOP_STATUSES:
        return stop_for_status(packet, options, state)

    save_fix_state(state)
    notes = log_escapes(state, options.escapes, options.lane)
    replies, failures = post_aikido_replies(packet, options.aikido_targets, state, options.pr)
    notes += failures
    if packet["ask"]:
        fill_packet_ask_ids(packet, state)
        present_packet_asks(packet, state)
    else:
        print_action("render-and-finish")
    sections = packet_sections(packet, state, replies, unreviewed_fix, capped_defer)
    print_user_block(handback.render(packet, options.skill, sections))
    present_plan_impacts(packet, state)
    print_logged(notes)
    credit_refusal = commit_credit_refusal(packet)
    if credit_refusal:
        print(credit_refusal)
    if options.skill == "review" and not is_outstanding(packet):
        print(f"Nothing is outstanding: say \"{NOTHING_OUTSTANDING}\"")
    print("MODEL STILL DOES: " + model_duties(packet, options))


def deferred_files_line(packet):
    """One line that states the findings left open at the cap are deferred, then names the files the capped loop
    touched: files_touched, else the paths fixed[] names."""
    touched_paths = packet["files_touched"] or handback.fixed_paths(packet)
    named_paths = ", ".join(touched_paths) or "none named in files_touched or fixed[]"
    return f"The findings left open at the cap are deferred, not fixed. Files the loop touched: {named_paths}"


def deferred_from_cap_section(packet):
    """The (heading, lines) section for a packet that deferred from the cap."""
    return ("Deferred at the review cap",
            ["- The review capped with no blocker and a passed full check of the final tree, so its leftovers are "
             "deferred to the branch-exit queue.",
             "- " + deferred_files_line(packet)])


def packet_sections(packet, state, replies, unreviewed_fix, capped_defer):
    sections = [("Aikido replies", replies)] if replies else []
    if capped_defer:
        sections.append(deferred_from_cap_section(packet))
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


def command_launch(argv):
    try:
        return review_launch.command_launch(argv, LOOP_SCRIPT)
    except review_launch.LaunchError as error:
        raise UsageError(str(error)) from error


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

def fill_packet_ask_ids(packet, state):
    """Give every ask without a valid finding_id the id of the ask row the loop logged for it, matched on file and
    line, or of an ask row logged here when the loop logged none. A valid id the loop wrote stays. A plan-impact ask
    is not a finding and gets none. An ask whose row cannot be logged gets none, and asks-done reports it. A repeat of
    the same packet keeps the asks saved the first time, so no ask row is logged twice."""
    if state.get("asks"):
        packet["ask"] = state["asks"]
        return

    review_asks.supply_finding_ask_ids(packet["ask"], os.environ.get("CLAUDE_CODE_SESSION_ID", ""), ASK_LOGGER, state)


# ---------- plan-impact ruling ----------

def discuss_commands():
    commands = []
    for by, words in (("user", "the decision in one line"), ("session", "your reason")):
        for decision in ("adopt", "keep"):
            commands.append(f'{REVIEW_FIX_COMMAND} decide {decision} --by {by} --ruling "<{words}>" {PLAN_ARG_NOTE}')
    return commands


def command_decide(argv):
    parser = argument_parser("decide")
    parser.add_argument("decision", choices=sorted(plan_format.DECISION_WORDS))
    parser.add_argument("--ruling", default="")
    parser.add_argument("--plan", default="")
    parser.add_argument("--by", nargs="?", const="", default=None)
    options = parser.parse_args(argv)
    state = read_state()
    held_in_hand_back = []
    if state is None and not review_fix_state_file().exists():
        held_in_hand_back = hand_back_plan_impacts()
    if state is None and not held_in_hand_back:
        state = load_fix_state()
    if state is not None and state.get("stage") != "plan-impact" and not state.get("plan_impact_held"):
        raise UsageError("no plan-impact is waiting in this session's packet, so the commit gate is already clear "
                         "(a `defer` clears it too). Add the ruling under the plan's decision log (`03-decisions.md` "
                         "or `## Plan Deviations`) by hand. `decide` reads the packet state when `packet` ran, "
                         "else this session's hand-back.")
    if options.decision == "discuss":
        return print_action("discuss", "Discuss the plan impact with the user, then run one of these. Do not "
                            "re-dispatch yet.", *discuss_commands(), plan_format.DECIDE_BY_NOTE)
    if not plan_format.is_ruling_by(options.by):
        raise UsageError(f"decide {options.decision} needs --by user or --by session. Usage: `{DECIDE_USAGE}`. "
                         f"{plan_format.DECIDE_BY_NOTE}")
    if not options.ruling.strip():
        raise UsageError(f"decide {options.decision} needs --ruling. Usage: `{DECIDE_USAGE}`.")
    plan_path = pathlib.Path(options.plan) if options.plan else None
    if plan_path is not None and not plan_path.exists():
        raise UsageError(f"--plan {options.plan} does not exist")

    if state is None:
        return decide_from_hand_back(held_in_hand_back, options.decision, options.by, options.ruling, plan_path)
    record_plan_ruling(state, options.decision, options.by, options.ruling, plan_path)


NO_PLAN_LINE = f"No --plan was given. {ADD_DEVIATIONS_LINE}"


def ruling_logged_line(plan_path):
    return f"Recorded in {plan_path} under ## Plan Deviations." if plan_path is not None else NO_PLAN_LINE


def hand_back_plan_impacts():
    """The held plan impacts of this session's latest hand-back for this repo that no ruling settles, read the way the
    commit gate reads them: [] with no session id, no work tree or nothing held."""
    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    repo = script_utils.work_tree_top(".")
    if not session_id or not repo:
        return []
    return handback.unruled_plan_impacts(handback_store.latest_for_repo(session_id, repo))


def write_ruling_entry(decision, by, ruling, plan_path, impact_text):
    """The `## Plan Deviations` entry lines of a plan-impact ruling, appended to plan_path when there is one."""
    choice = plan_format.DECISION_WORDS[decision]
    owner = plan_format.ruling_owner(".", by)
    ruled_at = plan_format.ruled_at_now()
    entry = plan_format.ruling_deviation(None, choice, owner, ruled_at, ruling, impact_text)
    if plan_path is not None:
        plan_format.append_deviation(plan_path, entry)
    return entry


def settle_kept_ruling():
    """Record a `keep` ruling for this session and return the line that says whether the commit gate is clear."""
    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    if not session_id:
        return ("CLAUDE_CODE_SESSION_ID is not set, so the ruling is not recorded and the commit gate still counts the "
                "review as dirty.")
    return record_ruling(session_id, "keep", "The ruling settles the plan impact, so the commit gate counts the "
                         "review as clean.")


def decide_from_hand_back(held, decision, by, ruling, plan_path):
    """`decide` for a run whose packet never went through `packet` (the caller read it through code_wait.py): the
    held plan impacts come from the hand-back store. `keep` records the ruling. `adopt` has no launch state to
    re-dispatch from, so it logs the deviation and sends the caller back to its own review loop."""
    entry = write_ruling_entry(decision, by, ruling, plan_path, handback.held_plan_impact_text(held))
    logged_line = ruling_logged_line(plan_path)
    if decision == "keep":
        return print_action("done", logged_line, *entry,
                            "The plan stays as written: nothing is re-dispatched.", settle_kept_ruling())
    return print_action("stop", logged_line, *entry,
                 "No review-fix launch state exists for this run, so `decide adopt` cannot re-dispatch. Run the review "
                 "again through your own loop (`/code resume`) now that the plan is changed. The commit gate stays "
                 "dirty until it hands back.")


def record_plan_ruling(state, decision, by, ruling, plan_path):
    """Log a plan-impact ruling under ## Plan Deviations (in plan_path, else as lines the session adds) and print the
    re-dispatch."""
    choice = plan_format.DECISION_WORDS[decision]
    entry = write_ruling_entry(decision, by, ruling, plan_path, state["plan_impact"])

    if decision == "keep" and state.pop("plan_impact_held", False):
        keep_line = (APPLIED_KEEP_LINE if state.pop("plan_impact_applied", False)
                     else "The plan stays as written: the held fix is not applied and nothing is re-dispatched.")
        state["stage"] = "done"
        save_fix_state(state)
        mark_line = settle_kept_ruling()
        return print_action(
            "done",
            ruling_logged_line(plan_path),
            *entry,
            keep_line,
            mark_line,
        )
    state.pop("plan_impact_held", None)

    spec = state.get("spec_iter")
    session_note = " The session ruled, not the user." if by == "session" else ""
    lines = [f"plan_impact: RESOLVED - {choice}.{session_note} Ruling: {one_line(ruling)}",
             f"iter={state['iter']}"]
    if spec is not None:
        lines.append(f"spec_iter={spec}")
    carried = state.get("carried_findings") or []
    if carried:
        lines.append(f"{plan_format.CARRIED_FINDINGS_KEY}  # left open by the round the plan impact stopped; "
                     "review them too")
        lines += [f"  - {finding}" for finding in carried]

    state["stage"] = "redispatch"
    save_fix_state(state)
    print_action("redispatch", ruling_logged_line(plan_path), *entry, *redispatch_lines(state, lines))


def redispatch_lines(state, resolved_lines):
    """The re-dispatch after an adopt ruling. With the first run's launch flags on record, the script writes the
    first handoff plus resolved_lines to a file and prints the ready launch line; without them, the session builds
    both by hand."""
    if not state.get("relaunch_args"):
        return [f"Write the first run's handoff plus the lines below to a file, then run `launch` in the background "
                f"with the first run's flags plus `--iter {state['iter']}` and `--handoff <that file>`:",
                *resolved_lines]

    first_handoff_file = review_launch.relaunch_handoff(state["relaunch_args"])
    try:
        first_handoff = first_handoff_file.read_text(encoding="utf-8")
    except OSError as error:
        raise UsageError(f"decide adopt: the first run's handoff {first_handoff_file} cannot be read ({error}). The "
                         "ruling is logged. Write that handoff plus the RESOLVED lines to a file and run `launch` "
                         "with the first run's flags, `--iter` and `--handoff <that file>`") from error

    handoff_file = review_fix_dir() / ADOPT_HANDOFF_NAME
    resolved_text = "\n".join(resolved_lines)
    script_utils.write_text_atomically(handoff_file, f"{first_handoff.rstrip()}\n{resolved_text}\n")
    launch_line = relaunch_line(state, [], handoff_file)
    return [f"The first run's handoff plus the RESOLVED lines are in {handoff_file}. Run this launch line now, in "
            "the background:", launch_line]


def command_defer(argv):
    """/code defers the held plan impacts to phase end: the handoff's one-line RESOLVED row is the ruling, so the
    commit gate stops waiting on them."""
    parser = argument_parser("defer")
    parser.add_argument("handoff")
    options = parser.parse_args(argv)
    handoff_path = pathlib.Path(options.handoff)
    if not handoff_path.is_file():
        raise UsageError(f"defer: {options.handoff} does not exist")

    handoff = handoff_path.read_text(encoding="utf-8")
    if not any(line.strip().startswith(DEFER_LINE_PREFIX) for line in handoff.splitlines()):
        raise UsageError(f"defer: {options.handoff} holds no `{DEFER_LINE}` line. Write it there first.")

    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    if not session_id:
        raise UsageError("defer: CLAUDE_CODE_SESSION_ID is not set, so the deferral cannot be recorded")

    print_action("done", record_ruling(
        session_id, "defer", "The plan impacts wait for phase end, so the commit gate counts the review as clean."))


def record_ruling(session_id, decision, settled_line):
    """Record a plan-impact ruling and credit the tree the ruled hand-back covered, so a commit of that tree passes
    the commit gate however many coders ran since. Returns settled_line, or why the gate still counts the review as
    dirty."""
    handback_store.record(session_id, handback_store.PLAN_RULING, decision=decision)
    refusal, _repo = handback.record_clean_review(session_id)
    if refusal:
        return f"The ruling is recorded, but the commit gate still counts the review as dirty: {refusal}."
    return settled_line


def mark_parse_failed():
    """Saves stage `parse-failed` on the open packet's state. A finished packet keeps its stage, so a stray bad packet
    cannot reopen it."""
    if not review_fix_state_file().exists():
        return
    try:
        state = load_fix_state()
    except UsageError:
        return
    if state.get("stage") in FINISHED_STAGES:
        return
    save_fix_state({**state, "stage": "parse-failed"})


def main():
    arguments = sys.argv[1:]
    handlers = {"packet": command_packet, "launch": command_launch, "escape": command_escape,
                "asks-done": command_asks_done, "decide": command_decide, "defer": command_defer}
    if not arguments or arguments[0] not in handlers:
        print(__doc__)
        return 2
    command = arguments[0]
    try:
        return handlers[command](arguments[1:]) or 0
    except PacketError as error:
        stop_for_parse_failure(error, error.raw)
        mark_parse_failed()
        return 2
    except UsageError as error:
        print_action("stop-usage", f"review_fix.py {command}: {error}", "Fix the call and run it again.")
        return 2


if __name__ == "__main__":
    sys.exit(main())
