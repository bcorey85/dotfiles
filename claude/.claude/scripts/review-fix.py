#!/usr/bin/env python3
"""review-fix.py: the fixed steps of /review and /fix as a script. The main session dispatches review-loop, runs
`packet`, and does exactly what the ACTION lines say. The script reads the packet through handback.py, routes on status,
renders the packet, logs the rows, posts the Aikido replies, and prints what the model still judges.

  review-fix.py packet --skill review|fix [options] [< packet]
      --scope branch-exit|standalone   scope of the ask rows (review passes branch-exit when it dispatched with base=)
      --lane eng-spec|code|other|none  lane of the ask and escape rows (default none for review, code for fix)
      --source conversation|cc|handoff (fix) where the findings came from; escapes log only for conversation
      --escape "file=<p>|class=<c>|severity=<s>|gate_missed=<g>|guard=<r>|desc=<one line>"   (fix, repeatable)
      --aikido "<path>:<line>=<comment_id>"                                                 (fix, repeatable)
      With empty stdin, `packet` reads this session's latest review-loop hand-back, which handback.py's hook stored,
      and refuses when the session has no dispatch on record. When the loop ended without handing back, it prints
      `ACTION: stop-no-handback` and leaves the saved state alone: re-dispatch once, then stop and show the user the
      loop's final text on a second miss.
      A re-run on the same hand-back (the same stored row; the same text, for a packet on stdin) repeats no side
      effect: posted replies, logged escapes and the nvim-jump are kept in the state. Two dispatches that return the
      same text are two runs.
  review-fix.py escape --escape "..."...   log escape rows from the saved packet state (fix, repeatable)
  review-fix.py asks-done <outcome>...   one outcome per ask, in order: accepted | rejected | modified, optional
                                         ":<one line note>" after it. Logs one row per ask, once.
  review-fix.py decide <adopt|keep> --by <user|session> --ruling "<the words>" [--plan <path>]
                                         Only --by user is the user's own word.
  review-fix.py decide discuss          print the decide commands for a plan-impact ruling and record nothing.

State lives in <git dir>/review-fix/state.json. A packet that does not parse stops with exit 2 and an instruction to
mark the gate dirty. Env REVIEW_FIX_CLAUDE_DIR overrides ~/.claude; REVIEW_FIX_NVIM_JUMP and REVIEW_FIX_GH override
the nvim-jump and gh commands; HANDBACK_STORE_DIR overrides the hand-back store; CLAUDE_CODE_SESSION_ID names the
session."""
import argparse
import datetime
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import handback  # noqa: E402
import script_utils  # noqa: E402
from handback import CLASSES, PacketError, item_field, item_text  # noqa: E402
from script_utils import one_line, split_location  # noqa: E402

CLAUDE_DIR = pathlib.Path(os.environ.get("REVIEW_FIX_CLAUDE_DIR", pathlib.Path.home() / ".claude"))
SEVERITIES = ["high", "medium", "low"]
GATES_MISSED = ["review", "drift-gate", "test-intent", "stage", "coder", "eng-spec"]
GUARDS = ["type", "convention", "gotcha", "rule", "check", "none", "n-a"]
LANES = ["eng-spec", "code", "other", "none"]
SOURCES = ["conversation", "cc", "handoff"]
ASK_OUTCOMES = ["accepted", "rejected", "modified"]
PLAN_IMPACT_OPTIONS = ["Adopt plan change", "Keep plan as written", "Discuss"]
DECISION_WORDS = {"adopt": PLAN_IMPACT_OPTIONS[0], "keep": PLAN_IMPACT_OPTIONS[1], "discuss": PLAN_IMPACT_OPTIONS[2]}
DECIDE_SCRIPT = "python3 ~/.claude/scripts/review-fix.py"
PLAN_ARG_NOTE = "--plan <the plan path, when the handoff names one>"
DECIDE_USAGE = f'decide <adopt|keep> --by <user|session> --ruling "<the user\'s answer>" {PLAN_ARG_NOTE}'
DECIDE_BY_NOTE = ("If the user told you to make the call yourself, or you rule without asking, pass `--by session` in "
                  "place of `--by user`. A session ruling never changes the acceptance criteria.")
