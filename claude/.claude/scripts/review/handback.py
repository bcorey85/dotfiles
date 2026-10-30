#!/usr/bin/env python3
"""handback.py: the one reader of the review-loop hand-back packet. The per-session store is handback_store.py.

  handback.py check < packet            exit 0 and one `ok` line for a packet that parses and validates; exit 1 and the
                                        problems on stderr for a bad one. A packet is one JSON object
  handback.py hook dispatch|handback|ran < hook event JSON
                                        PreToolUse hook. Matcher Agent records each review-loop dispatch; matcher
                                        SubagentHandback validates and records each review-loop hand-back, and denies a
                                        bad packet once per agent so the loop can repair it, denies once a cap-reached
                                        hand-back that is not a no-review run and whose last step is a coder with no
                                        reviewer after it, denies a hand-back (any
                                        status but plan-impact, setup-fault or critical-blocker) when no valid
                                        full-check receipt exists for the tree the loop reviewed
                                        (lib/full_check_receipt; once per code change), denies a hand-back (any
                                        status but plan-impact) whose files_touched names the dispatch prompt's plan
                                        file, denies a hand-back whose packet owes
                                        per-finding rows or a metrics line the loop did not log (a `ledger` row;
                                        it repeats once only: a second hand-back with no new logger call goes
                                        through), and denies any call from an agent whose
                                        report is already stored. `ran` is the PostToolUse hook (matcher
                                        Agent): it records a `dispatch-ran` row for a review-loop dispatch whose
                                        call ran. Any other argument does nothing.

Importers use, among others, parse, validate, load, render, false_clean_reason, fixed_paths and
unreviewed_fix_section; the hook (handle_hook, unchecked_code_reason) is in handback_hook.py. They read
the store (record, latest, hand_back_gap, ended_on_unreviewed_fix, unreviewed_streak) from handback_store and the
finding-id constants from loop_transcript. The store also holds a `stop` row that review_loop_gate.py writes at each
review-loop stop (agent_id, open_dispatches). `latest` keeps the last one after the last dispatch; while it shows
open_dispatches > 0 and no hand-back is current, hand_back_gap returns LOOP_WAITING,
and a later stop with none open, a hand-back or a new dispatch ends the wait. A validated packet's fixed,
skipped_fp, findings_remaining and ask entries are all mappings. The store is keyed by the hook event's session_id,
which is the value of CLAUDE_CODE_SESSION_ID inside a Bash call."""
import json
import pathlib
import re
import secrets
import sys

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / folder) for folder in (".", "../lib")]
import reviewed_tree
import script_utils
from capped_review import CAP_REACHED, DEFERRED, effective_status
from handback_store import (
    LOOP_WAITING,
    NO_DISPATCH,
    REDISPATCHED,
    hand_back_gap,
    latest,
    session_rows,
    settled_stop,
)
from loop_transcript import FINDING_ID_PATTERN, PRINTED_FINDING_ID
from plan_format import PLAN_CHANGE_MARK, plan_impact_cause
from script_utils import first_number, is_blocker, one_line

# The status for a loop that stopped because the fix passes removed the change under review.
FIX_REMOVED_CHANGE = "fix-removed-change"
STATUSES = ["converged", DEFERRED, "plan-impact", "critical-blocker", CAP_REACHED, "setup-fault",
            FIX_REMOVED_CHANGE]
CLEAN_STATUSES = ("converged", DEFERRED)
PACKET_KEYS = ["status", "iter", "spec_iter", "fixed", "skipped_fp", "blockers", "findings_remaining", "plan_impact",
               "ask", "class_closure", "full_check", "full_check_command", "full_check_summary", "full_check_tree",
               "files_touched", "check_changed", "check_rewrote_edited", "check_created", "nit", "load_bearing_clean",
               "tool_fault", "blocked_agents", "scoped_tests", "open_classes",
               "unrun_reviewer"]
# Keys only the review-loop script writes; the reviewer agent's packet template leaves them out.
SCRIPT_PACKET_KEYS = ["plan_impact_cause"]
LIST_KEYS = ["fixed", "skipped_fp", "blockers", "findings_remaining", "ask", "nit", "files_touched", "check_changed",
             "check_rewrote_edited", "check_created", "blocked_agents", "open_classes"]
