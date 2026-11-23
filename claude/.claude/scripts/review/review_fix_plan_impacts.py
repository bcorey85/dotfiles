"""review_fix_plan_impacts.py: how `review_fix.py packet` presents the plan impacts a review hand-back carries: the
deviation lines for an adopted one, the toolkit-fault lines, and the closing question for a held one. It also records
a plan-impact ruling and settles the push check with it: `record_ruling` and `settle_ruling` write the ruling and
credit the covered tree, and return a `Settled` (clean, or why the gate still counts the review as dirty), which
`print_settled` turns into `done` or `stop`. `decide` checks who may rule here: `refuse_session_ruling` for a session
ruling, `verified_decide_relay` for a user ruling another session relays."""
import os
import time
from typing import NamedTuple

import handback
import handback_store
import plan_format
import ruling_relay
import standing_rulings
from human_turn_lookup import HumanTurnRefusedError
from review_fix_asks import required_packet_repo
from review_fix_names import PLAN_IMPACT_FILED_AT_KEY
from review_fix_state import ADD_DEVIATIONS_LINE, REVIEW_FIX_COMMAND, UsageError, print_action, save_fix_state
from script_utils import one_line

APPLIED_IMPACT_LINE = ("A plan impact that changes an acceptance criterion came from a coder whose edits are already "
                       "in the tree. Keeping the plan as written means reverting those edits; adopting the change "
                       "keeps them.")
APPLIED_ADOPT_LINE = ("The plan changes as ruled: the coder's edits for the held plan impact are already in the tree, "
                      "so nothing is re-dispatched and no new review loop runs.")
APPLIED_KEEP_LINE = ("The plan stays as written: the coder's edits for the held plan impact are in the tree, so revert "
                     "them, and nothing is re-dispatched.")

ASKS_STILL_WAIT_LINE = ("The packet's asks still wait: after the user answers them, record them with "
                        f"`{REVIEW_FIX_COMMAND} asks-done`.")


def settle_stage(state, settled_line):
    """Set the stage a settled ruling leaves: `done`, except that the `asks` stage stays while the packet's asks
    wait. Returns the settled line, with the line that names the asks-done command added when the stage stays."""
    if state.get("stage") != "asks":
        state["stage"] = "done"
        return settled_line
    return f"{settled_line} {ASKS_STILL_WAIT_LINE}"


class PlanImpactSource(NamedTuple):
    """Where `decide` reads the plan impact from: the saved packet `state`, or else the `held` impacts and the
    `packet` of this session's latest hand-back (the packet is None when `state` is the source,
    or when the hand-back's packet cannot be read). `filed_at` is the epoch time the impact was filed: the state's
    PLAN_IMPACT_FILED_AT_KEY, or the hand-back's stored time (None when it has none)."""
    state: dict | None
    held: list
    packet: dict | None
    filed_at: float | None


def pop_decide_relay(argv):
    """(the words of a `decide` call without the relay option, RelayRequest or None). Raises UsageError for a bad
    relay option (see ruling_relay.pop_relay_options)."""
    try:
        return ruling_relay.pop_relay_options(argv)
    except ruling_relay.RelayRefusedError as error:
        raise UsageError(f"{ruling_relay.relay_refusal_line(error)}. Nothing was logged.") from error


def verified_decide_relay(relay, by, source):
    """The RelayedRuling of a `decide` call's relay, or None for a call with none. Refuses (UsageError, nothing
    logged) a relay under `--by session`, an impact with no filed time, and a relaying session with no real user
    turn typed after the impact was filed."""
    if relay is None:
        return None
    try:
        ruling_relay.refuse_relay_without_user(relay, by)
        if not isinstance(source.filed_at, (int, float)):
            raise ruling_relay.RelayRefusedError("the plan impact has no filed time, so no user turn can be shown to "
                                                 "come after it. Ask the user to rule from their own session")
        return ruling_relay.verify_relay(relay, source.filed_at)
    except HumanTurnRefusedError as error:
        raise UsageError(f"{ruling_relay.relay_refusal_line(error)}. Nothing was logged.") from error