MARK_CLEAN = "~/.claude/scripts/review-gate-mark clean"
MARK_DIRTY = "~/.claude/scripts/review-gate-mark dirty"
NOTHING_OUTSTANDING = "No issues found that warrant auto-fix. Ready for `/commit`."
CODE_STEP_HOOK_STAGES = ("coder", "review", "asks-coder")
FINISHED_STAGES = ("done", "redispatch")
PLAN_IMPACT_PREFIX = "PLAN-IMPACT"
VERBS = ("packet", "escape", "asks-done", "decide")


class UsageError(Exception):
    pass


class NoHandback(Exception):
    """The review-loop was dispatched and ended without calling SubagentHandback."""
    def __init__(self, lastHandBackId):
        super().__init__("dispatched, no hand-back since " + lastHandBackId)
        self.last_hand_back_id = lastHandBackId


# ---------- shell helpers ----------

def run_command(command, cwd=None):
    try:
        done = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    except FileNotFoundError:
        return 127, f"{command[0]}: command not found"
    return done.returncode, (done.stdout + done.stderr).strip()


def git_output(*args):
    code, output = run_command(["git", *args])
    return output if code == 0 else None


def repo_name():
    root = git_output("rev-parse", "--show-toplevel")
    if root is None:
        raise UsageError("not inside a git repo")
    return pathlib.Path(root).name


def review_fix_dir():
    found = git_output("rev-parse", "--path-format=absolute", "--git-path", "review-fix")
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


def load_state():
    path = state_file()
    if not path.exists():
        raise UsageError("no packet was processed yet. Run `packet` first.")
    state = read_state()
    if state is None:
        raise UsageError(f"{path} is not readable JSON")
    return state


def save_state(state):
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
    for name, allowed in (("class", CLASSES), ("severity", SEVERITIES), ("gate_missed", GATES_MISSED),
                          ("guard", GUARDS)):
        if fields[name] not in allowed:
            raise UsageError(f"--escape {name}={fields[name]!r} is not one of {'|'.join(allowed)}")
    extra = sorted(set(fields) - {"file", "class", "severity", "gate_missed", "guard", "desc", "lane"})
    if extra:
        raise UsageError(f"--escape has unknown keys: {', '.join(extra)}")
    if fields.get("lane") and fields["lane"] not in LANES:
        raise UsageError(f"--escape lane={fields['lane']!r} is not one of {'|'.join(LANES)}")
    return fields


def parse_aikido(spec):
    target, separator, commentId = spec.rpartition("=")
    path, line = split_location(target)
    if not separator or not path or not line or not commentId.strip().isdigit():
        raise UsageError(f"--aikido {spec!r} is not <path>:<line>=<numeric comment id>")
    return {"path": path, "line": line, "comment_id": commentId.strip()}


def argument_parser(name):
    parser = argparse.ArgumentParser(prog=f"review-fix.py {name}", add_help=False)
    parser.error = lambda message: (_ for _ in ()).throw(UsageError(message))
    return parser


def packet_arguments(argv):
    parser = argument_parser("packet")
    parser.add_argument("--skill", required=True, choices=["review", "fix"])
    parser.add_argument("--scope", default="standalone", choices=["branch-exit", "standalone"])
    parser.add_argument("--lane", choices=LANES)
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
    return any(packet[key] for key in ("fixed", "ask", "skipped_fp", "nit", "perf", "findings_remaining"))


def print_user_block(text):
    print("-----BEGIN USER TEXT (paste verbatim)-----")
    print(text)
    print("-----END USER TEXT-----")


def emit(action, *lines):
    print(f"ACTION: {action}")
    for line in lines:
        print(line)