# The list fields whose every JSON entry is a string.
STRING_LIST_KEYS = ("open_classes",)
# The list fields whose every entry is a mapping, and the text field each entry requires.
ENTRY_TEXT_KEYS = {"fixed": "finding", "skipped_fp": "item", "findings_remaining": "finding", "ask": "question"}
# The file_line of a finding that names no file. Its row takes no line.
UNLOCATED = "unlocated"
# The field each status requires, and the word for its absence. cap-reached says "missing" when the key is absent.
STATUS_REQUIRES = {"plan-impact": ("plan_impact", "empty"), "critical-blocker": ("blockers", "empty"),
                   "setup-fault": ("blockers", "empty"), FIX_REMOVED_CHANGE: ("blockers", "empty"),
                   CAP_REACHED: ("findings_remaining", "empty"),
                   DEFERRED: ("findings_remaining", "missing or empty")}
BLOCKER_STATUSES = {status for status, (field, _) in STATUS_REQUIRES.items() if field == "blockers"}
CLASSES = ["bug", "smell", "duplication", "complexity", "plan-drift", "test-gap", "weak-assertion", "security", "perf",
           "correctness", "docs", "other"]
REVIEW_LOOP = "review-loop"
DEFAULT_GATE = "code-reviewer"


class PacketError(Exception):
    def __init__(self, problems):
        super().__init__("; ".join(problems))
        self.problems = problems
        self.raw = ""


# ---------- parsing ----------

INTEGER_KEYS = ("iter", "spec_iter")


def json_packet_text(message):
    """The message without whitespace around it and without one wrapping code fence, when what is left opens a JSON
    object; None for any other message."""
    text = script_utils.unfenced_text(message)
    return text if text.startswith("{") else None


def json_field_problem_or_text(key, value):
    """(problem, value) of one JSON field: the raw value validate reads (a list stays a list, a scalar becomes text),
    or why the value has the wrong shape."""
    if key in LIST_KEYS:
        if not isinstance(value, list):
            return f"{key} must be a JSON list, not {script_utils.json_type_name(value)}", None
        return None, value
    if isinstance(value, str):
        return None, value
    is_integer = isinstance(value, int) and not isinstance(value, bool)
    if key in INTEGER_KEYS and is_integer:
        return None, str(value)
    allowed = "a JSON string or integer" if key in INTEGER_KEYS else "a JSON string"
    return f"{key} must be {allowed}, not {script_utils.json_type_name(value)}", None


def parse_json_packet(text):
    """The packet's raw fields from a JSON object: each list field as a list, each other field as text."""
    try:
        loaded = json.loads(text)
    except ValueError as error:
        raise PacketError([f"the packet is not valid JSON: {error}"]) from error
    if not isinstance(loaded, dict):
        raise PacketError([f"the packet must be one JSON object, not {script_utils.json_type_name(loaded)}"])
    problems = []
    packet = {}
    trailer = []
    for key, value in loaded.items():
        if key not in PACKET_KEYS and key not in SCRIPT_PACKET_KEYS:
            value_text = value if isinstance(value, str) else json.dumps(value, separators=(",", ":"))
            trailer.append(f"{key}: {value_text}")
            continue
        problem, field_text = json_field_problem_or_text(key, value)
        if problem:
            problems.append(problem)
            continue
        packet[key] = field_text
    if problems:
        raise PacketError(problems)
    packet["trailer"] = "\n".join(trailer)
    return packet


def parse(message):
    """The packet's raw fields, plus `trailer` (the keys outside the packet, one `key: value` line each). The packet is
    one JSON object; any other message is a PacketError."""
    json_text = json_packet_text(message)
    if json_text is None:
        raise PacketError(["the packet must be one JSON object, and the message does not open with `{`"])
    return parse_json_packet(json_text)


# ---------- items ----------

def item_text(item, *keys):
    if isinstance(item, dict):
        return " - ".join(str(item[key]) for key in keys if item.get(key))
    return str(item)


