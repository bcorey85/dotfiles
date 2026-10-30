"""code_step_phase_end.py: the text of the block a run shows when a phase ends: block A auto-advances, block B
asks for sign-off, block C ends the run.

Imports run one way: code_step_phase_end, code_step_boundary."""


def manual_item_line(item):
    return f"- [{'x' if item['checked'] else ' '}] {item['text']}"


def manual_groups_of(manual_items):
    return {
        "verified": [manual_item_line(i) for i in manual_items if i["verified"]],
        "notRun": [manual_item_line(i) for i in manual_items if not i["humanOnly"] and not i["verified"]],
        "humanOnly": [manual_item_line(i) for i in manual_items if i["humanOnly"] and not i["checked"]]}


def block_a(number, risk_label, manual_groups, next_number):
    verified_count, not_run_count, human_count = (
        len(manual_groups[name]) for name in ("verified", "notRun", "humanOnly")
    )
    return (
        f"Phase {number} complete - machine gates green (review ✓, execution ✓, automated-verification ✓). "
        f"Risk: {risk_label}. Manual verification: {verified_count} verified, {not_run_count} agent-run items not "
        f"yet run (/verify-branch runs them at the end of the branch), {human_count} human-only deferred to the "
        f"/verify-branch packet.\n-> Auto-advancing to Phase {next_number} in-session (no /clear; interrupt anytime)."
    )


def block_heading(block, number, risk_label, state, has_open_gate):
    # The first line of block B or C: which phase is complete and why the run stops here.
    if block == "B":
        return f"Phase {number} complete. Risk: {risk_label}. Phase-level sign-off requested."
    if number is None:
        return "The plan is complete."
    if state.only_phase == number:
        return f"Phase {number} complete (the phase this run was started for)."
    # Open gated phases mean the plan is not complete, so this phase is not the last one.
    return f"Phase {number} complete." if has_open_gate else f"Phase {number} complete (last phase)."


def block_sections(state, manual_groups):
    parts = []
    behavior = state.behavior or []
    if behavior:
        parts += ["Behavior delta (observable change + its proof, max 3 - no internals, no paths):",
                  *[f"- {line}" for line in behavior[:3]], ""]
    parts += ["Read first (/stage queue, blast-radius order):", "<<STAGE QUEUE>>", ""]
    if manual_groups["verified"]:
        parts += ["Verified (checked, or marked agent-verified in the plan):", *manual_groups["verified"], ""]
    if manual_groups["notRun"]:
        parts += ["Agent-run, not yet run (/verify-branch runs these at the end of the branch):",
                  *manual_groups["notRun"], ""]
    if manual_groups["humanOnly"]:
        parts += ["Human-only verification remaining:", *manual_groups["humanOnly"], ""]
    return parts


def block_b_next_steps(number, next_number, manual_groups):
    reads_queue = manual_groups["verified"] or manual_groups["humanOnly"]
    queue_steps = ["Read the queue (`]k`/`[k` in nvim)"] if reads_queue else ["Read the /stage queue"]
    if manual_groups["verified"]:
        queue_steps.append("spot-check the verified items")
    if manual_groups["humanOnly"]:
        queue_steps.append("run the human-only items")
    step1 = "; ".join(queue_steps) + "."
    return [
        "Next:",
        f"  1. {step1}",
        f"  2. Stage what you've read, then run /clear and /code to start Phase {next_number} fresh. "
        "To keep this context, confirm here.",
        "",
        "Or give feedback now for revisions to Phase " + number + ".",
    ]


def block_c_next_steps(is_only_phase, gate_block_message, moved_text):
    if is_only_phase:
        return ["This run was started for this phase only. Other phases may be open; run `resume` when the user "
                "asks for the next one."]
    if gate_block_message:
        return [f"No phase starts on its own: {gate_block_message} Tell the user. The plan is not complete."]
    if moved_text:
        return [f"All other phases are complete or moved to another ticket ({moved_text}). Next: /verify-branch "
                "(completeness + review packet; includes the remaining human-only checks), then you open the PR."]
    return ["All phases complete. Next: /verify-branch (completeness + review packet; includes the remaining "
            "human-only checks), then you open the PR."]


def block_b_or_c(block, number, risk_label, state, manual_groups, next_number, gate_block_message="", moved_text=""):
    has_open_gate = number is not None and bool(gate_block_message)
    heading = block_heading(block, number, risk_label, state, has_open_gate)
    parts = [heading, "", *block_sections(state, manual_groups)]
    if block == "B":
        return "\n".join(parts + block_b_next_steps(number, next_number, manual_groups))

    is_only_phase = number is not None and state.only_phase == number
    return "\n".join(parts + block_c_next_steps(is_only_phase, gate_block_message, moved_text))
