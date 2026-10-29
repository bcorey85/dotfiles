"""The review loop's hand-back: the packet text handback.py reads, the crash packet, and the rows a hand-back
writes (run event, hand-back store row, stop row, reviewed tree, agent-usage row)."""

import json
import os
import pathlib
import sys
import time

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / folder) for folder in (".", "../code", "../lib")]
import code_step_core
import full_check
import handback
import review_loop_gate
import reviewed_tree
import script_utils
from review_loop_findings import ASK_CHANGE_MARK, UNLOCATED, finding_class, finding_file


def located(text):
    """The packet's file_line for a finding text: the `path:line` the driver parses, or UNLOCATED."""
    path, line = finding_file(text)
    return f"{path}:{line}" if path else UNLOCATED


def finding_entry(text):
    return {"finding": text, "file_line": located(text)}


def ask_entry(text, gate, finding_id):
    # The text before the last `change:` marker is the question; the text after it is the edit an accepted answer
    # makes. An ask with no marker carries its own recommended edit, so its whole text is both.
    question, change = text, text
    change_marks = list(ASK_CHANGE_MARK.finditer(text))
    if change_marks:
        last_mark = change_marks[-1]
        question = text[:last_mark.start()].rstrip(" —-")
        change = text[last_mark.end():].strip()

    entry = {"question": question, "file_line": located(text), "change": change, "gate": gate,
             "class": finding_class(text)}
    if finding_id:
        entry["finding_id"] = finding_id
    return entry


def packet_message(outcome):
    """The outcome in the packet grammar handback.py reads: one `key: value` line per field, list fields as JSON."""
    status = "plan-impact" if outcome["status"] == "plan-change" else outcome["status"]
    asks = [ask_entry(text, outcome["ask_gates"].get(text, handback.DEFAULT_GATE), outcome["ask_ids"].get(text))
            for text in outcome["asks"]]
    fields = {
        "status": status,
        "iter": outcome["iter"],
        "fixed": [finding_entry(text) for text in outcome["fixed"]],
        "skipped_fp": [{"item": entry["item"], "reason": entry["reason"], "file_line": located(entry["item"])}
                       for entry in outcome["skipped_fp"]],
        "blockers": outcome["blockers"],
        "findings_remaining": [{"disposition": "fix", **finding_entry(text)} for text in outcome["open_fixes"]],
        "ask": asks,
        "class_closure": script_utils.one_line(outcome["class_closure"], limit=None),
        "files_touched": outcome["files_touched"],
        "nit": [finding_entry(text) for text in outcome["nits"]],
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
    if outcome["plan_change"]:
        fields["plan_impact"] = script_utils.one_line("; ".join(outcome["plan_change"]), limit=None)
    lines = []
    for key, value in fields.items():
        lines.append(f"{key}: {value if isinstance(value, str | int) else json.dumps(value)}")
    return "\n".join(lines)


def crash_outcome(progress, reason):
    # A crash is a tool fault, not a finding: tool_fault tells code_step to offer review-again.
    fixed = [item for item in progress["fixed"] if isinstance(item, str) and item.strip()]
    return {"status": "critical-blocker", "iter": progress["iter"], "fixed": fixed,
            "skipped_fp": [], "blockers": [reason], "plan_change": [], "open_fixes": [], "asks": [],
            "ask_gates": {}, "ask_ids": {}, "ask_rows": [], "class_closure": "none - the run ended in an error",
            "full_check": "", "full_check_command": "", "full_check_summaries": [], "check_changed": [],
            "check_rewrote_edited": [], "check_created": [],
            "files_touched": sorted(progress["files_touched"]), "nits": [],
            "unreviewed_fix": False, "scoped_tests": "", "tool_fault": reason}


def report_write_failure(what, error):
    print(f"review-loop-script: {what} not written, {type(error).__name__}: {error}", file=sys.stderr)


def write_handback_rows(repo, args, message, status, ask_rows, unreviewed_fix):
    # The driver's skipped re-reviews are its benched routes, so a clean row never sets no_reviewer;
    # a coder pass after the last reviewer round sets unreviewed_fix.
    try:
        code_step_core.log_event(repo, args.run_id, "handback", args.session, agent_id=args.agent_id,
                                 agent_type=handback.REVIEW_LOOP, message=message)
    except Exception as error:
        report_write_failure("run event", error)
    try:
        handback.record(args.session, "handback", agent_id=args.agent_id, status=status, problems=[], message=message,
                        no_reviewer=False, unreviewed_fix=unreviewed_fix and status in handback.CLEAN_STATUSES)
    except Exception as error:
        report_write_failure("hand-back row", error)
    review_loop_gate.record_stop({"session_id": args.session, "agent_id": args.agent_id}, 0, ask_rows)

    # The /code run that launched this loop can end before the loop hands back, and then nothing marks the gate. So
    # the loop records the tree it ended clean on itself, under the same rule as `review-gate-mark clean`.
    try:
        if handback.false_clean_reason(args.session) is None:
            reviewed_tree.record_reviewed(args.session, repo)
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