def is_plan_impact_ask(item):
    return any(PLAN_CHANGE_MARK.match(str(item.get(key) or "").lstrip()) for key in ("finding", "question"))


def carried_findings(packet, include_asks=True):
    """What a plan-impact, critical-blocker or cap-reached round leaves open for the next review, one line each: its
    asks (unless the asks route rules them; the plan ruling settles a PLAN-IMPACT ask), its blockers, its remaining
    findings and its closing prose, where the loop lists fix findings it did not dispatch."""
    lines = []
    if include_asks:
        open_asks = [item for item in packet["ask"] if not is_plan_impact_ask(item)]
        for item in open_asks:
            lines.append(f"ask: {one_line(script_utils.ask_text(item), 800)} ({item.get('file_line', '-')})")
    lines += ["blocker: " + one_line(item_text(item, "finding", "file_line"), 800) for item in packet["blockers"]]
    lines += ["finding: " + one_line(item_text(item, "finding", "file_line"), 800)
              for item in packet["findings_remaining"]]
    if packet["trailer"]:
        lines.append("loop note: " + one_line(packet["trailer"], 800))
    return lines


def ask_finding_id(item):
    """The entry's finding_id when it is an id the ledger writer mints (16 lowercase hex chars); otherwise None.
    A placeholder such as "none logged" or "-", or a damaged id, is not an id."""
    finding_id = item.get("finding_id")
    if isinstance(finding_id, str) and FINDING_ID_PATTERN.fullmatch(finding_id.strip()):
        return finding_id.strip()
    return None


def is_same_file(path, logged_path):
    """True when two paths name one file, or one is the other's tail after a `/`: the loop logs the path its command
    line spelled, which may be shorter than the ask's."""
    if not path or not logged_path:
        return False
    return path == logged_path or path.endswith("/" + logged_path) or logged_path.endswith("/" + path)


def claim_logged_ask_id(item, logged_rows):
    """The finding_id of the logged ask row at the ask's file and line, or None. A claimed row leaves logged_rows, so
    two asks never share one id. Each row is {file, line, finding_id}."""
    path, line = script_utils.split_location(item.get("file_line") or "")
    for row in logged_rows:
        if row["line"] == line and is_same_file(path, row["file"]):
            logged_rows.remove(row)
            return row["finding_id"]
    return None


def ask_row_fields(context, item):
    """The log-review-finding fields that an ask's row and its outcome row share. context holds the run's branch, lane,
    scope and iter, and a phase when the run has one (the writer takes phase as a token, so a run with none sends
    none)."""
    path, line = script_utils.split_location(item.get("file_line") or "-")
    location_fields = [f"file={path}"] if path == UNLOCATED else [f"file={path}", f"line={line}"]
    phase_fields = [f"phase={context['phase']}"] if context.get("phase") else []
    return [f"branch={context['branch']}", f"lane={context['lane']}", f"scope={context['scope']}", *phase_fields,
            f"iter={context['iter']}", f"gate={item.get('gate', 'code-reviewer')}", "disposition=ask",
            f"class={item.get('class', 'other')}", *location_fields, "actioned=ask"]


def log_ask_row(logger, context, item, cwd=None):
    """The finding_id that the log helper at `logger` printed for a new ask row, or None when the row was not logged."""
    code, output = script_utils.run_command(["bash", str(logger), "kind=finding", *ask_row_fields(context, item)], cwd)
    printed_ids = PRINTED_FINDING_ID.findall(output)
    return printed_ids[0] if code == 0 and printed_ids else None


def supply_ask_finding_ids(asks, session_id, logger, context, cwd=None):
    """Give every ask in `asks` without a valid finding_id the id of the ask row the loop logged for it (the stop row's
    ask_rows of this session, matched on file and line), or of an ask row logged here when the loop logged none. A
    valid id on an ask stays and its logged row is never given to another ask. An ask whose row cannot be logged gets
    none; the outcome is then logged under a new id. The caller saves the asks so a repeat logs no ask row twice."""
    stop_row = latest(session_id)["stop"] or {}
    written_ids = {ask_finding_id(item) for item in asks}
    logged_rows = [dict(row) for row in stop_row.get("ask_rows") or [] if row["finding_id"] not in written_ids]
    for item in asks:
        if ask_finding_id(item):
            continue

        finding_id = claim_logged_ask_id(item, logged_rows) or log_ask_row(logger, context, item, cwd)
        if finding_id:
            item["finding_id"] = finding_id