def stop_for_parse_failure(error, rawMessage):
    emit("stop-parse-failure",
         "The review-loop packet did not parse. Nothing was routed, logged or posted.",
         *[f"- {problem}" for problem in error.problems],
         f"If you ran `{MARK_CLEAN}` alongside this call, run `{MARK_DIRTY}` now as its own Bash command.",
         "Then show the user the raw packet and the problems above. Do not guess the missing fields.",
         "Do not re-dispatch to repair the packet unless the user asks.")
    print("RAW PACKET (first 1500 chars):")
    print(rawMessage[:1500])


def count_hand_back_miss(skill, lastHandBackId):
    """Misses of this caller since the session's last hand-back. /review and /fix each keep their own count; a new
    hand-back starts it again."""
    path = review_fix_dir() / "misses.json"
    try:
        misses = json.loads(path.read_text())
    except (OSError, ValueError):
        misses = {}
    entry = misses.get(skill) or {}
    count = (entry.get("count", 0) if entry.get("since") == lastHandBackId else 0) + 1
    misses[skill] = {"since": lastHandBackId, "count": count}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(misses))
    return count


def stop_for_missing_hand_back(skill, lastHandBackId):
    """The loop ended without calling SubagentHandback. The saved stage of any earlier run is left alone."""
    misses = count_hand_back_miss(skill, lastHandBackId)
    keepDirty = f"If you ran `{MARK_CLEAN}` alongside this call, run `{MARK_DIRTY}` now as its own Bash command."
    if misses < 2:
        emit("stop-no-handback",
             "The review-loop ended without calling SubagentHandback, so no packet is stored. Nothing was routed, "
             "logged or posted, and the earlier run's state is untouched.",
             "Re-dispatch review-loop once with the same arguments, then run `packet` again.",
             keepDirty)
        return
    emit("stop-no-handback",
         f"The review-loop ended {misses} times in a row without calling SubagentHandback. Nothing was routed, "
         "logged or posted, and the earlier run's state is untouched.",
         "Stop. Do not re-dispatch again. Show the user the loop's final text as it returned.",
         keepDirty)


def present_plan_impact(packet, state):
    state.update({"stage": "plan-impact", "plan_impact": packet["plan_impact"]})
    save_state(state)
    emit("ask-user-plan-impact",
         "Call AskUserQuestion now. Do not re-dispatch and do not triage this as an ask. Question: assumed, then "
         "found, then what changes, taken from this block:",
         packet["plan_impact"],
         f"Options, in this order: {' / '.join(PLAN_IMPACT_OPTIONS)}.",
         f"Then run: {DECIDE_SCRIPT} decide <adopt|keep> --by user --ruling \"<the user's answer>\" "
         f"{PLAN_ARG_NOTE}",
         DECIDE_BY_NOTE,
         f"Counters held for the re-dispatch: iter={packet['iter']} spec_iter={packet['spec_iter'] if packet['spec_iter'] is not None else 'absent'}")


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


def present_asks(packet, state):
    asks = packet["ask"]
    if "jumped" not in state:
        state["jumped"] = run_nvim_jump(asks)
    state.update({"stage": "asks", "asks": asks})
    save_state(state)
    lines = [f"The script ran nvim-jump for all asks ({state['jumped']}). Do not run it again.",
             "Present each ask below with its question and wait for the user's direction. Never auto-fix an ask.",
             f"After the user answers, run once: python3 ~/.claude/scripts/review-fix.py asks-done "
             f"<outcome> x{len(asks)}  (accepted | rejected | modified, optional ':<one line note>')",
             gate_mark_line()]
    for number, item in enumerate(asks, 1):
        askClass = item["class"] + (f" (was {item['class_raw']})" if item.get("class_raw") else "")
        lines.append(f"{number}. {item.get('file_line') or 'no file:line'}  [{item['gate']}/{askClass}]")
        lines.append(f"   {item['question']}")
    emit("present-asks", *lines)


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
        code, output = run_command(["bash", str(CLAUDE_DIR / "scripts/log-escape"), f"repo={repo_name()}",
                                    "stage_found=walkthrough", f"gate_missed={fields['gate_missed']}",
                                    f"class={fields['class']}", f"severity={fields['severity']}",
                                    f"lane={fields.get('lane') or lane}", f"guard={fields['guard']}",
                                    f"desc={one_line(fields['desc'])}", f"file={file}"])
        if code == 0:
            logged.append(file)
            notes.append(f"escape logged for {file} (guard={fields['guard']})")
        else:
            notes.append(f"escape log FAILED for {file}: {output}. Mention it and continue.")
    save_state(state)
    return notes


