#!/usr/bin/env python3
"""capture_packets.py: refresh tests/scripts/fixtures/packets from packets a real producer wrote.

Usage: capture_packets.py store [<handback store dir>]   review-loop hand-backs (and the full-check fields they carry)
       capture_packets.py tree <bench run tree>          coder hand-back reports in the tree's transcripts

The store defaults to the hand-back store (handback_store.store_dir). Categories claim in alphabetical order; each
keeps the shortest packet that fits it and that no earlier category took. A capture is kept as the producer wrote
it, apart from one scrub: a home directory path becomes HOME_PLACEHOLDER. A packet that names a credential word, or
holds a token-like string or an email address, is dropped. The script writes only under the fixtures folder and
prints each file it wrote."""
import pathlib
import sys

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parents[1] / folder) for folder in ("review", "lib", "code")]
import code_step_report
import full_check
import handback
import handback_store
import redact_text
import script_utils

FIXTURES_DIR = pathlib.Path(__file__).resolve().parents[4] / "tests" / "scripts" / "fixtures" / "packets"


def full_check_category(result):
    """`full-check-<passed|failed|unverified|not-run>` for a packet whose full-check result is one of those,
    else None. The check-only pass (`CHECK_ONLY_PASSED`), the pre-existing result and a `setup fault (exit N)`
    result fit no category."""
    if result == full_check.PASSED:
        return "full-check-passed"
    if full_check.is_failure(result):
        return "full-check-failed"
    if full_check.is_unverified(result):
        return "full-check-unverified"
    if full_check.is_not_run(result):
        return "full-check-not-run"
    return None


def review_categories(message):
    """The categories a review-loop hand-back falls in, or [] when it is not one JSON object (the old
    free-text form is being removed) or does not parse."""
    if handback.json_packet_text(message) is None:
        return []

    try:
        packet = handback.load(message)
    except handback.PacketError:
        return []

    status = packet["status"]
    if status == "converged":
        status = "converged-asks" if packet["ask"] else "converged-fixed" if packet["fixed"] else "converged-clean"

    categories = [f"review-loop-{status}"]
    check_category = full_check_category(packet["full_check"])
    if check_category:
        categories.append(check_category)
    return categories


def store_messages(store_dir):
    """Every hand-back message in the store, in file then row order."""
    for session_file in sorted(pathlib.Path(store_dir).glob("*.jsonl")):
        for row in script_utils.read_jsonl(session_file):
            if row.get("kind") == "handback" and isinstance(row.get("message"), str):
                yield row["message"]


def tree_messages(tree):
    """Every SubagentHandback message, and every task notification's hand-back report, in the transcripts under a run
    tree."""
    for transcript in sorted(pathlib.Path(tree).rglob("*.jsonl")):
        for row in script_utils.read_jsonl(transcript):
            report = row.get("handback_report")
            if isinstance(report, dict) and isinstance(report.get("text"), str):
                yield report["text"]

            message = row.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            if not isinstance(content, list):
                continue

            for block in content:
                tool_input = block.get("input") if isinstance(block, dict) else None
                if isinstance(tool_input, dict) and block.get("name") == "SubagentHandback" \
                        and isinstance(tool_input.get("message"), str):
                    yield tool_input["message"]


def coder_categories(message):
    """The categories a coder report falls in, each decided by the reader that owns the line; a report with none of
    them is no coder report."""
    found = {
        "coder-why": bool(code_step_report.why_by_file(message)),
        "coder-plan-impact": code_step_report.has_plan_impact_block(message),
        "coder-open-questions": bool(code_step_report.open_questions(message)),
        "coder-eng-spec": code_step_report.recommends_eng_spec(message),
        "coder-behavior": bool(code_step_report.behavior_lines(message)),
    }
    return [name for name, present in found.items() if present]


def shortest_per_category(messages, categories_of):
    """{category: shortest clean message}, a message used for one category only.
    Categories claim in alphabetical order, so a message that two categories share goes to the first alphabetically."""
    candidates = {}
    for message in messages:
        if redact_text.has_secret(message):
            continue
        for category in categories_of(message):
            candidates.setdefault(category, []).append(message)

    chosen, used = {}, set()
    for category in sorted(candidates):
        for message in sorted(candidates[category], key=len):
            if message not in used:
                chosen[category] = message
                used.add(message)
                break
    return chosen


def write_captures(chosen, out_dir):
    """Write each chosen message, scrubbed, as <category>.txt under out_dir; the files written, in name order."""
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    written = []

    for category, message in sorted(chosen.items()):
        target = out_dir / f"{category}.txt"
        script_utils.write_text_atomically(target, redact_text.scrub(message))
        written.append(target)
    return written


def capture(kind, source, out_dir):
    if kind == "store":
        messages, categories_of = store_messages(source), review_categories
    else:
        messages, categories_of = tree_messages(source), coder_categories

    chosen = shortest_per_category(messages, categories_of)
    return write_captures(chosen, out_dir)


def main(argv):
    kind = argv[1] if len(argv) > 1 else ""
    if kind not in ("store", "tree") or len(argv) > 3 or (kind == "tree" and len(argv) != 3):
        print(__doc__, file=sys.stderr)
        return 2

    source = argv[2] if len(argv) == 3 else handback_store.store_dir()
    written = capture(kind, source, FIXTURES_DIR)

    for target in written:
        print(f"wrote {target}")
    if not written:
        print(f"{source}: no packet fit a category", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
