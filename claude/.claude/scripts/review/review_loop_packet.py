"""The review loop's hand-back: the packet (one JSON object) handback.py reads, the crash packet, and the rows a
hand-back writes (hand-back store row, stop row, reviewed tree, agent-usage row)."""

import copy
import json
import os
import pathlib
import sys
import time

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / folder) for folder in (".", "../code", "../lib")]
import full_check
import handback
import handback_store
import script_utils
from review_loop_findings import ASK_CHANGE_MARK, UNLOCATED

PLAN_IMPACT_KEYS = ("text", "gate", "ac_change", "cause", "adopted", "applied")
# A pointer ask rides in the packet's ask list with no question, so handback drops it with this reason as its warning.
POINTER_ASK_REASON = "ask only points back to another ask"


def located(finding):
    """The packet's file_line for a finding: the `path:line` the driver parses, or UNLOCATED."""
    return f"{finding.path}:{finding.line}" if finding.path else UNLOCATED


def finding_entry(finding):
    return {"finding": finding.text, "file_line": located(finding)}


def ask_entry(ask, gate, finding_id):
    # The text before the last `change:` marker is the question; the text after it is the edit an accepted answer
    # makes. An ask with no marker carries its own recommended edit, so its whole text is both. An ask that opens
    # with its marker asks its change, and one that ends on an empty marker carries its edit in its question.
    text = ask.text
    question, change = text, text
    change_marks = list(ASK_CHANGE_MARK.finditer(text))
    if change_marks:
        last_mark = change_marks[-1]
        after_mark = text[last_mark.end():].strip()
        before_mark = text[:last_mark.start()].rstrip(" —-")
        question = before_mark or after_mark
        change = after_mark or before_mark

    entry = {"question": question, "file_line": located(ask), "change": change, "gate": gate,
             "class": ask.finding_class}
    if finding_id:
        entry["finding_id"] = finding_id
    return entry


def packet_message(outcome):
    """The outcome as the packet handback.py reads: one JSON object with one key per field. A key the outcome lacks
    reads as empty."""
    outcome = {**EMPTY_OUTCOME, **outcome}
    asks = [ask_entry(ask, outcome["ask_gates"].get(ask, handback.DEFAULT_GATE), outcome["ask_ids"].get(ask))
            for ask in outcome["asks"]]
    pointer_entries = [{"text": ask.text, "file_line": located(ask), "drop_reason": POINTER_ASK_REASON}
                       for ask in outcome["pointer_asks"]]
    asks += pointer_entries

    fields = {
        "status": outcome["status"],
        "iter": outcome["iter"],
        "review_round": outcome["review_round"],
        "fixed": [finding_entry(finding) for finding in outcome["fixed"]],
        "skipped_fp": [{"item": entry["item"].text, "reason": entry["reason"], "file_line": located(entry["item"])}
                       for entry in outcome["skipped_fp"]],
        "blockers": outcome["blockers"],
        "findings_remaining": [{"disposition": "fix", **finding_entry(finding)}
                               for finding in outcome["open_fixes"]],
        "ask": asks,
        "plan_impacts": [{key: entry[key] for key in PLAN_IMPACT_KEYS} for entry in outcome["plan_impacts"]],
        "class_closure": script_utils.one_line(outcome["class_closure"], limit=None),
        "open_classes": outcome["open_classes"],
        "files_touched": outcome["files_touched"],
        "nit": [finding_entry(finding) for finding in outcome["nits"]],
    }
    if outcome["full_check"]:
        fields["full_check"] = outcome["full_check"]
        if outcome["full_check_command"]:
            fields["full_check_command"] = script_utils.one_line(outcome["full_check_command"], limit=None)
        summary = full_check.summary_text(outcome["full_check"], outcome["full_check_summaries"])
        if summary is not None:
            fields["full_check_summary"] = script_utils.one_line(summary, limit=None)
    if outcome["scoped_tests"]:
        fields["scoped_tests"] = script_utils.one_line(outcome["scoped_tests"], limit=None)
    for key in ("check_changed", "check_rewrote_edited", "check_created", "tool_fault"):
        if outcome.get(key):
            fields[key] = outcome[key]
    return json.dumps(fields, ensure_ascii=False)


# Every key of a loop outcome, empty. A crash fills in only what it knows, so a key added here reaches the crash path.
EMPTY_OUTCOME = {
    "status": "", "iter": 0, "review_round": 0, "fixed": [], "skipped_fp": [], "blockers": [], "open_fixes": [],
    "asks": [], "ask_gates": {}, "pointer_asks": [], "ask_ids": {}, "ask_rows": [], "class_closure": "",
    "open_classes": [], "full_check": "", "full_check_command": "", "full_check_summaries": [], "check_changed": [],
    "check_rewrote_edited": [], "check_created": [], "files_touched": [], "nits": [], "unreviewed_fix": False,
    "scoped_tests": "", "tool_fault": "", "plan_impacts": [],
}


def crash_outcome(progress, reason):
    # A crash is a tool fault, not a finding: tool_fault names the failure for the caller.
    fixed = [item for item in progress["fixed"] if item.text.strip()]
    return {**copy.deepcopy(EMPTY_OUTCOME), "status": "critical-blocker", "iter": progress["iter"], "fixed": fixed,
            "blockers": [reason], "class_closure": "none - the run ended in an error",
            "files_touched": sorted(progress["files_touched"]), "tool_fault": reason}


def report_write_failure(what, error):
    print(f"review-loop-script: {what} not written, {type(error).__name__}: {error}", file=sys.stderr)


def write_handback_rows(args, message, status, ask_rows, unreviewed_fix):
    # The driver's skipped re-reviews are its benched routes, so a clean row never sets no_reviewer;
    # a coder pass after the last reviewer round sets unreviewed_fix.
    try:
        handback_store.record_handback(args.session, agent_id=args.agent_id, status=status, problems=[],
                                       message=message, no_reviewer=False,
                                       unreviewed_fix=unreviewed_fix and status in handback.CLEAN_STATUSES)
    except Exception as error:
        report_write_failure("hand-back row", error)
    # The stop row carries the ask rows, so `review_fix.py packet` can give each ask its id.
    try:
        handback_store.record(args.session, "stop", agent_id=args.agent_id or "unknown", ask_rows=list(ask_rows))
    except Exception as error:
        report_write_failure("stop row", error)

    # The /code run that launched this loop can end before the loop hands back, and then nothing records the tree.
    # So the loop records the tree it ended clean on itself, under the commit gate's hand-back rule.
    try:
        reason, reviewed_repo = handback.record_clean_review(args.session)
        if not reason and not reviewed_repo:
            report_write_failure("reviewed tree", ValueError("the stored review dispatch names no repo"))
    except Exception as error:
        report_write_failure("reviewed tree", error)


def write_usage_row(repo, started, calls):
    if not script_utils.telemetry_switch_on():
        return
    usage_file = os.environ.get("AGENT_USAGE_FILE") or pathlib.Path.home() / ".claude" / "agent-usage.jsonl"
    finished_calls = [call for call in calls if call]
    row = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "repo": pathlib.Path(repo).name,
        "agent": handback.REVIEW_LOOP,
        "model": "script",
        "desc": "scripted review loop",
        "tokens": sum(call["tokens"] for call in finished_calls),
        "toolUses": None,
        "durationMs": round((time.time() - started) * 1000),
        "reportChars": None,
        "noResult": None,
        "respKeys": [],
        "driver": "script",
        "calls": len(finished_calls),
    }
    try:
        script_utils.append_jsonl(usage_file, row)
    except OSError as error:
        report_write_failure("agent-usage row", error)