def aikido_reply(target, packet):
    where = (script_utils.normalize_path(target["path"]), target["line"])
    named = f"{where[0]}:{where[1]}"
    for item in packet["fixed"]:
        if where in handback.entry_locations(item):
            return f"Fixed — {one_line(item_field(item, 'finding'), 160)}"
    for item in packet["skipped_fp"]:
        if named in item_text(item, "item", "finding", "file_line") or where in handback.entry_locations(item):
            return f"@AikidoSec ignore: {one_line(item_field(item, 'reason', 'no reason given'), 200)}"
    for item in packet["findings_remaining"] + packet["ask"]:
        if where in handback.entry_locations(item):
            reason = item_field(item, "question") or item_field(item, "finding") or "open"
            return f"Not fixed in this pass: {packet['status']} — {one_line(reason, 160)}"
    return f"Not fixed in this pass: {packet['status']} — no matching entry in the packet"


def post_aikido_replies(packet, targets, state):
    """(reply lines for the user text, failure notes). A comment id that got a reply is never posted to again."""
    if not targets:
        return [], []
    posted = state.setdefault("aikido_posted", {})
    pending = [target for target in targets if target["comment_id"] not in posted]
    lines = [f"- {posted[target['comment_id']]} (already posted)" for target in targets if target["comment_id"] in posted]
    if not pending:
        return lines, []
    gh = os.environ.get("REVIEW_FIX_GH", "gh")
    codeRepo, repoSlug = run_command([gh, "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"])
    codePr, prNumber = run_command([gh, "pr", "view", "--json", "number", "--jq", ".number"])
    if codeRepo != 0 or codePr != 0:
        return lines, [f"Aikido replies NOT posted: gh could not name the repo or PR ({one_line(repoSlug + ' ' + prNumber, 160)}). "
                       "Report it and continue."]
    failures = []
    for target in pending:
        reply = aikido_reply(target, packet)
        code, output = run_command([gh, "api", "--method", "POST",
                                    f"repos/{repoSlug}/pulls/{prNumber}/comments/{target['comment_id']}/replies",
                                    "-f", f"body={reply}"])
        where = f"{target['path']}:{target['line']}"
        if code == 0:
            posted[target["comment_id"]] = f"{where}: {reply}"
            lines.append(f"- {where}: {reply}")
        else:
            failures.append(f"{where} reply FAILED: {one_line(output, 160)}")
    save_state(state)
    return lines, failures


# ---------- the packet ----------

def code_step_state_path():
    found = git_output("rev-parse", "--path-format=absolute", "--git-path", "code-step")
    return None if found is None else pathlib.Path(found) / "state.json"


def active_code_step(sessionId):
    """(state path, stage) of a /code run that owns this session's review hand-backs, else None. A run pinned to a
    different session does not count."""
    path = code_step_state_path()
    if path is None or not path.exists():
        return None
    try:
        codeStep = json.loads(path.read_text())
    except ValueError:
        return None
    if codeStep.get("stage") not in CODE_STEP_HOOK_STAGES:
        return None
    if codeStep.get("sessionId") != sessionId:
        return None
    return path, codeStep["stage"]


def hand_back_id(storedRow, sessionId):
    """The run id of a stored hand-back row; `none:<session>` when the session has no hand-back yet, so sessions in
    one repo never share a miss count."""
    if storedRow is None:
        return f"none:{sessionId}"
    return f"handback:{storedRow.get('agent_id')}:{storedRow.get('ts')}"