def ask_outcome_finding_id(item):
    """(the finding_id an ask's outcome row is logged under, a stderr note or None). A valid id, which the script
    supplied from the ask's logged row, supersedes that row. An ask the script could not match or log has no valid id:
    its outcome row gets a new id in the ledger writer's shape and stands as that ask's only row, so the user's answer
    is never dropped."""
    finding_id = ask_finding_id(item)
    if finding_id is not None:
        return finding_id, None

    new_finding_id = secrets.token_hex(8)
    ignored_value = item.get("finding_id")
    ignored_text = "no finding_id" if ignored_value is None else f"ignored {ignored_value!r}"
    note = f"ask outcome without a valid finding_id ({ignored_text}), logged under new finding_id {new_finding_id}"
    return new_finding_id, note


def entry_paths(item):
    """Every normalized path that a list entry names: its file_line plus each path:line in its finding text."""
    return script_utils.paths_named(item.get("file_line"), item.get("finding"), item.get("item"))


def entry_locations(item):
    """Every (path, line) that a list entry names."""
    finding_text = str(item.get("finding") or "")
    item_summary = str(item.get("item") or "")
    texts = [str(item.get("file_line") or ""), *script_utils.PATH_LINE.findall(finding_text),
             *script_utils.PATH_LINE.findall(item_summary)]
    return [script_utils.split_location(text) for text in texts if text.strip()]


def first_token(text):
    tokens = [token for token in re.split(r"[\s,;|/]+", str(text or "")) if token]
    return tokens[0] if tokens else ""


# ---------- validation ----------

def read_header(raw):
    """(the packet's scalar fields, their problems)."""
    problems = []
    status_words = raw.get("status", "").strip().strip("`'\"").lower().split()
    status = status_words[0] if status_words else ""
    if status not in STATUSES:
        problems.append(f"status is {raw.get('status', 'missing')!r}; want one of {', '.join(STATUSES)}")
    iter_round = first_number(raw.get("iter"))
    if iter_round is None:
        problems.append("iter is missing or has no number")
    spec_iter = first_number(raw.get("spec_iter"))
    if raw.get("spec_iter", "").strip() and spec_iter is None:
        problems.append("spec_iter has no number")

    plan_impact = raw.get("plan_impact", "").strip()
    # The review-loop script one-lines the block and sends its cause; a reviewer agent's block keeps its lines and
    # a block with no cause reads as plan.
    cause = raw.get("plan_impact_cause", "").strip().lower() or plan_impact_cause(plan_impact)
    header = {"status": status, "iter": iter_round, "spec_iter": spec_iter,
              "class_closure": raw.get("class_closure", "").strip(),
              "full_check": raw.get("full_check", "").strip(),
              "full_check_command": raw.get("full_check_command", "").strip(),
              "full_check_summary": raw.get("full_check_summary", "").strip(),
              "full_check_tree": raw.get("full_check_tree", "").strip(),
              "load_bearing_clean": raw.get("load_bearing_clean", "").strip(),
              "tool_fault": raw.get("tool_fault", "").strip(),
              "scoped_tests": raw.get("scoped_tests", "").strip(),
              "unrun_reviewer": raw.get("unrun_reviewer", "").strip(),
              "plan_impact": plan_impact, "plan_impact_cause": cause}
    return header, problems


def normalize_ask(item):
    if not item.get("question"):
        question_source = item.get("finding") or item.get("change")
        if question_source:
            item["question"] = question_source

    item["gate"] = first_token(item.get("gate")) or DEFAULT_GATE

    ask_class = str(item.get("class") or "").strip()
    if ask_class in CLASSES:
        return
    item["class"] = "other"
    if ask_class:
        item["class_raw"] = ask_class


