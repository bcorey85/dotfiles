"""The review statuses that end a code_step run: a tool fault, a critical blocker, a setup fault, an unverified check
and the review cap. Each prints its stop or question; the caller goes on to the asks or the phase end otherwise."""
import script_utils
from code_step_core import (
    REVIEW_AGAIN_INVOKE,
    restart_instruction,
    save_state,
    script_command,
    set_stop,
    stop_with_question,
)
from script_utils import ask_text


def is_capped_review(state):
    return state.get("reviewStatus") == "cap-reached"


def left_findings_open(state):
    # The review ended with findings open (a cap, or a critical blocker with asks): its rulings go to one more review
    # of the whole phase, and the review gate stays dirty until that review ends clean.
    return state.get("reviewStatus") in ("cap-reached", "critical-blocker")


def review_stop_next_step(state):
    # The command after a review stop: the phase started over, once the user has ruled on the findings.
    return f"after the user rules on the findings, {restart_instruction(state)} to start the phase over."


# The statuses that stop on the packet's blockers: (the question, the instruction to the caller).
BLOCKER_STOP_TEXT = {
    "critical-blocker": ("the review found a critical blocker.",
                         "Review found a critical blocker. Present these to the user. Do not mark the phase done."),
    "setup-fault": ("the review's full check could not run here.",
                    "The full check could not run here. This is a toolkit or environment fault, not a code failure. "
                    "Present these to the user. Do not mark the phase done."),
}


def blocker_stop_next_step(state):
    # A critical blocker the user can clear without a code change (a missing tool, a broken environment) goes on with
    # one command: the review runs again on the same diff.
    review_again_command = script_command("review-again")
    return (f"if the blocker is a fault of the environment and the user has fixed it, run `{review_again_command}` to "
            f"review the same diff again. Otherwise {review_stop_next_step(state)}")


def ask_lines(packet):
    # The reviewer's questions for the user, one line each, with the file and line they concern.
    return [f"{script_utils.one_line(ask_text(item), 800)} ({item.get('file_line', '-')})"
            for item in packet.get("ask", [])]


def stop_on_review_status(repo_dir, state, module, packet):
    # True after the stop or question a packet status that ends the run prints. A plan-impact packet is the
    # caller's: it opens the plan-impact modal before this runs.
    # Imported here: review/ joins sys.path when code_step_core loads, which sorted top-level imports would precede.
    import full_check
    status = packet["status"]
    if packet["tool_fault"]:
        set_stop(state, "tool-fault")
        save_state(repo_dir, state)
        stop_with_question(
            repo_dir, "a review call failed, so the review did not finish; it found nothing.",
            [packet["tool_fault"]], f"to run the review again on the same diff, {REVIEW_AGAIN_INVOKE}.",
            "The review did not run to the end: a tool fault, not a finding. Do not mark the phase done.",
            "Tool fault: " + packet["tool_fault"],
            f"To run the review again on the same diff, {REVIEW_AGAIN_INVOKE}.")
        return True
    if status == "critical-blocker" and packet["ask"] and not state.get("blockerCarried"):
        # With asks, the asks route takes the rulings first, as after a cap: the blockers go to the review after it.
        # Only the first blocker stop of a phase takes it, so a preset ruling cannot loop with no human.
        state["blockerCarried"] = True
        state["carriedFindings"] = module.carried_findings(packet, include_asks=False)
        return False
    if status in BLOCKER_STOP_TEXT:
        question, instruction = BLOCKER_STOP_TEXT[status]
        set_stop(state, status)
        save_state(repo_dir, state)

        blocker_lines = ["- " + script_utils.one_line(module.item_text(item, "finding", "file_line"), 800)
                         for item in packet["blockers"]]
        stop_with_question(
            repo_dir, question, [line[2:] for line in blocker_lines], blocker_stop_next_step(state), instruction,
            *blocker_lines, questions=ask_lines(packet))
        return True
    if status in ("converged", "deferred") and full_check.is_unverified(packet["full_check"]):
        # A check that exited 0 printed no test-runner summary, so the check did not show that any test ran: the phase
        # is not verified, so it does not finish.
        set_stop(state, "check-unverified")
        save_state(repo_dir, state)
        check_command = packet["full_check_command"] or "(not named)"
        configured = full_check.configured_check_command(repo_dir)
        if configured:
            # The repo already names its check, so a Quality check line would change nothing: the runner's output
            # is what the toolkit does not recognize.
            why = ("the full check exited 0 and printed no test-runner summary this toolkit recognizes, so the check "
                   "did not show that any test ran.")
            fix = (f"make the configured check (`{configured}`) print its test runner's summary, or add the "
                   "runner's summary format to SUMMARY_LINES in ~/.claude/scripts/lib/test_run_output.py")
        else:
            why = ("the full check exited 0 and printed no test-runner summary, so the check did not show that any "
                   "test ran.")
            fix = "add a Quality check: `<the command that runs the tests>` line to the repo's CLAUDE.md"
        why_sentence = why[0].upper() + why[1:]
        fix_sentence = fix[0].upper() + fix[1:]
        stop_with_question(
            repo_dir, why, [check_command],
            f"{fix}, then run `{script_command('review-again')}` to review the same diff again.",
            f"{why_sentence} The check ran: `{check_command}`. {fix_sentence}, then run "
            "review-again. Do not mark the phase done.",
            questions=ask_lines(packet))
        return True
    if status == "cap-reached":
        # The first cap of a phase sends the open findings to one more review-loop pass with a fresh round budget.
        # With asks, the asks route takes the rulings first. A cap after that pass stops for a restart.
        # The packet's iter stays on the state: the ask rows of this round log it. The next review dispatch resets it.
        is_second_cap = state.get("capCarried", False)
        state["capCarried"] = True
        if packet["ask"] and not is_second_cap:
            state["carriedFindings"] = module.carried_findings(packet, include_asks=False)
            return False

        if is_second_cap:
            set_stop(state)
        else:
            state["carriedFindings"] = module.carried_findings(packet)
            set_stop(state, "cap-reached")

        next_step = review_stop_next_step(state)
        if not is_second_cap:
            next_step = (f"for one more review-loop pass on the same diff, {REVIEW_AGAIN_INVOKE}. "
                         f"Or, {next_step}")
        save_state(repo_dir, state)
        remaining_lines = ["- " + module.item_text(item, "finding", "file_line")
                           for item in packet["findings_remaining"]]
        stop_with_question(
            repo_dir, "the review cap was reached with findings still open.", [line[2:] for line in remaining_lines],
            next_step,
            "The review cap was reached. Report these findings to the user. Do not mark the phase "
            "done. The session stays dirty, so git commit stays blocked.", *remaining_lines,
            questions=ask_lines(packet))
        return True
    return False