def saved_hand_back(sessionId):
    """The latest review-loop hand-back row of this session. Raises NoHandback when the loop was dispatched and never
    handed back."""
    if not sessionId:
        raise PacketError(["the packet on stdin is empty and CLAUDE_CODE_SESSION_ID is not set, so no saved "
                           "hand-back can be looked up"])
    codeStep = active_code_step(sessionId)
    if codeStep:
        raise PacketError([f"a /code run owns this session's review hand-backs (code-step state {codeStep[0]}, stage "
                           f"{codeStep[1]}): its packet goes through code-step.py after-review, not `packet`"])
    seen = handback.latest(sessionId)
    gap = handback.hand_back_gap(seen)
    if gap == handback.NO_DISPATCH:
        raise PacketError([f"this session has no review-loop dispatch on record (session {sessionId}): a hand-back "
                           "from another session or an older run is never taken as current"])
    if gap:
        raise NoHandback(hand_back_id(seen["handback"], sessionId))
    return seen["handback"]


def read_message():
    """(packet text, run id). A saved hand-back is one run per stored row (agent id and time), so two dispatches that
    return the same text are two runs. A packet on stdin has no row: its text hash is the run id."""
    stdinText = "" if sys.stdin.isatty() else sys.stdin.read()
    if stdinText.strip():
        return stdinText, "stdin:" + hashlib.sha1(stdinText.encode("utf-8")).hexdigest()
    sessionId = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    storedRow = saved_hand_back(sessionId)
    return storedRow["message"], hand_back_id(storedRow, sessionId)


def new_state(options, packet, packetId):
    previous = read_state() or {}
    sameRun = previous.get("packet_id") == packetId
    fixedPaths = []
    for item in packet["fixed"]:
        fixedPaths += [path for path in handback.entry_paths(item) if path not in fixedPaths]
    state = {"skill": options.skill, "scope": options.scope, "lane": options.lane, "iter": packet["iter"],
             "spec_iter": packet["spec_iter"], "status": packet["status"], "repo": repo_name(),
             "branch": git_output("branch", "--show-current") or "-", "packet_id": packetId,
             "source": options.source, "fixed_paths": fixedPaths}
    if sameRun:
        for key in ("stage", "asks", "jumped", "aikido_posted", "escapes_logged", "asks_logged", "plan_impact"):
            if key in previous:
                state[key] = previous[key]
    return state


def command_packet(argv):
    options = packet_arguments(argv)
    try:
        message, packetId = read_message()
    except NoHandback as error:
        stop_for_missing_hand_back(options.skill, error.last_hand_back_id)
        return 2
    packet = handback.load(message)
    state = new_state(options, packet, packetId)
    if state.get("stage") in FINISHED_STAGES:
        return emit("done", f"This packet was already processed (stage {state['stage']}). Nothing was logged or "
                    "posted again. Continue from the step the first output named.")
    status = packet["status"]

    if status == "plan-impact":
        return present_plan_impact(packet, state)
    if status in ("critical-blocker", "cap-reached"):
        save_state(state)
        replies, failures = post_aikido_replies(packet, options.aikido_targets, state)
        if status == "critical-blocker":
            emit("stop", "Present these blockers and wait for direction. Do not re-dispatch. Do not run /fix. "
                 "Do not mark the gate.",
                 *["- " + one_line(item_text(item, "finding", "item"), 400) for item in packet["blockers"]])
        else:
            emit("stop", "The review cap was reached. Report these findings; the user decides. Do not "
                 "re-dispatch. Do not run /fix. Do not mark the gate: the session stays dirty, so git commit "
                 "stays blocked.",
                 *["- " + item_text(item, "disposition", "finding", "file_line") for item in packet["findings_remaining"]])
        if replies:
            print("AIKIDO REPLIES POSTED:")
            print("\n".join(replies))
        if failures:
            print("LOGGED / POSTED (mention failures, never block on them):")
            print("\n".join("- " + note for note in failures))
        return

    save_state(state)
    notes = log_escapes(state, options.escapes, options.lane)
    replies, failures = post_aikido_replies(packet, options.aikido_targets, state)
    notes += failures
    if packet["ask"]:
        present_asks(packet, state)
    else:
        emit("render-and-finish", gate_mark_line())
    sections = [("Aikido replies", replies)] if replies else []
    print_user_block(handback.render(packet, options.skill, sections))
    if notes:
        print("LOGGED / POSTED (mention failures, never block on them):")
        print("\n".join("- " + note for note in notes))
    if options.skill == "review" and not is_outstanding(packet):
        print(f"Nothing is outstanding: say \"{NOTHING_OUTSTANDING}\"")
    print("MODEL STILL DOES: " + model_duties(packet, options))


