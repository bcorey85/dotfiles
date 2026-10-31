"""code_step_routes.py: the one table that routes a /code run.

Installed beside code_step.py and imported by code_step_core. A run's row is its stage, and its stop kind when it is
stopped. The row names the step `resume` takes next and the one guarded verb the run accepts there (and `verify` once
the phase's review converged, at a stage marked VERIFY_ON_CLEAN_REVIEW); `start`, `tick`, `abort`, `guide` and `status`
run at any state. A step that hangs on what the run's log shows names that observation
and the step for each answer. The stage facts tell the rest of code-step what a stage means."""
import dataclasses
import enum

from code_step_state import Stage, StopKind

# The row of a checkout with no saved run.
NO_RUN = (None, None)
# The step `resume` takes, whatever the row, when the plan's phase changed under the saved run.
STALE_PHASE_STEP = "ask-stale-phase"


def state_key(state):
    # The saved run's row: its stage, and its stop kind when it is stopped.
    if state is None:
        return NO_RUN
    if state.stage != Stage.STOPPED or state.stop is None:
        return state.stage, None
    return Stage.STOPPED, state.stop.kind


@dataclasses.dataclass(frozen=True)
class Observed:
    # A step that hangs on what the run's log shows: `then` when the observation holds, `otherwise` when it does not.
    observation: str
    then: str
    otherwise: str


@dataclasses.dataclass(frozen=True)
class Route:
    # The step `resume` takes from a row, and the guarded verb the row accepts (None: only the verbs that run anywhere,
    # and verify once the phase's review converged, at a stage marked VERIFY_ON_CLEAN_REVIEW).
    step: str | Observed
    verb: str | None = None


# An agent the run dispatched is out. Its hand-back is waited for only once the dispatch is on record.
CODER_HANDBACK = Observed("dispatch-recorded", "after-coder", "ask-status")
REVIEW_HANDBACK = Observed("dispatch-recorded", "after-review", "ask-status")
PLAN_EDIT_HANDBACK = Observed("dispatch-recorded", "after-plan-edit", "ask-status")
# A stopped coder's hand-back is waited for once the user's answer reached it.
CODER_ANSWERED = Observed("coder-answer-sent", "after-coder", "ask-coder")
# A review-loop the wait cap stopped on is waited for again while a review script is on record (after-review stops on
# one that has gone) or once the user resumed it.
REVIEW_GOES_ON = Observed("review-goes-on", "after-review", "ask-review-cap")

ROUTES = {
    NO_RUN: Route("start"),
    (Stage.CODER, None): Route(CODER_HANDBACK),
    (Stage.ASKS_CODER, None): Route(CODER_HANDBACK, "correct-ruling"),
    (Stage.REVIEW, None): Route(REVIEW_HANDBACK),
    (Stage.PLAN_CODER, None): Route(PLAN_EDIT_HANDBACK),
    (Stage.IMPACT_CODER, None): Route("ask-impact", "decide"),
    (Stage.IMPACT_REVIEW, None): Route("ask-impact", "decide"),
    (Stage.ASKS, None): Route("ask-asks", "asks-done"),
    (Stage.SKILL, None): Route("closing-skill", "skill-done"),
    (Stage.SESSION, None): Route("session-phase", "session-done"),
    (Stage.DONE, None): Route("done"),
    # A stop with no kind, or one no command clears, prints the saved state and how to start the phase over.
    (Stage.STOPPED, None): Route("ask-status"),
    (Stage.STOPPED, StopKind.REVIEW_NOT_CONVERGED): Route("ask-status"),
    (Stage.STOPPED, StopKind.CODER_RESUMABLE): Route(CODER_ANSWERED),
    (Stage.STOPPED, StopKind.REVIEW_RESUMABLE): Route(REVIEW_GOES_ON, "review-again"),
    (Stage.STOPPED, StopKind.CODER_CAP): Route("ask-coder-cap"),
    # The user fixes the cause outside the run; the row's verb goes on from there.
    (Stage.STOPPED, StopKind.VERIFICATION): Route("ask-cause-fixed", "verify"),
    (Stage.STOPPED, StopKind.PLAN_FORMAT): Route("ask-cause-fixed", "verify"),
    (Stage.STOPPED, StopKind.INVALID_PACKET): Route("ask-cause-fixed", "review-again"),
    (Stage.STOPPED, StopKind.CAP_REACHED): Route("ask-cause-fixed", "review-again"),
    (Stage.STOPPED, StopKind.TOOL_FAULT): Route("ask-cause-fixed", "review-again"),
    (Stage.STOPPED, StopKind.CHECK_UNVERIFIED): Route("ask-cause-fixed", "review-again"),
    (Stage.STOPPED, StopKind.CHECK_NOT_RUN): Route("ask-cause-fixed", "review-again"),
    (Stage.STOPPED, StopKind.PLAN_IMPACT_CAUSE): Route("ask-cause-fixed", "review-again"),
    # A review gate refused as false-clean is reviewed again, not stopped on again.
    (Stage.STOPPED, StopKind.FALSE_CLEAN): Route("review-again", "review-again"),
    (Stage.STOPPED, StopKind.CRITICAL_BLOCKER): Route("ask-critical-blocker", "review-again"),
    (Stage.STOPPED, StopKind.SETUP_FAULT): Route("ask-critical-blocker", "review-again"),
    (Stage.STOPPED, StopKind.FIX_REMOVED_CHANGE): Route("ask-critical-blocker", "review-again"),
}
# The verbs that run only from a row that names them (and verify once the phase's review converged, at a stage marked
# VERIFY_ON_CLEAN_REVIEW).
GUARDED_VERBS = frozenset(route.verb for route in ROUTES.values() if route.verb)


