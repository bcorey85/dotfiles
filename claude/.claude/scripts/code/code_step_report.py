"""Reading a coder hand-back report: plan-impact blocks, why and behavior notes, and change lines."""
import json
import re

import coder_gate
import script_utils

OPEN_QUESTIONS_LINE = re.compile(r"^[ \t>*`_-]*OPEN QUESTIONS[*`_]*:[*`_]*[ \t]*(.*)$", re.M)
UNREADABLE_QUOTE_LIMIT = 120


def open_questions(report):
    # The strings of the report's `OPEN QUESTIONS: <JSON list of strings>` line. `none` or no such line means none. Any
    # other value that is not a JSON list of strings comes back as one flagged item. Only the first such line is read.
    found = OPEN_QUESTIONS_LINE.search(report)
    if not found:
        return []
    value = found.group(1).strip()
    if value.lower() == "none":
        return []
    questions = script_utils.json_string_list(value)
    if questions is not None:
        return questions
    quoted = script_utils.one_line(value, UNREADABLE_QUOTE_LIMIT)
    return [f"the OPEN QUESTIONS line could not be read as a JSON list of strings: {quoted}"]


PLAN_IMPACT_BLOCK_HEADER = "PLAN-IMPACT:\n"
PLAN_IMPACT_HEADER = re.compile(r"^[ \t>*`_-]*PLAN-IMPACT[*`_]*:?[*`_]*[ \t]*$")
PLAN_IMPACT_KEY = re.compile(r"^[ \t>*`_-]*(?:assumed|found|changes|acceptance_criteria)[*`_]*:", re.I)


def plan_impact_body(lines_after_header):
    # The indented lines, or lines that start with one of the three keys, under a PLAN-IMPACT header. Blank lines may
    # sit between the header and the first line.
    body = []
    for later in lines_after_header:
        if not later.strip():
            if body:
                break
            continue
        if later[0] in " \t":
            body.append(later.rstrip())
        elif PLAN_IMPACT_KEY.match(later):
            body.append("  " + later.strip())
        else:
            break
    return body


def plan_impact_block(report):
    # The block is the header line `PLAN-IMPACT:` (bold or backticked is fine) and the lines under it.
    lines = report.splitlines()
    for index, line in enumerate(lines):
        if not PLAN_IMPACT_HEADER.match(line):
            continue
        body = plan_impact_body(lines[index + 1:])
        if body:
            return PLAN_IMPACT_BLOCK_HEADER + "\n".join(body)
    if re.search(r"^PLAN-IMPACT:\s*yes\s*$", report, re.M):
        return "PLAN-IMPACT: yes (block not found in the report; read the report)"
    return None


def has_plan_impact_block(report):
    # True when the report holds a found block, not the `PLAN-IMPACT: yes (block not found…)` fallback.
    block = plan_impact_block(report)
    return block is not None and block.startswith(PLAN_IMPACT_BLOCK_HEADER)


def first_plan_impact(messages):
    for message in messages:
        block = plan_impact_block(message)
        if block:
            return block
    return None


ALREADY_DONE_LINE = re.compile(
    r"^[ \t>*`_-]*ALREADY-DONE[*`_]*:[ \t]*(?:ask[ \t]*)?(\d+)[ \t]*(?:—|–|--?)[ \t]*(.*)$", re.M
)
PASSING_CHECK = re.compile(r"`[^`]+`[ \t]*->[ \t]*exit 0")


def already_done_ask_numbers(repo_dir, report):
    # The numbers of the asks the coder says need no edit. Each one counts only when its ALREADY-DONE line holds nothing
    # but a file:line whose file exists in the repo, or a backticked command that exited 0 (a verify-only ask), a
    # closing period, comma or semicolon aside.
    numbers = set()
    for match in ALREADY_DONE_LINE.finditer(report):
        evidence = match.group(2).strip().rstrip(".,;")

        if PASSING_CHECK.fullmatch(evidence):
            numbers.add(int(match.group(1)))
            continue

        location = script_utils.PATH_LINE.fullmatch(evidence)
        if location and (repo_dir / script_utils.normalize_path(location.group(1))).is_file():
            numbers.add(int(match.group(1)))
    return numbers


def every_accepted_ask_already_done(repo_dir, state, report):
    accepted_asks = state.get("acceptedAsks")
    if not accepted_asks:
        return False

    accepted_ask_numbers = set(range(1, len(accepted_asks) + 1))
    return accepted_ask_numbers <= already_done_ask_numbers(repo_dir, report)