def model_duties(packet, options):
    duties = []
    if packet["ask"]:
        duties.append("present each ask and judge the user's answer")
    if options.skill == "fix":
        duties.append("recommend /eng-spec if a finding needs architectural rethinking")
        if options.source == "conversation" and not options.escapes:
            duties.append("if a fixed finding was a defect in code /review already passed, run "
                          "`review-fix.py escape --escape ...` (class, severity, gate_missed, guard)")
    duties.append("write the closing line to the user; add nothing the block already says")
    return "; ".join(duties) + "."


def command_escape(argv):
    parser = argument_parser("escape")
    parser.add_argument("--escape", action="append", default=[])
    options = parser.parse_args(argv)
    escapes = [parse_escape(spec) for spec in options.escape]
    if not escapes:
        raise UsageError("escape needs at least one --escape")
    state = load_state()
    if state.get("skill") != "fix":
        raise UsageError("escape rows belong to /fix; the saved packet came from /review.")
    emit("done", *["- " + note for note in log_escapes(state, escapes, state["lane"])])


# ---------- asks ----------

def is_plan_impact_ask(item):
    return any(str(item.get(key) or "").lstrip().startswith(PLAN_IMPACT_PREFIX) for key in ("finding", "question"))


def log_ask_outcome(state, item, outcome, note):
    path, line = split_location(item.get("file_line") or "-")
    desc = "ask resolved: " + one_line(note or item["question"], 100)
    if item.get("class_raw"):
        desc += f" [class: {one_line(item['class_raw'], 40)}]"
    return run_command(["bash", str(CLAUDE_DIR / "skills/review/log-review-finding"), "kind=finding",
                        f"repo={state['repo']}", f"branch={state['branch']}", f"lane={state['lane']}",
                        f"scope={state['scope']}", "phase=-", f"iter={state['iter']}", f"gate={item['gate']}",
                        "disposition=ask", f"class={item['class']}", f"file={path}", f"line={line}",
                        "actioned=ask", f"ask_outcome={outcome}", f"desc={desc}"]), path, line


def command_asks_done(argv):
    state = load_state()
    asks = state.get("asks") or []
    if state.get("stage") == "done" and asks:
        return emit("done", "The ask outcomes were already logged. Run nothing more.")
    if state.get("stage") != "asks" or not asks:
        raise UsageError("no asks are waiting. `asks-done` follows a packet that carried ask[] entries.")
    if len(argv) != len(asks):
        raise UsageError(f"{len(asks)} ask(s) waiting but {len(argv)} outcome(s) given")
    outcomes = []
    for word in argv:
        outcome, _, note = word.partition(":")
        if outcome not in ASK_OUTCOMES:
            raise UsageError(f"outcome {word!r} is not one of {'|'.join(ASK_OUTCOMES)}")
        outcomes.append((outcome, note.strip()))
    logged = state.setdefault("asks_logged", [])
    failures = []
    skippedPlanImpact = 0
    for index, (item, (outcome, note)) in enumerate(zip(asks, outcomes)):
        if index in logged:
            continue
        if is_plan_impact_ask(item):
            logged.append(index)
            skippedPlanImpact += 1
            continue
        (code, output), path, line = log_ask_outcome(state, item, outcome, note)
        if code == 0:
            logged.append(index)
        else:
            failures.append(f"{path}:{line}: {one_line(output, 160)}")
    if not failures:
        state["stage"] = "done"
    save_state(state)
    emit("done", f"Logged {len(logged) - skippedPlanImpact} of {len(asks)} ask outcome row(s)." +
         (f" {skippedPlanImpact} plan-impact ask(s) are not logged as findings." if skippedPlanImpact else "") +
         (" Failures (mention, never block; run the same asks-done again to retry only these):" if failures else ""),
         *["- " + failure for failure in failures])
    print("MODEL STILL DOES: act on accepted/modified asks as the user directed (dispatch a coder, or edit in scope).")