def fill_fixed_finding(item):
    """Gives fixed entry `item` its smell as its finding when it has no finding."""
    if not item.get("finding") and item.get("smell"):
        item["finding"] = item["smell"]


def read_json_entries(key, entries):
    """(the entries of the JSON list field `key`, their problems). A mapping list holds only mappings, each with its
    required text field; the entry is never read as free text. An ask that names no file_line is unlocated. A
    string list holds only strings. Any other list passes as it is."""
    if key in STRING_LIST_KEYS:
        if script_utils.is_string_list(entries):
            return entries, []
        return [], [f"{key} must be a JSON list of strings, not {one_line(json.dumps(entries), 80)!r}"]
    required = ENTRY_TEXT_KEYS.get(key)
    if required is None:
        return entries, []

    items = []
    problems = []
    for position, entry in enumerate(entries):
        if not isinstance(entry, dict):
            problems.append(f"{key}[{position}] must be a JSON object, not {script_utils.json_type_name(entry)}: "
                            f"{one_line(json.dumps(entry), 80)!r}")
            continue

        item = dict(entry)
        if key == "fixed":
            fill_fixed_finding(item)
        if key == "ask":
            normalize_ask(item)
        is_dropped_ask = key == "ask" and item.get("drop_reason")
        if not is_dropped_ask and not str(item.get(required) or "").strip():
            problems.append(f"{key}[{position}] has no {required}: {one_line(json.dumps(entry), 80)!r}")
            continue

        if key == "ask":
            item.setdefault("file_line", UNLOCATED)
        items.append(item)
    return items, problems


def is_askable(item):
    """Whether ask entry `item` holds a question, once normalize_ask has filled it from its finding or its change."""
    return isinstance(item, dict) and bool(item.get("question"))


def drop_unaskable_asks(packet):
    """Removes each ask entry the loop marked with a drop_reason from packet["ask"]. packet["dropped_asks"] holds one
    warning line per dropped entry, its reason and its text, so the rest of the review survives it."""
    askable_asks = [item for item in packet["ask"] if is_askable(item)]
    packet["dropped_asks"] = [dropped_ask_warning(item) for item in packet["ask"] if not is_askable(item)]
    packet["ask"] = askable_asks


def dropped_ask_warning(item):
    return f"{item['drop_reason']}, so it was dropped: {one_line(item.get('text'), 80)!r}"


def print_dropped_asks(packet):
    """Prints the packet's dropped-ask warnings once, before any route. Each command that loads a packet calls it
    right after the load."""
    if not packet["dropped_asks"]:
        return
    print("DROPPED ASKS (tell the user; the review went on without them):")
    for warning in packet["dropped_asks"]:
        print("- " + warning)


def item_problems(packet):
    problems = [f"fixed entry has no finding: {one_line(item, 80)!r}" for item in packet["fixed"]
                if not (isinstance(item, dict) and item.get("finding"))]
    for item in packet["ask"]:
        if not is_askable(item):
            continue
        question = one_line(item.get("question"), 80)
        if not item.get("file_line"):
            problems.append(f"ask entry has no file_line: {question!r}")
        elif not item.get("change"):
            problems.append(f"ask entry has no change, the one edit an accepted answer makes: {question!r}")
    return problems


def status_problems(raw, packet):
    status = packet["status"]
    problems = []
    if "fixed" not in raw and status in CLEAN_STATUSES:
        problems.append("fixed is missing: the packet must always carry fixed, even as []")

    # A blocker left open keeps the commit gate shut, so it never rides out on a status that clears it.
    if status in CLEAN_STATUSES and any(is_blocker(item) for item in packet["findings_remaining"]):
        problems.append(f"status is {status} but findings_remaining holds a blocker: return cap-reached")

    if status in CLEAN_STATUSES and packet["full_check"].startswith(("failed", "setup fault")):
        problems.append(f"status is {status} but full_check is {packet['full_check']!r}: a failed gate returns "
                        "critical-blocker and a gate that could not run returns setup-fault")

    field, absence = STATUS_REQUIRES.get(status, (None, ""))
    if field is None or packet[field]:
        return problems
    if status == CAP_REACHED and field not in raw:
        absence = "missing"
    problems.append(f"status is {status} but {field} is {absence}")
    return problems


