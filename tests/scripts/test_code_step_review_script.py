"""The /code review dispatch that runs review_loop_script.py in place of the review-loop agent.

A stand-in script under the stub claude dir takes the real script's arguments and, by FAKE_LOOP_MODE, hands back a
converged packet, exits with no hand-back, or runs until it is killed. The fixtures are those of test_code_step.py;
its own tests run there, not here.

run: python3 -m unittest test_code_step_review_script
"""
import json
import os
import pathlib
import signal
import time

import test_code_step as base

FAKE_LOOP_SCRIPT = """import os
import pathlib
import signal
import sys
import time

scripts = pathlib.Path(__file__).resolve().parent.parent
sys.path[:0] = [str(scripts / "code"), str(scripts / "lib")]
import code_step_core
import handback

arguments = sys.argv[1:]
options = dict(zip(arguments[1::2], arguments[2::2]))
out = pathlib.Path(os.environ["FAKE_LOOP_OUT"])
(out / "argv.json").write_text(__import__("json").dumps(arguments))
mode = os.environ["FAKE_LOOP_MODE"]


def terminated(signal_number, frame):
    (out / "terminated").write_text(str(os.getpid()))
    sys.exit(0)


if mode == "hang":
    signal.signal(signal.SIGTERM, terminated)
    (out / "started").write_text(str(os.getpid()))
    time.sleep(60)
if mode in ("converged", "plan-impact", "unreviewed-fix"):
    message = "status: converged\\niter: 1\\nfixed: []\\nask: []\\nnit: []"
    if mode == "unreviewed-fix":
        message = ("status: converged\\niter: 2\\nfixed: [{finding: f, file_line: src/orders.ts:4, blocker: false}]"
                   "\\nask: []\\nnit: []")
    if mode == "plan-impact":
        message = "status: plan-impact\\niter: 1\\nplan_impact: |\\n    PLAN-IMPACT:\\n      found: B\\n"
    code_step_core.log_event(arguments[0], options["--run-id"], "handback", options["--session"],
                             agent_id=options["--agent-id"], agent_type="review-loop", message=message)
    handback.record(options["--session"], "handback", agent_id=options["--agent-id"], status="converged",
                    problems=[], message=message, no_reviewer=False, unreviewed_fix=mode == "unreviewed-fix")
"""


