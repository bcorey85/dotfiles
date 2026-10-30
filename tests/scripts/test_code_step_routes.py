"""code_step_routes.py: every state a /code run can be in has one row in the route table, `resume` takes a step with a
handler from each of them, and each guarded verb runs from the rows that name it and from no other.

run: python3 -m unittest test_code_step_routes
"""
import sys
import unittest

import toolkit_paths

for folder in (toolkit_paths.LIB_DIR, toolkit_paths.REVIEW_DIR, toolkit_paths.CODE_DIR):
    sys.path.insert(0, str(folder))
import code_step  # noqa: E402
import code_step_core  # noqa: E402
import code_step_review  # noqa: E402
import code_step_review_stops  # noqa: E402
from code_step_routes import (  # noqa: E402
    GUARDED_VERBS,
    ROUTES,
    STAGE_FACTS,
    STALE_PHASE_STEP,
    Observed,
    StageFact,
    resume_step,
    state_key,
)
from code_step_state import RunState, Stage, Stop, StopKind  # noqa: E402


def every_state():
    # No saved run, then one saved run in each stage, and one stopped run with no kind and with each kind.
    yield None
    for stage in Stage:
        if stage != Stage.STOPPED:
            yield RunState(stage)
    yield RunState(Stage.STOPPED, Stop(None, 1.5))
    for kind in StopKind:
        yield RunState(Stage.STOPPED, Stop(kind, 1.5))


def steps_of(route):
    # Every step a route can take, under either answer to its observation.
    if isinstance(route.step, Observed):
        return {route.step.then, route.step.otherwise}
    return {route.step}


def answering(answer):
    # Observations that all give one answer, in place of what a run's log shows.
    return {name: lambda repo_dir, state: answer for name in code_step.OBSERVATIONS}


def stages_with(fact):
    return {stage for stage, facts in STAGE_FACTS.items() if fact in facts}


class RouteTableTest(unittest.TestCase):
    def test_every_state_has_one_row_and_every_row_one_state(self):
        state_keys = [state_key(state) for state in every_state()]

        self.assertEqual(len(state_keys), len(set(state_keys)))
        self.assertEqual(set(ROUTES), set(state_keys))

    def test_resume_from_every_state_takes_a_step_that_has_a_handler(self):
        for state in every_state():
            for answer in (True, False):
                with self.subTest(state_key(state), observation_holds=answer):
                    step = resume_step(None, state, answering(answer))
                    self.assertIn(step, code_step.STEPS)

    def test_every_handler_and_observation_serves_a_row(self):
        reachable_steps = {STALE_PHASE_STEP}
        for route in ROUTES.values():
            reachable_steps |= steps_of(route)
        named_observations = {route.step.observation for route in ROUTES.values() if isinstance(route.step, Observed)}

        self.assertEqual(reachable_steps, set(code_step.STEPS))
        self.assertEqual(named_observations, set(code_step.OBSERVATIONS))

    def test_a_guarded_verb_runs_from_the_rows_that_name_it_and_from_no_other(self):
        for state in every_state():
            route = ROUTES[state_key(state)]
            for verb in sorted(GUARDED_VERBS):
                with self.subTest(state_key(state), verb=verb):
                    self.assertEqual(route.verb == verb, code_step_core.guarded_verb_runs(verb, state))

    def test_verify_also_runs_once_the_phase_review_converged_with_no_coder_at_work(self):
        runs_after_converged_review = (Stage.REVIEW, Stage.IMPACT_CODER, Stage.IMPACT_REVIEW, Stage.ASKS, Stage.STOPPED)
        refused_after_converged_review = (Stage.CODER, Stage.ASKS_CODER, Stage.PLAN_CODER, Stage.SKILL, Stage.DONE)

        for stage in runs_after_converged_review:
            with self.subTest(stage):
                converged = RunState(stage, review_status="converged")
                self.assertTrue(code_step_core.guarded_verb_runs("verify", converged))
        for stage in refused_after_converged_review:
            with self.subTest(stage):
                converged = RunState(stage, review_status="converged")
                self.assertFalse(code_step_core.guarded_verb_runs("verify", converged))
        self.assertFalse(code_step_core.guarded_verb_runs("verify", RunState(Stage.REVIEW, review_status=None)))

    def test_every_guarded_verb_has_a_refusal(self):
        self.assertEqual(GUARDED_VERBS, set(code_step_review.VERB_REFUSALS))
        self.assertLessEqual(set(code_step_review.GO_ON_REFUSAL_VERBS), GUARDED_VERBS)

    def test_a_stop_that_waits_on_a_fix_or_reviews_again_names_the_verb_that_goes_on(self):
        for key, route in ROUTES.items():
            steps = steps_of(route)
            if "ask-cause-fixed" in steps or "review-again" in steps:
                with self.subTest(key):
                    self.assertIsNotNone(route.verb)

    def test_every_blocker_stop_has_its_question(self):
        blocker_kinds = {key[1] for key, route in ROUTES.items() if "ask-critical-blocker" in steps_of(route)}

        self.assertLessEqual(blocker_kinds, set(code_step_review_stops.blocker_stop_text()))


class StageFactsTest(unittest.TestCase):
    def test_every_stage_has_its_facts(self):
        self.assertEqual(set(Stage), set(STAGE_FACTS))

    def test_a_stage_with_an_agent_out_waits_for_it_only_once_its_dispatch_is_on_record(self):
        for stage in stages_with(StageFact.AGENT_OUT):
            step = ROUTES[(stage, None)].step
            with self.subTest(stage):
                self.assertIsInstance(step, Observed)
                self.assertEqual("dispatch-recorded", step.observation)

    def test_a_code_agent_is_an_agent_out_and_never_edits_the_plan(self):
        code_agent_stages = stages_with(StageFact.CODE_AGENT_OUT)

        self.assertLessEqual(code_agent_stages, stages_with(StageFact.AGENT_OUT))
        self.assertFalse(code_agent_stages & stages_with(StageFact.PLAN_EDITED))


if __name__ == "__main__":
    unittest.main()
