"""review_fix_plan_impacts.py: how `review_fix.py packet` presents the plan impacts a review hand-back carries: the
deviation lines for an adopted one, the toolkit-fault lines, and the closing question for a held one."""
import handback
import plan_format
from review_fix_state import ADD_DEVIATIONS_LINE, REVIEW_FIX_COMMAND, print_action, save_fix_state
from script_utils import one_line

PLAN_ARG_NOTE = "--plan <the plan path, when the handoff names one>"
APPLIED_IMPACT_LINE = ("A plan impact that changes an acceptance criterion came from a coder whose edits are already "
                       "in the tree. Keeping the plan as written means reverting those edits; adopting the change "
                       "keeps them.")
APPLIED_KEEP_LINE = ("The plan stays as written: the coder's edits for the held plan impact are in the tree, so revert "
                     "them, and nothing is re-dispatched.")


def plan_impact_question_lines(plan_impact, packet):
    """The lines that tell the session to rule on a plan-impact itself or put one question to the user, depending on
    the criteria owner, and what to run on the answer."""
    return [
        f"When the run has a plan, first run `{plan_format.PLAN_CHECK_OWNER_COMMAND}` and read `owner`. Owner "
        "`session`: rule yourself with `decide ... --by session`, no question. Owner `plan`: rule yourself only while "
        f"{plan_format.PLAN_OWNER_RULE_CONDITION}, else ask the user.",
        "Owner `user`, owner `plan` with that condition not met, or no plan: call AskUserQuestion now. Without "
        "that tool, ask the same question in plain text, list the options numbered, end the turn and wait for the "
        "reply. Do not re-dispatch and do not triage this as an ask. Question: assumed, then found, then what "
        "changes, taken from this block:",
        plan_impact,
        f"Options, in this order: {' / '.join(plan_format.PLAN_IMPACT_OPTIONS)}.",
        "Map the answer, picked or typed (or your own ruling when you rule yourself), to adopt, keep or discuss. "
        "For adopt or keep, put the user's words, or your ruling under `--by session`, in --ruling; for discuss, "
        "run `decide discuss`.",
        f"Then run: {REVIEW_FIX_COMMAND} {plan_format.DECIDE_USAGE_STEM} {PLAN_ARG_NOTE}",
        plan_format.DECIDE_BY_NOTE,
        f"Counters held for the re-dispatch: iter={packet['iter']} "
        f"spec_iter={packet['spec_iter'] if packet['spec_iter'] is not None else 'absent'}",
    ]


def plan_impact_deviation_lines(adopted):
    """The `## Plan Deviations` lines for the plan impacts adopted by rule, no question asked."""
    owner = plan_format.SESSION_RULING_OWNER
    ruled_at = plan_format.ruled_at_now()
    choice = plan_format.DECISION_WORDS["adopt"]
    lines = []
    for impact in adopted:
        ruling = plan_format.below_criteria_ruling(impact["text"])
        lines += plan_format.ruling_deviation(None, choice, owner, ruled_at, ruling, impact["text"])
    return lines


def present_plan_impacts(packet, state):
    """Prints the packet's plan impacts once, after the review result. The loop never stopped for them. An adopted one
    prints as a plan deviation line to add, with no question; a settled adopted one, which an earlier ruling covers,
    prints nothing. A toolkit-cause one prints as a toolkit fault, with no question. The ones that change an
    acceptance criterion go to the user in one closing question; the fix waits for the answer."""
    impacts = packet["plan_impacts"]
    if not impacts:
        return

    adopted = handback.rule_adopted_plan_impacts(packet)
    toolkit = handback.toolkit_plan_impacts(packet)
    held = handback.held_plan_impacts(packet)
    lines = []
    if adopted:
        lines += ["Plan impacts adopted by rule (no acceptance criterion changes, so the code wins; no one was asked). "
                  + ADD_DEVIATIONS_LINE,
                  *plan_impact_deviation_lines(adopted)]
    for impact in toolkit:
        lines += [f"Toolkit fault, not a plan change (the {impact['gate']} {plan_format.cause_stop(impact['cause'])}):",
                  impact["text"]]
    if not held:
        if lines:  # a settled impact alone leaves nothing to show
            print_action("show-plan-impacts", *lines)
        return

    held_text = handback.held_plan_impact_text(held)
    applied = any(impact["applied"] for impact in held)
    state.update({"plan_impact": held_text, "plan_impact_held": True, "plan_impact_applied": applied,
                  "carried_findings": [*handback.carried_findings(packet),
                                       *[f"plan impact: {one_line(impact['text'], None)}" for impact in held]]})
    if state.get("stage") != "asks":
        state["stage"] = "plan-impact"
    save_fix_state(state)
    if applied:
        lines += [APPLIED_IMPACT_LINE, "Ask once, now that the review is done."]
    else:
        lines += ["Plan impacts that change an acceptance criterion stay unapplied until the user signs off. Ask once, "
                  "now that the review is done."]
    lines.append(f"Gate: do not commit yet: {len(held)} plan impact(s) wait for a ruling, so the commit gate counts "
                 "the review as dirty until `decide` records one.")
    print_action("ask-user-plan-impact", *lines, *plan_impact_question_lines(held_text, packet))
