"""expected_red.py: a phase's declared expected-red checks, and the files a plan gives only to later phases.

A phase section may hold `Expected red: `<command>` until Phase <id>` lines. <command> is the repo's CLAUDE.md
`Quality check:` command or one `&&` step of it, and it fails until the named later phase lands. While that phase is
open the review's full check runs without it; once it is done, the line has no effect. A line in any other form, a
target that is not a later phase in Phase Status order, or a command that is not the Quality check or one of its
steps fails the plan check.
"""
import re

import plan_format
import script_utils
import shell_command

EXPECTED_RED_START = re.compile(r"^\s*(?:[-*]\s+)?(?:\*\*)?expected red\b", re.I)
EXPECTED_RED_LINE = re.compile(rf"^\s*(?:[-*]\s+)?Expected red:\s*`([^`]+)`\s+until Phase\s+({plan_format.PHASE_ID})"
                               r"\s*\.?\s*$")
EXPECTED_FORM = "Expected red: `<command>` until Phase <id>"
NOT_RUN_PREFIX = "not run (expected red until Phase "
STEP_SEPARATOR = " && "


def declared(plan_lines):
    """(every Expected red line of the plan as {"line", "phase", "command", "until"}, the failures for a line in another
    form or outside a phase section). `line` is 1-based."""
    spans, _ = plan_format.phase_spans(plan_lines)
    fenced = script_utils.fenced_line_indexes(plan_lines)
    entries = []
    failures = []

    for index, line in enumerate(plan_lines):
        if index in fenced or not EXPECTED_RED_START.match(line):
            continue

        holder = next((section_id for section_id, section in spans if section["start"] <= index < section["end"]),
                      None)
        match = EXPECTED_RED_LINE.match(line)
        if not match:
            failures.append({"line": index + 1, "kind": "expected-red-form", "detail": f"{line.strip()!r}. Write it "
                             f"as `{EXPECTED_FORM}`."})
            continue
        if holder is None:
            failures.append({"line": index + 1, "kind": "expected-red-outside-phase", "detail": "An Expected red line "
                             "belongs in the section of the phase whose check it lets fail."})
            continue

        entries.append({"line": index + 1, "phase": holder, "command": match.group(1).strip(),
                        "until": match.group(2)})
    return entries, failures


def plan_failures(plan_lines, quality_check):
    """The failures of the plan's Expected red lines: a line in another form, a target phase that is not in Phase
    Status or not after the phase that holds the line, and a command that is not `quality_check` (the repo's CLAUDE.md
    `Quality check:` command, None when it has none) or one of its `&&` steps."""
    entries, failures = declared(plan_lines)
    order = [entry["number"] for entry in plan_format.parse_plan_with_closing_phases(plan_lines)["entries"]]
    steps = shell_command.and_steps(quality_check) if quality_check else None

    for entry in entries:
        if entry["until"] not in order:
            failures.append({"line": entry["line"], "kind": "expected-red-unknown-phase", "detail": f"Phase "
                             f"{entry['until']} is not in Phase Status. Name the later phase whose change turns "
                             "the check green."})
        elif entry["phase"] not in order or order.index(entry["until"]) <= order.index(entry["phase"]):
            failures.append({"line": entry["line"], "kind": "expected-red-not-later", "detail": f"Phase "
                             f"{entry['until']} does not come after Phase {entry['phase']} in Phase Status. An "
                             "Expected red line names a later phase."})

        if not quality_check:
            failures.append({"line": entry["line"], "kind": "expected-red-no-check", "detail": "The repo's CLAUDE.md "
                             "has no `Quality check:` line, so the review's full check is unknown. Add the line, "
                             "or drop the Expected red line."})
        elif entry["command"] != quality_check.strip() and entry["command"] not in (steps or []):
            failures.append({"line": entry["line"], "kind": "expected-red-not-the-check", "detail": f"`"
                             f"{entry['command']}` is neither the repo's Quality check `{quality_check}` nor one of "
                             "its `&&` steps."})
    return sorted(failures, key=lambda failure: failure["line"])


def failure_rows(plan_lines, quality_check, plan_name):
    return [f"{plan_name}:{failure['line']}: {failure['kind']}: {failure['detail']}"
            for failure in plan_failures(plan_lines, quality_check)]


def active(plan_lines, phase_id):
    """The phase's Expected red entries whose target phase is still open."""
    entries, _ = declared(plan_lines)
    entries = [entry for entry in entries if entry["phase"] == str(phase_id)]
    if not entries:
        return []

    open_ids = {entry["number"] for entry in plan_format.parse_plan_with_closing_phases(plan_lines)["entries"]
                if entry["open"]}
    return [entry for entry in entries if entry["until"] in open_ids]


def check_for_phase(check_command, plan_lines, phase_id):
    """(the command the phase's full check runs, the active Expected red entries it leaves out). The command is None
    when an entry names the whole check, or every step of it. An entry that names neither leaves the check as it is."""
    entries = active(plan_lines, phase_id) if check_command and phase_id is not None else []
    if not entries:
        return check_command, []

    commands = {entry["command"] for entry in entries}
    if check_command.strip() in commands:
        return None, [entry for entry in entries if entry["command"] == check_command.strip()]

    steps = shell_command.and_steps(check_command) or [check_command.strip()]
    kept = [step for step in steps if step not in commands]
    left_out = [entry for entry in entries if entry["command"] in steps]
    if not kept:
        return None, left_out
    return STEP_SEPARATOR.join(kept), left_out


def entry_text(entry):
    return f"`{entry['command']}` until Phase {entry['until']}"


def not_run_result(entries):
    """The full_check result of a check that every active entry leaves out."""
    phases = ", ".join(sorted({entry["until"] for entry in entries}))
    return f"{NOT_RUN_PREFIX}{phases})"


def later_phase_paths(plan_lines, phase_id):
    """The Changes Required file paths of the open phases after this one in Phase Status that this phase's section does
    not name (plan_format.file_entry_paths), sorted. A path both name stays the phase's own."""
    plan = plan_format.parse_plan_with_closing_phases(plan_lines)
    order = [entry["number"] for entry in plan["entries"]]
    if str(phase_id) not in order:
        return []

    later_ids = [entry["number"] for entry in plan["entries"][order.index(str(phase_id)) + 1:] if entry["open"]]
    own_paths = section_paths(plan_lines, plan["sections"].get(str(phase_id)))
    later_paths = set()
    for later_id in later_ids:
        later_paths |= plan_format.file_entry_paths(plan_lines, plan["sections"].get(later_id))
    return sorted(later_paths - own_paths)


def section_paths(plan_lines, section):
    if section is None:
        return set()
    fenced = script_utils.fenced_line_indexes(plan_lines)
    return {match.group(1) for index in range(section["start"], section["end"]) if index not in fenced
            for match in plan_format.PATH_IN_BACKTICKS.finditer(plan_lines[index])}
