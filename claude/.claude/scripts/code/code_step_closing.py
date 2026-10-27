"""The `skill-done` verb of code_step.py: a failed closing-phase check writes its question.md before it stops."""
import script_utils
from code_step_boundary import command_skill_done, phase_open_items
from code_step_core import restart_instruction, save_state, stop_with_question


def open_criteria_texts(repo_dir, state):
    # The open Success Criteria lines of the closing phase, or [] when the plan cannot be read.
    plan_path = repo_dir / state["plan"] if state.get("plan") else None
    if plan_path is None or not plan_path.is_file():
        return []
    items, _offset = phase_open_items(plan_path.read_text().split("\n"), state["phase"])
    return [item["text"] for item in items]


def command_skill_done_with_question(repo_dir, state, args):
    # `skill-done fail --finding "<one line>"` names each open finding in question.md. With no --finding, the open
    # Success Criteria lines of the phase are named instead.
    words, findings = script_utils.pop_repeated_option(args, "--finding")
    verdict = words[0].lower() if words else "pass"
    if verdict != "fail":
        return command_skill_done(repo_dir, state, words)

    state["stage"] = "stopped"
    save_state(repo_dir, state)
    items = [finding for finding in findings if finding.strip()] or open_criteria_texts(repo_dir, state)
    why = "the closing phase's check failed (a MISSING criterion, or an unmet Success Criteria)."
    next_step = f"once the user rules on the findings and they are fixed, {restart_instruction(state)} to run it again."
    stop_with_question(repo_dir, why, items, next_step,
                       "The closing phase's check failed (a MISSING criterion, or an unmet Success Criteria). "
                       "Do not mark the phase done. Report what failed to the user.")