ENG_SPEC_MARKER = "RECOMMEND: eng-spec"
CODER_CHECKS_LINE = "Run the typecheck, and lint and tests for only the files you changed, once, after all edits."


def eng_spec_brief(subject):
    return f"If {subject} turns out architectural, end your report with the line `{ENG_SPEC_MARKER}`."


ENG_SPEC_BRIEF = eng_spec_brief("the task")


def coder_model(modifier):
    return "haiku" if modifier == "+fast" else None


ENG_SPEC_MARKER_LINE = re.compile(r"^[ \t>*`_-]*RECOMMEND[*`_]*:[ \t]*/?eng-spec[*`_.]*[ \t]*$", re.M | re.I)


def recommends_eng_spec(report):
    # Only the marker line the coder brief names escalates; a mention of /eng-spec in free text does not.
    return bool(ENG_SPEC_MARKER_LINE.search(report))


def why_by_file(report):
    grouped = {}
    for match in re.finditer(r"^WHY:\s*`?(\S+?)`?(?::|\s+)(\d+-\d+)\s*[—-]+\s*(.+)$", report, re.M):
        grouped.setdefault(match.group(1), []).append({"lines": match.group(2), "note": match.group(3).strip()})
    return grouped


def behavior_lines(report):
    found = [m.group(1).strip() for m in re.finditer(r"^BEHAVIOR:\s*(.+)$", report, re.M)]
    return [line for line in found if line.lower() != "none"]


def path_suffixes(path, min_parts=2):
    parts = path.split("/")
    return ["/".join(parts[start:]) for start in range(len(parts)) if len(parts) - start >= min(min_parts, len(parts))]


def resolve_report_paths(grouped, files):
    # Re-key a report's per-path dict to the changed files' full paths, matching on trailing path parts.
    resolved = {}
    for report_path, value in grouped.items():
        candidates = [name for name in files if name == report_path or name.endswith("/" + report_path)
                      or report_path.endswith("/" + name)]
        target = candidates[0] if len(candidates) == 1 else report_path
        resolved.setdefault(target, []).extend(value)
    return resolved


def change_line(report, path, files, fallback_behavior, is_new_file=False):
    # A report names a file's change on a bullet that starts with the path (or a trailing part of it).
    # Prose lines that only mention the path, and grouped "Created: a, b" lines, do not count.
    base_name = path.rsplit("/", 1)[-1]
    shares_base_name = any(name != path and name.rsplit("/", 1)[-1] == base_name for name in files)
    suffixes = sorted(path_suffixes(path) + ([] if shares_base_name else [base_name]), key=len, reverse=True)
    for line in report.splitlines():
        if not re.match(r"^\s*[-*]\s", line):
            continue
        body = line.strip().lstrip("-* ").lstrip("`")
        for suffix in suffixes:
            match = re.match(rf"{re.escape(suffix)}`?\s*(?:[:—-]+\s*|\s+)(.+)$", body)
            if match:
                return re.sub(r"\s+", " ", match.group(1).strip())[:160]
    if is_new_file:
        return "new file"
    return fallback_behavior or "changed by the coder"


def gate_results(repo_dir):
    gate_file = coder_gate.gate_path(repo_dir)
    if gate_file is None or not gate_file.exists():
        return None
    return json.loads(gate_file.read_text())


def tests_run_text(gate, state):
    if gate is None or not gate["coders"]:
        return "none"
    parts = []
    for coder in gate["coders"].values():
        outcome_texts = {
            coder_gate.FAILED: f"failed at the hand-back gate ({coder['result']})",
            coder_gate.TIMED_OUT: "timed out at the hand-back gate, no test result",
            coder_gate.SETUP_FAULT: "could not run at the hand-back gate (setup fault), no test result",
            coder_gate.COMMAND_ERROR: "command error at the hand-back gate (missing path), no test result",
            coder_gate.SKIPPED: "skipped, no changed files",
        }
        for command in gate["commands"]:
            outcome = coder.get("commands", {}).get(command, {}).get("outcome")
            parts.append(f"{command} -> {outcome_texts.get(outcome, 'exit 0')}")
    return "; ".join(parts)


def coder_message_without_gate_stamp(message):
    # The coder's own text. The gate's stamp holds command output, which is not the coder's report.
    return script_utils.text_before_marker(message, script_utils.HAND_BACK_GATE_MARKER)
