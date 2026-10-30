"""The `skill-done` verb of code_step.py: `pass` writes each open Success Criteria item's evidence into the plan and
ends the phase, and a failed closing-phase check writes its question.md before it stops."""
import plan_format
import script_utils
from code_step_boundary import finish_phase
from code_step_concentration import (
    concentration_gate,
    concentration_gate_position,
    gate_stop_lines,
    is_refactor_phase,
    manual_gate_item_end,
    missing_gate_item_lines,
    simplify_done_text,
    with_manual_gate_lines,
)
from code_step_core import emit, restart_instruction, save_state, script_command, set_stop, stop_with_question


def open_criteria_texts(repo_dir, state):
    # The open Success Criteria lines of the closing phase, or [] when the plan cannot be read.
    plan_path = repo_dir / state.plan if state.plan else None
    if plan_path is None or not plan_path.is_file():
        return []
    items, _offset = phase_open_items(plan_path.read_text().split("\n"), state.phase)
    return [item["text"] for item in items]


def pass_with_concentration_gate(repo_dir, state, words):
    # A refactor phase passes only once its concentration gate is evaluated: `--simplify "<module>; <trigger>"` records
    # a simplify run, and a branch under both triggers needs none.
    if not is_refactor_phase(state):
        return command_skill_done(repo_dir, state, words)

    words, base = script_utils.pop_option(words, "--base")
    rest, simplify_records = script_utils.pop_repeated_option(words, "--simplify")
    gate = concentration_gate(repo_dir, base)
    stop_lines = gate_stop_lines(gate, simplify_records)
    if stop_lines:
        return emit("stop", *stop_lines)

    simplify_done_texts = [simplify_done_text(record) for record in simplify_records]
    triggered = gate["trigger"] is not None
    rerun_command = pass_rerun_command(simplify_records, base) if triggered else None

    return command_skill_done(repo_dir, state, rest, simplify_done_texts, rerun_command)


def pass_rerun_command(simplify_records, base):
    # The `skill-done pass` line as the session gave it, without the `--evidence` values.
    base_option = f" --base {base}" if base else ""
    simplify_options = "".join(f' --simplify "{record}"' for record in simplify_records)
    return script_command(f"skill-done pass{base_option}{simplify_options}")


def command_skill_done_with_question(repo_dir, state, args):
    # `skill-done fail --finding "<one line>"` names each open finding in question.md. With no --finding, the open
    # Success Criteria lines of the phase are named instead.
    words, findings = script_utils.pop_repeated_option(args, "--finding")
    verdict = words[0].lower() if words else "pass"
    if verdict != "fail":
        return pass_with_concentration_gate(repo_dir, state, words)

    set_stop(state)
    save_state(repo_dir, state)
    items = [finding for finding in findings if finding.strip()] or open_criteria_texts(repo_dir, state)
    why = "the closing phase's check failed (a MISSING criterion, or an unmet Success Criteria)."
    next_step = f"once the user rules on the findings and they are fixed, {restart_instruction(state)} to run it again."
    stop_with_question(repo_dir, why, items, next_step,
                       "The closing phase's check failed (a MISSING criterion, or an unmet Success Criteria). "
                       "Do not mark the phase done. Report what failed to the user.")


def evidence_command_shape(item_count):
    # The `skill-done pass` line with one `--evidence` placeholder per open item.
    placeholders = " ".join(f'--evidence "<item {number} evidence>"' for number in range(1, item_count + 1))
    return script_command(f"skill-done pass {placeholders}")


def evidence_request_lines(items):
    # What the session records at `skill-done pass`: each open Success Criteria item, numbered, and the command.
    if not items:
        return []
    numbered_items = [f"{number}. {item['text']}" for number, item in enumerate(items, 1)]
    return [
        "Open Success Criteria items. Give one `--evidence` per item, in this order; the script checks each box and "
        "writes the evidence under it:",
        *numbered_items,
        f"Run `{evidence_command_shape(len(items))}`. Each evidence states what its item asks for, with the numbers "
        "where it asks for counts (for example both concentration-gate counts, the test-audit denominator).",
    ]


def phase_open_items(plan_lines, number):
    # The open Success Criteria items of one phase's section, and the section's first line index in the plan.
    section = plan_format.phase_section(plan_lines, number)
    if section is None:
        return [], 0
    return plan_format.open_success_items(plan_lines[section["start"]:section["end"]]), section["start"]


def with_simplify_lines(items, evidence, simplify_done_texts):
    # `evidence` with each given Done text added as a Done line under the concentration-gate item's evidence.
    if not simplify_done_texts:
        return evidence

    simplify_lines = [f"\n  {plan_format.DONE_PREFIX}{text}" for text in simplify_done_texts]

    gate_position = concentration_gate_position(items)
    combined = list(evidence)
    combined[gate_position] += "".join(simplify_lines)
    return combined


def stop_for_missing_gate_item(items, simplify_done_texts, rerun_command):
    # Emits a stop and returns True when a simplify record has no open concentration-gate item to be written under.
    # `rerun_command` is the refused `skill-done pass` when the gate triggered, else None.
    if not simplify_done_texts or concentration_gate_position(items) is not None:
        return False

    emit("stop", *missing_gate_item_lines(rerun_command))
    return True


def record_closing_evidence(repo_dir, state, evidence, simplify_done_texts, rerun_command):
    # Writes each open item's evidence into the plan, and the simplify Done texts under the concentration-gate item.
    # Returns False, after a stop, when the evidence count does not match the open items or a simplify record has no
    # open concentration-gate item; nothing is written then.
    plan_path = repo_dir / state.plan
    if not plan_path.is_file():
        return True

    plan_lines = plan_path.read_text().split("\n")
    items, offset = phase_open_items(plan_lines, state.phase)

    manual_gate_end = None
    if simplify_done_texts and concentration_gate_position(items) is None:
        manual_gate_end = manual_gate_item_end(plan_lines, state.phase)
    if manual_gate_end is None and stop_for_missing_gate_item(items, simplify_done_texts, rerun_command):
        return False

    if len(items) != len(evidence):
        listing = evidence_request_lines(items) or ["The phase has no open Success Criteria items: run "
                                                    "`skill-done pass` with no `--evidence`."]
        emit("stop", f"skill-done pass got {len(evidence)} --evidence values for {len(items)} open items. Nothing "
             "was changed.", *listing)
        return False

    shifted = [{**item, "index": item["index"] + offset, "end": item["end"] + offset} for item in items]
    if manual_gate_end is not None:
        plan_lines, shifted = with_manual_gate_lines(plan_lines, shifted, manual_gate_end, simplify_done_texts)
        simplify_done_texts = ()
    if not items and manual_gate_end is None:
        return True

    recorded = with_simplify_lines(items, evidence, simplify_done_texts)
    plan_path.write_text("\n".join(plan_format.write_item_evidence(plan_lines, shifted, recorded)))
    return True


def command_skill_done(repo_dir, state, args, simplify_done_texts=(), rerun_command=None):
    words, evidence = script_utils.pop_repeated_option(args, "--evidence")
    verdict = words[0].lower() if words else "pass"
    if verdict not in ("pass", "fail"):
        return emit("stop", "skill-done takes pass or fail.")
    if verdict == "fail":
        set_stop(state)
        save_state(repo_dir, state)
        return emit("stop", "The closing phase's check failed (a MISSING criterion, or an unmet Success Criteria). "
                    "Do not mark the phase done. Report what failed to the user.")
    if not record_closing_evidence(repo_dir, state, evidence, simplify_done_texts, rerun_command):
        return
    finish_phase(repo_dir, state, skip_verification=True)