def validate(raw):
    """Typed packet from the raw fields. Raises PacketError listing every problem; never guesses a missing field."""
    packet, problems = read_header(raw)

    list_problems = []
    for key in LIST_KEYS:
        packet[key], entry_problems = read_json_entries(key, raw.get(key, []))
        list_problems += entry_problems
    packet["trailer"] = raw.get("trailer", "").strip()

    problems += list_problems + item_problems(packet) + status_problems(raw, packet)
    if problems:
        raise PacketError(problems)

    drop_unaskable_asks(packet)
    return packet


def load(message):
    """parse then validate. PacketError carries the raw message."""
    try:
        return validate(parse(message))
    except PacketError as error:
        error.raw = message
        raise


# ---------- rendering ----------

def receipt_is_missing(closure):
    if not closure:
        return True
    return re.fullmatch(r"(none|n/a)?[\s.]*", closure.strip().lower()) is not None


def remaining_line(item):
    return f"- [{item.get('disposition', 'open')}] {item_text(item, 'finding', 'file_line')}"


def render_items(lines, heading, items, item_line):
    if not items:
        return
    lines.append(f"### {heading}")
    lines += [item_line(item) for item in items]


def fixed_paths(packet):
    """Every path the packet's fixed[] entries name, once each, in order."""
    paths = []
    for item in packet["fixed"]:
        paths += [path for path in entry_paths(item) if path not in paths]
    return paths


def unreviewed_fix_section(packet):
    """The (heading, lines) section for a clean hand-back whose last step was a coder: no reviewer read that fix."""
    named_paths = ", ".join(fixed_paths(packet)) or "none named in fixed[]"
    return ("Last fix not reviewed",
            [f"- No reviewer read the loop's last fixes. Their files are among: {named_paths}",
             "- Review-again is not advised: it ends on an unreviewed fix the same way. Read that diff yourself."])


def full_check_lines(packet):
    """The full check's lines for the user: a check that did not run, ran unverified, ran with no tests because CI runs
    the full suite, or failed as it does without the diff (`pre-existing`), and the files it changed or created."""
    import full_check

    lines = []
    if packet["full_check"].startswith(("not run", "unverified", "pre-existing", full_check.CHECK_ONLY_PASSED)):
        lines.append("Full check: " + packet["full_check"])
    if packet["scoped_tests"]:
        lines.append("Scoped tests after the last fix: " + packet["scoped_tests"])
    if packet["check_changed"]:
        lines.append("Changed by the full check, not by the coder (restore with `git checkout --` or keep): "
                     + ", ".join(packet["check_changed"]))
    if packet["check_rewrote_edited"]:
        lines.append("Hold coder edits and a full check rewrite, so review them (do not restore): "
                     + ", ".join(packet["check_rewrote_edited"]))
    if packet["check_created"]:
        lines.append("Created by the full check, not by the coder (delete or keep): "
                     + ", ".join(packet["check_created"]))
    return lines


def render(packet, skill, sections=()):
    """The user-facing text. `sections` are (heading, lines) pairs placed before the trailer. Fixed findings, nits
    and skipped false positives show as counts only."""
    fixed = packet["fixed"]
    lines = [f"Fixed {len(fixed)}, nits {len(packet['nit'])}, skipped {len(packet['skipped_fp'])}"]

    closure = packet["class_closure"]
    if skill == "review" or closure:
        lines.append(f"Class closure: {closure or 'MISSING'}")
        owes_receipt = bool(fixed) or not closure
        if skill == "review" and packet["status"] == "converged" and owes_receipt and receipt_is_missing(closure):
            lines.append("The class-closure receipt is missing or names no repaired finding. Do not present this "
                         "run as clean.")
    lines += full_check_lines(packet)
    load_bearing = packet["load_bearing_clean"]
    if load_bearing and load_bearing.lower() not in ("none", "omitted"):
        lines.append("Load-bearing: " + load_bearing)

    remaining_heading = "Deferred to branch exit" if packet["status"] == DEFERRED else "Findings remaining"
    render_items(lines, remaining_heading, packet["findings_remaining"], remaining_line)
    render_items(lines, "Blocked agents (not reviewed)", packet["blocked_agents"], lambda entry: f"- {entry}")
    for heading, section_lines in sections:
        lines.append(f"### {heading}")
        lines += section_lines
    if packet["trailer"]:
        lines.append(packet["trailer"])
    return "\n".join(lines)


