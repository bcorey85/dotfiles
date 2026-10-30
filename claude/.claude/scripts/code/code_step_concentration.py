"""The concentration gate of the refactor closing phase: `skill-done pass` needs the gate evaluated, by a recorded
simplify run (module and trigger) or by the two added-line counts, which this module computes from the branch diff."""
import pathlib
import re
import subprocess

import plan_format
from numstat import added_lines_by_group
from script_utils import git_output
from source_paths import is_counted_source

MODULE_TRIGGER_LINES = 100
BRANCH_TRIGGER_LINES = 300
BRANCH_BASE = pathlib.Path(__file__).resolve().parent.parent / "tools" / "branch-base"
SIMPLIFY_FORM = '--simplify "<module>; <trigger>"'
BASE_FORM = "skill-done pass --base <ref>"
REFACTOR_SKILL = "/refactor +deep"
REFUSAL = "The concentration gate is not evaluated, so the refactor phase is not done. Nothing was changed."


GATE_CRITERION = "Concentration gate evaluated (module dispatched with the trigger named, or both counts stated)"


def names_concentration_gate(text):
    return re.search(r"concentration[\s-]+gate", text, re.I) is not None


def concentration_gate_position(items):
    # The position of the concentration-gate item among the open items, or None when there is none.
    for position, item in enumerate(items):
        if names_concentration_gate(item["text"]):
            return position
    return None


def is_refactor_phase(state):
    return plan_format.closing_skill(state.get("title") or "") == REFACTOR_SKILL


def module_of(path):
    # A module is the directory a file sits in; a file at the repo root is the module ".".
    return str(pathlib.PurePosixPath(path).parent)


def is_gate_counted(path):
    # Source the gate counts: no test, lockfile or generated file, and nothing under a docs folder (plans, ADRs).
    folders = pathlib.PurePosixPath(path).parts[:-1]
    return is_counted_source(path) and "docs" not in folders


