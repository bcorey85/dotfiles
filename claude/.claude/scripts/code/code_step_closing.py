"""The `skill-done` verb of code_step.py: a failed closing-phase check writes its question.md before it stops."""
import script_utils
from code_step_boundary import command_skill_done, phase_open_items
from code_step_concentration import concentration_gate, gate_stop_lines, is_refactor_phase, simplify_done_text
from code_step_core import emit, restart_instruction, save_state, script_command, stop_with_question


def open_criteria_texts(repo_dir, state):
    # The open Success Criteria lines of the closing phase, or [] when the plan cannot be read.
    plan_path = repo_dir / state["plan"] if state.get("plan") else None
    if plan_path is None or not plan_path.is_file():
        return []
    items, _offset = phase_open_items(plan_path.read_text().split("\n"), state["phase"])
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

    state["stage"] = "stopped"
    save_state(repo_dir, state)
    items = [finding for finding in findings if finding.strip()] or open_criteria_texts(repo_dir, state)
    why = "the closing phase's check failed (a MISSING criterion, or an unmet Success Criteria)."
    next_step = f"once the user rules on the findings and they are fixed, {restart_instruction(state)} to run it again."
    stop_with_question(repo_dir, why, items, next_step,
                       "The closing phase's check failed (a MISSING criterion, or an unmet Success Criteria). "
                       "Do not mark the phase done. Report what failed to the user.")