# ---------- plan-impact ruling ----------

def append_plan_deviation(planPath, entry):
    path = pathlib.Path(planPath)
    if not path.exists():
        raise UsageError(f"--plan {planPath} does not exist")
    text = path.read_text()
    heading = re.search(r"^## Plan Deviations[ \t]*$", text, re.M)
    if heading is None:
        path.write_text(text.rstrip("\n") + f"\n\n## Plan Deviations\n\n{entry}\n")
        return
    nextHeading = re.search(r"^## ", text[heading.end():], re.M)
    insertAt = heading.end() + nextHeading.start() if nextHeading else len(text)
    path.write_text(text[:insertAt].rstrip("\n") + f"\n{entry}\n" + (("\n" + text[insertAt:]) if nextHeading else ""))


def discuss_commands():
    commands = []
    for by, words in (("user", "the user's answer"), ("session", "your reason")):
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
    state = load_state()
    if state.get("stage") != "plan-impact":
        raise UsageError("no plan-impact is waiting.")
    if options.decision == "discuss":
        return emit("discuss", "Discuss the plan impact with the user, then run one of these. Do not re-dispatch yet.",
                    *discuss_commands(), DECIDE_BY_NOTE)
    if options.by not in ("user", "session"):
        raise UsageError(f"decide {options.decision} needs --by user or --by session. Usage: `{DECIDE_USAGE}`. "
                         f"{DECIDE_BY_NOTE}")
    if not options.ruling.strip():
        raise UsageError(f"decide {options.decision} needs --ruling. Usage: `{DECIDE_USAGE}`.")
    choice = DECISION_WORDS[options.decision]
    if options.by == "session":
        owner = "the session, not the user"
    else:
        identity = git_output("var", "GIT_AUTHOR_IDENT") or ""
        owner = identity.split(" <")[0] or "user"
    today = datetime.date.today().isoformat()
    finding = one_line(state["plan_impact"], 300)
    entry = f"- {today} | {finding} | {choice} | {owner} | {one_line(options.ruling)}"
    if options.plan:
        append_plan_deviation(options.plan, entry)
    spec = state.get("spec_iter")
    sessionNote = " The session ruled, not the user." if options.by == "session" else ""
    lines = [f"plan_impact: RESOLVED - {choice}.{sessionNote} Ruling: {one_line(options.ruling)}",
             f"iter={state['iter']}"]
    if spec is not None:
        lines.append(f"spec_iter={spec}")
    state["stage"] = "redispatch"
    save_state(state)
    emit("redispatch", (f"Recorded in {options.plan} under ## Plan Deviations." if options.plan else
                        "No --plan was given: add this line under ## Plan Deviations in the plan yourself, then continue:"),
         entry,
         "Re-dispatch review-loop (same Agent call, model: \"sonnet\") with the same arguments as the first dispatch "
         "and these lines added, both counters kept:",
         *lines)


def main():
    arguments = sys.argv[1:]
    if not arguments or arguments[0] not in VERBS:
        print(__doc__)
        return 2
    command = arguments[0]
    handlers = {"packet": command_packet, "escape": command_escape, "asks-done": command_asks_done,
                "decide": command_decide}
    try:
        return handlers[command](arguments[1:]) or 0
    except PacketError as error:
        stop_for_parse_failure(error, error.raw)
        try:
            if state_file().exists():
                save_state({**load_state(), "stage": "parse-failed"})
        except UsageError:
            pass
        return 2
    except UsageError as error:
        emit("stop-usage", f"review-fix.py {command}: {error}",
             f"If you ran `{MARK_CLEAN}` alongside this call, run `{MARK_DIRTY}` now. Fix the call and run it again.")
        return 2


if __name__ == "__main__":
    sys.exit(main())
