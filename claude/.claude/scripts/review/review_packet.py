"""The review loop's hand-back packet: the outcome of a loop in the grammar handback.py reads."""

import json
import pathlib
import re
import sys

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPT_DIR.parent / folder) for folder in (".", "review", "lib")]
import full_check
import handback
import script_utils
from review_findings import UNLOCATED, finding_class, finding_file

# The marker before the one edit an accepted ask makes: `... — the question — change: the edit`.
ASK_CHANGE_MARK = re.compile(r"\bchange:", re.I)


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
        "findings_remaining": [],
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
    if outcome["check_changed"]:
        fields["check_changed"] = outcome["check_changed"]
    if outcome["check_rewrote_edited"]:
        fields["check_rewrote_edited"] = outcome["check_rewrote_edited"]
    if outcome["check_created"]:
        fields["check_created"] = outcome["check_created"]
    if outcome.get("tool_fault"):
        fields["tool_fault"] = outcome["tool_fault"]
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
            "skipped_fp": [], "blockers": [reason], "plan_change": [], "asks": [],
            "ask_gates": {}, "ask_ids": {}, "ask_rows": [], "class_closure": "none - the run ended in an error",
            "full_check": "", "full_check_command": "", "full_check_summaries": [], "check_changed": [],
            "check_rewrote_edited": [], "check_created": [],
            "files_touched": sorted(progress["files_touched"]), "nits": [],
            "unreviewed_fix": False, "tool_fault": reason}