def branch_numstat(repo_dir, base=None):
    # `git diff --numstat -z <base>...HEAD` text against `base` when given, else against the base ref the toolkit's
    # branch-base resolver names; None when there is none or git fails.
    if base:
        return git_output(repo_dir, "diff", "--numstat", "-z", "--no-renames", f"{base}...HEAD")

    try:
        resolved = subprocess.run([str(BRANCH_BASE)], cwd=repo_dir, stdin=subprocess.DEVNULL, capture_output=True,
                                  text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None

    words = resolved.stdout.split()
    if resolved.returncode != 0 or not words:
        return None

    return git_output(repo_dir, "diff", "--numstat", "-z", "--no-renames", f"{words[0]}...HEAD")


def concentration_gate(repo_dir, base=None):
    """{"module", "largest", "branch", "trigger"} for the branch diff, or None when no base ref exists. `trigger` is
    "concentrated", "distributed" or None."""
    numstat_text = branch_numstat(repo_dir, base)
    if numstat_text is None:
        return None

    by_module = added_lines_by_group(numstat_text, module_of, lambda path: not is_gate_counted(path))
    module, largest = max(by_module.items(), key=lambda pair: pair[1], default=("-", 0))
    branch = sum(by_module.values())
    trigger = None
    if largest >= MODULE_TRIGGER_LINES:
        trigger = "concentrated"
    elif branch >= BRANCH_TRIGGER_LINES:
        trigger = "distributed"
    return {"module": module, "largest": largest, "branch": branch, "trigger": trigger}


def gate_lines(gate):
    # The report the phase prompt and the refusal print.
    if gate is None:
        return ["Concentration gate: no base branch found, so the counts cannot be computed. Ask the user for a base "
                f"branch, then run `{BASE_FORM}`; do not run simplify on an unknown module."]
    counts = (f"largest module {gate['module']} {gate['largest']} added lines (trigger {MODULE_TRIGGER_LINES}), "
              f"branch {gate['branch']} added lines (trigger {BRANCH_TRIGGER_LINES})")
    if gate["trigger"] is None:
        return [f"Concentration gate: {counts}. Not triggered: no simplify run needed."]
    return [f"Concentration gate: {counts}. TRIGGERED ({gate['trigger']}): run `/refactor simplify {gate['module']}` "
            "on that one module."]


def simplify_option(gate):
    # The option the gate needs on `skill-done pass`: `--base` when no base was found, `--simplify` when triggered,
    # "" when the gate needs none.
    if gate is None:
        return " --base <ref>"

    if gate["trigger"] is None:
        return ""

    return f' --simplify "{gate["module"]}; {gate["trigger"]}"'


def simplify_record_parts(record):
    # "<module>; <trigger>": split on the first ";", each part stripped.
    module, _separator, trigger = record.partition(";")
    return module.strip(), trigger.strip()


def simplify_done_text(record):
    module, trigger = simplify_record_parts(record)
    return f"simplify {module} ({trigger})"


def is_simplify_record(record):
    # Both parts of `<module>; <trigger>` non-empty.
    module, trigger = simplify_record_parts(record)
    return bool(module and trigger)


def wrong_module_lines(gate, simplify_records):
    # The refusal when the gate triggered and a record names another module than the one the gate computed.
    if gate["trigger"] is None:
        return []

    named = [simplify_record_parts(record)[0] for record in simplify_records]
    if all(module == gate["module"] for module in named):
        return []

    return ["The --simplify module is not the one the gate named, so the refactor phase is not done. Nothing was "
            "changed.",
            f"Expected module: `{gate['module']}`. Run `/refactor simplify {gate['module']}`, then repeat "
            f"`skill-done pass` with `{simplify_option(gate).strip()}`."]


def missing_gate_item_lines(rerun_command):
    # The stop when a simplify record has no open concentration-gate item. A triggered gate (`rerun_command` is the
    # `skill-done pass` that was refused) cannot close without the record, so the stop names the criterion to add and
    # the same command to rerun; a gate that did not trigger needs no record.
    head = "The phase has no open concentration-gate item, so the simplify record has nowhere to go. Nothing was " \
           "changed and the phase stays open."
    if rerun_command is None:
        return [head, "Run `skill-done pass` again without `--simplify`."]

    return [
        head,
        "The gate triggered, so the phase needs the criterion. Add this line to the phase's Success Criteria in the "
        "plan (or change its `[x]` back to `[ ]`):",
        f"- [ ] {GATE_CRITERION}",
        f"Then rerun `{rerun_command}` with one `--evidence` per open item, including the new one.",
    ]


def gate_stop_lines(gate, simplify_records):
    """[] when the gate is evaluated: not triggered, or a well-formed simplify record naming the module the gate
    computed. Otherwise the refusal lines. `gate` is the result of `concentration_gate`."""
    if simplify_records and not all(is_simplify_record(record) for record in simplify_records):
        return ["Malformed --simplify record, so the refactor phase is not done. Nothing was changed.",
                f"Expected form: `{SIMPLIFY_FORM}`, the module you ran simplify on and the trigger that named it."]

    if gate is None:
        return [REFUSAL, *gate_lines(None)]

    if simplify_records:
        return wrong_module_lines(gate, simplify_records)

    if gate["trigger"] is None:
        return []

    return [
        REFUSAL,
        *gate_lines(gate),
        f"Run `/refactor simplify <module>`, then repeat `skill-done pass` with `{SIMPLIFY_FORM}` "
        "(the module you ran it on and the trigger that named it).",
    ]


def manual_gate_item_end(plan_lines, phase):
    # The line index after the phase's open Manual Verification item that names the concentration gate (after its
    # indented continuation lines), or None when there is none. A plan may fold the gate into such an item.
    for item in plan_format.manual_verification("\n".join(plan_lines)):
        if item["phase"] != phase or item["checked"] or not names_concentration_gate(item["text"]):
            continue

        end = item["line"]
        while end < len(plan_lines) and plan_lines[end].strip() and plan_lines[end][0] in " \t":
            end += 1
        return end
    return None


def with_manual_gate_lines(plan_lines, shifted_items, manual_gate_end, simplify_done_texts):
    # `plan_lines` with a Done line per simplify text under the Manual Verification gate item, its box left open for
    # the person, and the open items moved past the inserted lines.
    simplify_lines = [f"  - Done: {text}" for text in simplify_done_texts]
    written = plan_lines[:manual_gate_end] + simplify_lines + plan_lines[manual_gate_end:]

    moved_by = len(simplify_lines)
    moved_items = [item if item["index"] < manual_gate_end
                   else {**item, "index": item["index"] + moved_by, "end": item["end"] + moved_by}
                   for item in shifted_items]
    return written, moved_items