def resume_step(repo_dir, state, observations):
    # The step `resume` takes from the saved run's row. A step that hangs on the run's log asks observations, a dict
    # of observation name to function(repo_dir, state), for the answer.
    step = ROUTES[state_key(state)].step
    if not isinstance(step, Observed):
        return step

    holds = observations[step.observation](repo_dir, state)
    return step.then if holds else step.otherwise


class StageFact(enum.Enum):
    # An agent the run dispatched may be out: the hooks watch the fork's calls, and a restart abandons the dispatch.
    AGENT_OUT = "agent-out"
    # The agent out works on the phase's code: it owns the session's review-loop hand-backs, and its diff may not edit
    # a later phase's files.
    CODE_AGENT_OUT = "code-agent-out"
    # The plan is edited on purpose here, so a changed phase does not make the run stale.
    PLAN_EDITED = "plan-edited"
    # The text say.md holds was handed back already, so a resume clears it.
    RESUME_CLEARS_SAY = "resume-clears-say"
    # No coder works on the phase: once its review converged, `verify` may run its checks and close it.
    VERIFY_ON_CLEAN_REVIEW = "verify-on-clean-review"


STAGE_FACTS = {
    Stage.CODER: (StageFact.AGENT_OUT, StageFact.CODE_AGENT_OUT),
    Stage.ASKS_CODER: (StageFact.AGENT_OUT, StageFact.CODE_AGENT_OUT),
    Stage.REVIEW: (StageFact.AGENT_OUT, StageFact.CODE_AGENT_OUT, StageFact.VERIFY_ON_CLEAN_REVIEW),
    Stage.PLAN_CODER: (StageFact.AGENT_OUT, StageFact.PLAN_EDITED, StageFact.RESUME_CLEARS_SAY),
    Stage.IMPACT_CODER: (StageFact.PLAN_EDITED, StageFact.RESUME_CLEARS_SAY, StageFact.VERIFY_ON_CLEAN_REVIEW),
    Stage.IMPACT_REVIEW: (StageFact.PLAN_EDITED, StageFact.RESUME_CLEARS_SAY, StageFact.VERIFY_ON_CLEAN_REVIEW),
    Stage.ASKS: (StageFact.RESUME_CLEARS_SAY, StageFact.VERIFY_ON_CLEAN_REVIEW),
    Stage.SKILL: (StageFact.RESUME_CLEARS_SAY,),
    Stage.SESSION: (StageFact.RESUME_CLEARS_SAY,),
    Stage.DONE: (),
    Stage.STOPPED: (StageFact.RESUME_CLEARS_SAY, StageFact.VERIFY_ON_CLEAN_REVIEW),
}