def refuse_session_ruling(decision, plan_arg):
    """Raises UsageError when the session may not rule: the plan's criteria are the user's, the owner cannot be read,
    or no plan names them. Only the user's word changes a criterion the user owns; with no plan the rules say ask."""
    refusal = f"decide {decision} --by session is refused: "
    must_rule = ("The user must rule: ask the user, then run decide with --by user, or relay the user's ruling "
                 f"with `--by user {ruling_relay.RELAY_USAGE}`.")
    if not plan_arg:
        raise UsageError(f"{refusal}no --plan names the criteria owner. {must_rule}")

    try:
        owner = plan_format.plan_criteria_owner(plan_arg)["owner"]
    except plan_format.PlanFormatError as error:
        raise UsageError(f"{refusal}the criteria owner of {plan_arg} cannot be read ({error}). {must_rule}") from error

    if owner == plan_format.CRITERIA_OWNER_USER:
        raise UsageError(f"{refusal}the criteria owner of {plan_arg} is `{owner}`. {must_rule}")


def relayed_owner(owner, relayed):
    """The `Ruled by` words of a ruling: `owner`, with the relaying session and the time of the user turn that backs
    it when `relayed` is a RelayedRuling."""
    if relayed is None:
        return owner
    return f"{owner}, relayed by session {relayed.request.relayed_by} (user turn at {relayed.turn.timestamp})"


def write_ruling_entry(decision, by, ruling, plan_path, impact_text, ruled_repo, finding_texts=(), relayed=None):
    """The `## Plan Deviations` entry lines of a plan-impact ruling, appended to plan_path when there is one. The ruled
    row goes under `ruled_repo`, the repo the packet answers: one row per accepted finding the ruling covers
    (`finding_texts`), else one row with none. A relayed ruling also stores a PLAN_RULING_RELAYED row."""
    choice = plan_format.DECISION_WORDS[decision]
    owner = relayed_owner(plan_format.ruling_owner(".", by), relayed)
    ruled_at = plan_format.ruled_at_now()
    entry = plan_format.ruling_deviation(None, choice, owner, ruled_at, ruling, impact_text)
    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    for finding_text in finding_texts or [None]:
        handback_store.record_ruled_impact(session_id, impact_text, ruled_repo, finding_text=finding_text,
                                           decision=decision, owner=owner, ruled_at=ruled_at)
    if relayed is not None:
        handback_store.record_relayed_plan_ruling(session_id, ruled_repo, by, relayed.request.relayed_by,
                                                  relayed.turn.timestamp, impact_text)
    if plan_path is not None:
        plan_format.append_deviation(plan_path, entry)
    return entry


class Settled(NamedTuple):
    """What recording a ruling left: `clean` is True when the push check counts the review as clean, and `line` says
    so, or says why the gate still counts it as dirty."""
    clean: bool
    line: str


def record_ruling(session_id, decision, settled_line):
    """Record a plan-impact ruling and credit the tree the ruled hand-back covered, so a push of that tree passes
    the push check however many coders ran since. Settled is clean with settled_line, or dirty with why the gate
    still counts the review as dirty."""
    handback_store.record(session_id, handback_store.PLAN_RULING, decision=decision)
    refusal, _repo = handback.record_clean_review(session_id)
    if refusal:
        return Settled(False, f"The ruling is recorded, but the push check still counts the review as dirty: "
                              f"{refusal}.")
    return Settled(True, settled_line)


def settle_ruling(decision):
    """Record a `keep` or an applied-`adopt` ruling for this session."""
    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    if not session_id:
        return Settled(False, "CLAUDE_CODE_SESSION_ID is not set, so the ruling is not recorded and the push check "
                              "still counts the review as dirty.")
    return record_ruling(session_id, decision, "The ruling settles the plan impact, so the push check counts the "
                                               "review as clean.")