# ---------- per-session store ----------

def stop_rows_after(session_id, agent_id, since):
    """The stop rows of agent_id written at or after `since`, blocked or not, in append order."""
    if not session_id:
        return []
    try:
        stop_rows = session_rows(session_id, "stop", agent_id)
    except ValueError:
        return []
    return [row for row in stop_rows if row.get("ts", 0) >= since]


def settled_stop_row(session_id, agent_id, since):
    """The newest stop row of agent_id written at or after `since` that the gate did not block, or None. The hand-back
    row lands before the stop row of the same loop, so a reader of the hand-back looks here for the stop that
    follows it."""
    settled = [row for row in stop_rows_after(session_id, agent_id, since) if settled_stop(row)]
    return settled[-1] if settled else None


def stored_effective_status(seen):
    """The effective_status of the hand-back that `latest` returned, read against the work tree now."""
    row = seen["handback"]
    status = row.get("status")
    if status != CAP_REACHED:
        return status

    packet = load(row.get("message", ""))
    return effective_status(packet, seen["dispatch"].get("repo"))


def false_clean_reason(session_id):
    """Why the session's review earns no commit credit, or None when its latest review-loop hand-back is current and
    converged or deferred. Takes the hook event's session_id, the value of CLAUDE_CODE_SESSION_ID in a Bash call. An
    empty session id is refused."""
    return standing_false_clean_reason(latest(session_id))


def standing_false_clean_reason(seen):
    """false_clean_reason of a `latest` or `latest_for_repo` result."""
    gap = hand_back_gap(seen)
    if gap == LOOP_WAITING:
        return "the review-loop is waiting on a background agent or shell it started and has not handed back"
    if seen["handback"] is None:
        return "no review-loop hand-back is stored for this session"
    if gap == NO_DISPATCH:
        return "a hand-back is stored but this session has no review-loop dispatch on record"
    if gap == REDISPATCHED:
        return "the review-loop was dispatched again and has not handed back"
    status = stored_effective_status(seen)
    if status not in CLEAN_STATUSES:
        return f"the latest review-loop hand-back is {status}"
    if seen["handback"].get("no_reviewer"):
        return "the review-loop handed back clean with no reviewer run"
    return None


def record_clean_review(session_id, committing_session=None):
    """Credit the tree of the repo the session's review-loop was dispatched on, when false_clean_reason finds the
    session's review ended clean. The one writer of the reviewed-tree record. The credit goes to committing_session,
    default the reviewing session. Returns (refusal, repo): the refusal text or None, and the repo the stored dispatch
    names (None when it names none, and then no tree is recorded)."""
    reason = false_clean_reason(session_id)
    if reason:
        return reason, None
    repo = latest(session_id)["dispatch"].get("repo")
    if repo:
        reviewed_tree.record_reviewed(committing_session or session_id, repo)
    return None, repo


def command_check():
    message = sys.stdin.read()
    try:
        packet = load(message)
    except PacketError as error:
        print("handback check: the packet does not parse:", file=sys.stderr)
        for problem in error.problems:
            print(f"- {problem}", file=sys.stderr)
        return 1
    print(f"ok: status={packet['status']} fixed={len(packet['fixed'])} ask={len(packet['ask'])}")
    print_dropped_asks(packet)
    return 0


def main(argv):
    if argv[:1] == ["check"]:
        return command_check()
    if argv[:1] == ["hook"]:
        import handback_hook

        return handback_hook.command_hook(argv[1:])
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