class ReviewScriptTest(base.CodeStepTest):
    def setUp(self):
        super().setUp()
        fake_script = self.claude / "scripts/review/review_loop_script.py"
        fake_script.parent.mkdir(parents=True, exist_ok=True)
        fake_script.write_text(FAKE_LOOP_SCRIPT)
        self.fake_out = self.tmp / "fake-loop"
        self.fake_out.mkdir()
        self.env.pop("CODE_STEP_REVIEW_LOOP")
        self.env.update(FAKE_LOOP_OUT=str(self.fake_out), FAKE_LOOP_MODE="converged")

    def wait_for_file(self, name):
        marker = self.fake_out / name
        deadline = time.time() + 20
        while not marker.exists() and time.time() < deadline:
            time.sleep(0.05)
        self.assertTrue(marker.exists(), f"the stand-in script wrote no {name}")
        return marker

    def wait_for_script_exit(self, pid):
        deadline = time.time() + 20
        while time.time() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            time.sleep(0.05)

    def script_argv(self):
        argv_file = self.wait_for_file("argv.json")
        return json.loads(argv_file.read_text())

    def test_the_review_dispatch_launches_the_script_and_its_hand_back_finishes_the_phase(self):
        out = self.coder_round()

        self.assertIn("ACTION: wait", out)
        self.assertNotIn("AGENT: review-loop", out)
        state = self.state()
        dispatch = self.events_named("dispatch")[-1]
        self.assertEqual(("review-loop", "script"), (dispatch["agent_type"], dispatch["model"]))
        agent_id = f"loop-script-{state['runId']}-{dispatch['id']}"
        self.assertEqual([agent_id], [event["agent_id"] for event in self.events_named("launch")
                                      if event.get("dispatch") == dispatch["id"]])

        argv = self.script_argv()
        options = dict(zip(argv[1::2], argv[2::2], strict=True))
        self.assertEqual(agent_id, options["--agent-id"])
        prompt_text = pathlib.Path(options["--prompt-file"]).read_text()
        self.assertTrue(prompt_text.startswith("mode: review-first\ncaller: code\n"), prompt_text)
        self.wait_for_script_exit(state["reviewScriptPid"])

        out = self.step("resume")

        self.assert_first_phase_ticked()
        self.assert_marked_clean(out)

    def test_a_hand_back_ending_on_an_unreviewed_fix_finishes_and_names_the_fix_files(self):
        self.env["FAKE_LOOP_MODE"] = "unreviewed-fix"
        self.coder_round()
        self.wait_for_script_exit(self.state()["reviewScriptPid"])

        out = self.step("resume")

        self.assert_first_phase_ticked()
        self.assert_marked_clean(out)
        self.assertIn("### Last fix not reviewed", self.said())
        self.assertIn("Its files are among: src/orders.ts", self.said())

    def test_a_converged_hand_back_ending_on_a_reviewer_names_no_unreviewed_fix(self):
        self.coder_round()
        self.wait_for_script_exit(self.state()["reviewScriptPid"])

        self.step("resume")

        self.assertNotIn("Last fix not reviewed", self.said())

    def test_a_script_that_exits_with_no_hand_back_stops_with_its_log_and_the_review_again_line(self):
        self.env["FAKE_LOOP_MODE"] = "silent"
        self.coder_round()
        state = self.state()
        self.wait_for_script_exit(state["reviewScriptPid"])
        self.wait_env(5, "0.05")

        out = self.step("resume")

        self.assertIn("ACTION: stop", out)
        self.assertIn(state["reviewScriptLog"], out)
        self.assertIn("review-again", out)
        state = self.state()
        self.assertEqual(("stopped", "invalid-packet"), (state["stage"], state["stopReason"]))
        self.assertNotIn("reviewScriptPid", state)

    def test_review_again_kills_the_running_script_and_launches_a_new_one(self):
        self.env["FAKE_LOOP_MODE"] = "hang"
        self.coder_round()
        first_pid = int(self.wait_for_file("started").read_text())
        self.set_state(stage="stopped", stopReason="invalid-packet")

        out = self.step("review-again")

        self.assertEqual(str(first_pid), self.wait_for_file("terminated").read_text())
        self.assertIn("ACTION: wait", out)
        self.assertNotEqual(first_pid, self.state()["reviewScriptPid"])
        self.step("abort")

    def test_abort_kills_the_running_script(self):
        self.env["FAKE_LOOP_MODE"] = "hang"
        self.coder_round()
        started_pid = self.wait_for_file("started").read_text()

        out = self.step("abort")

        self.assertEqual(started_pid, self.wait_for_file("terminated").read_text())
        self.assertIn(f"Killed the review loop script (pid {started_pid})", out)
        self.assertNotIn("may still be running", out)

    def test_abort_of_a_script_that_already_exited_does_not_claim_to_have_killed_it(self):
        self.env["FAKE_LOOP_MODE"] = "silent"
        self.coder_round()
        script_pid = self.state()["reviewScriptPid"]
        self.wait_for_script_exit(script_pid)

        out = self.step("abort")

        self.assertIn(f"The review loop script (pid {script_pid}) had already exited.", out)
        self.assertNotIn("Killed the review loop script", out)
        self.assertNotIn("may still be running", out)

    def dispatch_rows(self):
        rows = []
        for store_file in (self.tmp / "handback-store").glob("*.jsonl"):
            rows += [json.loads(line) for line in store_file.read_text().splitlines()]
        return [row for row in rows if row["kind"] == "dispatch"]

    def test_a_plan_impact_hand_back_adopted_launches_a_new_script_for_the_next_review(self):
        self.env["FAKE_LOOP_MODE"] = "plan-impact"
        self.coder_round()
        first_pid = self.state()["reviewScriptPid"]
        self.wait_for_script_exit(first_pid)

        out = self.step("resume")

        self.assertIn("ACTION: ask-user", out)
        self.env["FAKE_LOOP_MODE"] = "hang"
        out = self.step("decide", "adopt", "--by", "user", "--ruling", "adopt it")
        self.assertIn("AGENT: coder", out)
        (self.repo / self.plan).write_text(self.plan_text().replace(
            "## Phase 2", "Adopted step: drop the header.\n\n## Phase 2", 1))
        self.wait_env(5, "0.05")
        self.hook("coder", "docs/plans/orders/spec.md:3: Add orders.")
        out = self.step("after-plan-edit")

        self.assertIn("ACTION: wait", out)
        self.assertNotIn("exited with no hand-back", out)
        self.wait_for_file("started")
        second_pid = self.state()["reviewScriptPid"]
        self.assertNotEqual(first_pid, second_pid)
        self.assertEqual(2, len(self.dispatch_rows()))
        self.step("abort")

    def test_the_wait_cap_stop_of_a_running_script_names_its_log_and_the_two_verbs(self):
        self.env["FAKE_LOOP_MODE"] = "hang"
        self.coder_round()
        self.wait_for_file("started")
        self.age_dispatches(100)
        self.set_state(dispatchAt=time.time() - 100)
        self.wait_env(1, "0.2", waits=3)

        out = self.step("after-review")

        self.assertIn("ACTION: stop", out)
        self.assertIn(self.state()["reviewScriptLog"], out)
        self.assertIn("keep waiting", out)
        self.assertIn("kill", out)
        self.assertNotIn("SendMessage", out)
        self.step("abort")

    def test_a_script_dispatch_carries_the_plans_own_gate_variables(self):
        self.set_verification("- [ ] **Env**: passes - `GATE_X=1 npx vitest run`")

        self.coder_round()

        options = dict(zip(*[iter(self.script_argv()[1:])] * 2, strict=True))
        self.assertIn("gate-env: GATE_X=1", pathlib.Path(options["--prompt-file"]).read_text())

    def test_resume_after_the_wait_cap_stop_of_a_script_takes_its_hand_back(self):
        self.env["FAKE_LOOP_MODE"] = "hang"
        self.coder_round()
        self.wait_for_file("started")
        self.age_dispatches(100)
        self.set_state(dispatchAt=time.time() - 100)
        self.wait_env(1, "0.2", waits=3)
        self.assertIn("ACTION: stop", self.step("after-review"))
        self.assertTrue(self.state()["resumableReview"])
        dispatch = self.events_named("dispatch")[-1]
        agent_id = f"loop-script-{self.state()['runId']}-{dispatch['id']}"
        self.hook("review-loop", self.LOOP_OK, agent_id=agent_id)

        out = self.step("resume")

        self.assert_first_phase_ticked()
        self.assert_marked_clean(out)
        state = self.state()
        self.assertFalse(state.get("resumableReview"))
        self.assertNotIn("reviewScriptPid", state)
        self.step("abort")

    def test_a_script_killed_after_the_wait_cap_stop_never_asks_for_a_sendmessage(self):
        self.env["FAKE_LOOP_MODE"] = "hang"
        self.coder_round()
        script_pid = int(self.wait_for_file("started").read_text())
        self.age_dispatches(100)
        self.set_state(dispatchAt=time.time() - 100)
        self.wait_env(1, "0.2", waits=3)
        self.assertIn("ACTION: stop", self.step("after-review"))
        os.kill(script_pid, signal.SIGTERM)
        self.wait_for_script_exit(script_pid)
        self.wait_env(5, "0.05")

        first_out = self.step("resume")
        self.step("resume")

        self.assertIn("exited with no hand-back", first_out)
        question = self.real_question_file().read_text()
        self.assertIn("The run is at stage stopped", question)
        self.assertNotIn("SendMessage", question)
        self.assertFalse(self.state().get("resumableReview"))

    def test_a_restart_kills_a_script_left_running_by_the_wait_cap_stop(self):
        self.env["FAKE_LOOP_MODE"] = "hang"
        self.coder_round()
        started_pid = self.wait_for_file("started").read_text()
        self.age_dispatches(100)
        self.set_state(dispatchAt=time.time() - 100)
        self.wait_env(1, "0.2", waits=3)
        self.assertIn("ACTION: stop", self.step("after-review"))

        self.step("start", "--restart")

        self.assertEqual(started_pid, self.wait_for_file("terminated").read_text())

    def test_a_restart_that_stops_before_dispatching_leaves_nothing_to_resume(self):
        self.env["FAKE_LOOP_MODE"] = "hang"
        self.coder_round()
        self.wait_for_file("started")
        self.age_dispatches(100)
        self.set_state(dispatchAt=time.time() - 100)
        self.wait_env(1, "0.2", waits=3)
        self.assertIn("ACTION: stop", self.step("after-review"))

        self.step("start", "--restart", "missing.md")
        self.step("resume")

        question = self.real_question_file().read_text()
        self.assertEqual({}, self.state())
        self.assertNotIn("SendMessage", question)

    def test_the_taken_hand_back_forgets_the_finished_script(self):
        self.coder_round()
        self.wait_for_script_exit(self.state()["reviewScriptPid"])
        self.step("resume")

        self.assertNotIn("reviewScriptPid", self.state())

# The tests inherited from the fixture class run in test_code_step.py: leave them out here.
for inherited_test in [name for name in dir(base.CodeStepTest) if name.startswith("test_")]:
    if inherited_test not in vars(ReviewScriptTest):
        setattr(ReviewScriptTest, inherited_test, None)


if __name__ == "__main__":
    base.unittest.main()