def print_settled(settled, *lines):
    """Print the end of a ruling that needs no re-dispatch: `done` when the gate is clear, else `stop`, with `lines`
    and then the Settled line that says which."""
    action = "done" if settled.clean else "stop"
    print_action(action, *lines, settled.line)


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
        f"Then run: {REVIEW_FIX_COMMAND} {plan_format.DECIDE_USAGE}",
        plan_format.DECIDE_BY_NOTE,
        f"Counters held for the re-dispatch: iter={packet['iter']} "
        f"spec_iter={packet['spec_iter'] if packet['spec_iter'] is not None else 'absent'}",
    ]


def session_adoption_lines(impacts, ruling_words_of, ruled_at):
    """The `## Plan Deviations` lines that record `impacts` as adopted by the session at `ruled_at`.
    `ruling_words_of(impact)` gives the words of each ruling."""
    owner = plan_format.SESSION_RULING_OWNER
    choice = plan_format.DECISION_WORDS[plan_format.ADOPT_DECISION]
    lines = []
    for impact in impacts:
        lines += plan_format.ruling_deviation(None, choice, owner, ruled_at, ruling_words_of(impact), impact["text"])
    return lines


def plan_impact_deviation_lines(adopted, ruled_at):
    """The `## Plan Deviations` lines for the plan impacts adopted by rule, no question asked."""
    return session_adoption_lines(adopted, lambda impact: plan_format.below_criteria_ruling(impact["text"]),
                                  ruled_at)


def standing_reword_deviation_lines(rewords, ruling, ruled_at):
    """The `## Plan Deviations` lines for the reword impacts a standing ruling covers (held ones adopted now and
    ones the loop adopted). The session is the owner; the standing ruling (who, at, summary) is in the ruling words,
    so no sign-off is recorded at a time the user never ruled."""
    ruling_words = f"covered by the standing ruling by {standing_rulings.ruling_label(ruling)}: {ruling['summary']}"
    return session_adoption_lines(rewords, lambda impact: ruling_words, ruled_at)


def record_standing_adoption(session_id, rewords, repo, ruled_at, nothing_held):
    """Records the adoption of each impact in `rewords` at `ruled_at` in `repo` where the review record reads rulings: a
    ruled-impact row for each. With `nothing_held` (no held impact is left in the packet) it also writes the
    plan-ruling row and credits the reviewed tree as a `decide` ruling does; with a held impact left, that row would
    settle it too, so none is written."""
    for impact in rewords:
        handback_store.record_ruled_impact(session_id, impact["text"], repo, decision=plan_format.ADOPT_DECISION,
                                           owner=plan_format.SESSION_RULING_OWNER, ruled_at=ruled_at)
    if not nothing_held:
        return
    handback_store.record(session_id, handback_store.PLAN_RULING, decision=plan_format.ADOPT_DECISION)
    refusal, _repo = handback.record_clean_review(session_id)
    if refusal:
        print(f"The standing adoption is recorded, but the push check still counts the review as dirty: {refusal}.")


def standing_settled(packet, standing):
    """The held reword impacts a standing ruling covers; [] with no ruling or no reword impact. Changes nothing."""
    if standing is None:
        return []
    return [impact for impact in handback.held_plan_impacts(packet) if impact["reword"]]


def settle_standing_rewords(packet, rewords, state, ruled_at):
    """Marks each impact in `rewords` adopted and records the adoption for the push check, under the repo the
    packet answers. Without a session id it records nothing and says so."""
    if not rewords:
        return
    for impact in rewords:
        impact["adopted"] = True
    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    if not session_id:
        named = "; ".join(one_line(impact["text"], 120) for impact in rewords)
        print("CLAUDE_CODE_SESSION_ID is not set, so the adoption of the standing-ruling rewords is not recorded "
              f"and the push check still counts the review as dirty. Rewords: {named}.")
        return
    repo = required_packet_repo(state.get("relaunch_args") or [])
    nothing_held = not handback.held_plan_impacts(packet)
    record_standing_adoption(session_id, rewords, repo, ruled_at, nothing_held)


def standing_reword_lines(packet, plan_path, state, ruled_at):
    """(the lines for the reword impacts adopted under the plan's standing ruling, the rule-adopted impacts left
    over). The rewords are the held ones the ruling adopts now plus the ones the loop adopted under it, which change a
    criterion's words and so never print as a code-wins adoption. A standing ruling line that does not parse is
    named and holds the impacts."""
    try:
        standing = standing_rulings.reword_ruling(plan_path) if plan_path is not None else None
    except plan_format.PlanFormatError as error:
        # A bad standing ruling line stops nothing else in the packet: print it by file and line, hold the impacts.
        print(f"Standing ruling line does not parse, so no reword is adopted under it: {error}")
        return [], handback.rule_adopted_plan_impacts(packet)

    # Before the held rewords are adopted below, so they are not counted twice.
    loop_adopted = loop_adopted_rewords(packet, standing)
    rewords = standing_settled(packet, standing)
    settle_standing_rewords(packet, rewords, state, ruled_at)

    adopted = handback.rule_adopted_plan_impacts(packet)
    rewords = [*rewords, *loop_adopted]
    if not rewords:
        return [], adopted
    lines = ["Plan impacts adopted under a standing ruling (they only reword a criterion; no one was asked). "
             + ADD_DEVIATIONS_LINE,
             *standing_reword_deviation_lines(rewords, standing, ruled_at)]
    return lines, [impact for impact in adopted if impact not in rewords]


def loop_adopted_rewords(packet, standing):
    """The rule-adopted impacts that reword a criterion: the loop adopted them under the standing ruling. Empty with
    no ruling."""
    if standing is None:
        return []
    return [impact for impact in handback.rule_adopted_plan_impacts(packet)
            if impact["reword"] and impact["ac_change"]]


def present_plan_impacts(packet, state, plan_path=None):
    """Prints the packet's plan impacts once, after the review result. The loop never stopped for them. An adopted one
    prints as a plan deviation line to add, with no question; a settled adopted one, which an earlier ruling covers,
    prints nothing. A held one that only rewords a criterion is adopted the same way when the plan at `plan_path`
    holds a standing ruling covering rewords; its line names that ruling, and a reword the loop adopted under that
    ruling prints the same way. A toolkit-cause one prints as a toolkit fault, with no question. The ones that change
    an acceptance criterion go to the user in one closing question; the fix waits for the answer."""
    impacts = packet["plan_impacts"]
    if not impacts:
        return

    ruled_at = plan_format.ruled_at_now()
    lines, adopted = standing_reword_lines(packet, plan_path, state, ruled_at)
    toolkit = handback.toolkit_plan_impacts(packet)
    held = handback.held_plan_impacts(packet)
    if adopted:
        lines += ["Plan impacts adopted by rule (no acceptance criterion changes, so the code wins; no one was asked). "
                  + ADD_DEVIATIONS_LINE,
                  *plan_impact_deviation_lines(adopted, ruled_at)]
    for impact in toolkit:
        lines += [f"Toolkit fault, not a plan change (the {impact['gate']} {plan_format.cause_stop(impact['cause'])}):",
                  impact["text"]]
    if not held:
        if lines:  # a settled impact alone leaves nothing to show
            print_action("show-plan-impacts", *lines)
        return

    held_text = handback.held_plan_impact_text(held)
    applied = any(impact["applied"] for impact in held)
    same_impact = state.get("plan_impact") == held_text
    filed_at = state.get(PLAN_IMPACT_FILED_AT_KEY) if same_impact else None
    state.update({"plan_impact": held_text, "plan_impact_held": True, "plan_impact_applied": applied,
                  PLAN_IMPACT_FILED_AT_KEY: filed_at or time.time(),
                  "plan_impact_adopt_settles": handback.adopt_settles(packet, held),
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
    lines.append(f"Gate: do not commit yet: {len(held)} {handback.PLAN_IMPACTS_WAIT_TEXT}, so the push check counts "
                 "the review as dirty until `decide` records one.")
    print_action("ask-user-plan-impact", *lines, *plan_impact_question_lines(held_text, packet))
