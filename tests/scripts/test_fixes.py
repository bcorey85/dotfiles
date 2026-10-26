"""Scratch checks for the code_step.py fixes: packet block scalars, questions in say.md, say.md cleared on a
resumed run, the plan-edit coder after an adopted change, and the per-file change fallback."""
import importlib.util
import json
import os
import pathlib
import subprocess
import tempfile
import time
import unittest

import toolkit_paths

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
REPO_CODE_STEP = REPO_ROOT / "claude" / ".claude" / "scripts" / "code" / "code_step.py"
SCRIPT = pathlib.Path(os.environ.get("CODE_STEP_SCRIPT") or REPO_CODE_STEP)
spec = importlib.util.spec_from_file_location("code_step", SCRIPT)
code_step = importlib.util.module_from_spec(spec)
spec.loader.exec_module(code_step)
import code_step_core  # noqa: E402

PLAN = """# Plan

## Phase Status

- [ ] Phase 1: add the export

## Phase 1: add the export

1. Write the CSV with a header row.

### Automated Verification

- [ ] `npm test` exits 0

## References

- none
"""

REVIEW_PACKET = """status: plan-impact
iter: 1
plan_impact: |
    PLAN-IMPACT:
      assumed: the CSV has a header row

      found: the importer rejects a header row
fixed: []

The loop stopped on a plan question.
"""


REAL_CLAUDE_DIR = pathlib.Path(os.environ.get("CODE_STEP_REAL_CLAUDE") or toolkit_paths.CLAUDE_DIR)
RULING = "the importer is right, so drop the header row"


def git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def make_repo(test_case):
    # The repo sits beside a throwaway home, so the script reads no real home and never waits for a hand-back.
    root = tempfile.TemporaryDirectory(prefix="codestep-")
    test_case.addCleanup(root.cleanup)
    repo = pathlib.Path(root.name) / "repo"
    repo.mkdir()
    (repo.parent / "home").mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "t@t")
    git(repo, "config", "user.name", "t")
    (repo / "plan.md").write_text(PLAN)
    (repo / "a.py").write_text("a = 1\n")
    (repo / "b.py").write_text("b = 1\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "base")
    (repo / ".git" / "code-step").mkdir()
    return repo


def write_state(repo, state):
    (repo / ".git" / "code-step" / "state.json").write_text(json.dumps(state))


def read_state(repo):
    return json.loads((repo / ".git" / "code-step" / "state.json").read_text())


def say_text(repo):
    say_file = repo / ".git" / "code-step" / "say.md"
    return say_file.read_text() if say_file.exists() else ""


def save_report(repo, agent_type, stage, message):
    # Logs what the hooks log for one agent of the run: its dispatch, its launch and its hand-back. A review-loop
    # hand-back counts only from the agent that the pending review dispatch launched.
    run_id = "20260101T000000-1"
    state = read_state(repo)
    state["runId"] = run_id
    state["dispatchAt"] = time.time()
    write_state(repo, state)
    agent_id = f"{agent_type}-1"
    dispatch_id = f"d{len(code_step_core.read_events(repo, run_id)) + 1}"
    code_step_core.log_event(repo, run_id, "dispatch", "session-1", id=dispatch_id, agent_type=agent_type,
                             stage=stage)
    code_step_core.log_event(repo, run_id, "launch", "session-1", agent_id=agent_id, dispatch=dispatch_id)
    code_step_core.log_event(repo, run_id, "handback", "session-1", agent_id=agent_id, agent_type=agent_type,
                             message=message)


def run(repo, *args):
    env = dict(os.environ, HOME=str(repo.parent / "home"), CODE_STEP_WAIT_SECONDS="0",
               CODE_STEP_CLAUDE_DIR=str(REAL_CLAUDE_DIR), CODE_STEP_NVIM_JUMP="true")
    done = subprocess.run(["python3", str(SCRIPT), *args], cwd=repo, capture_output=True, text=True, env=env)
    return done.stdout + done.stderr


def coder_state(repo, files):
    return {"stage": "review", "plan": "plan.md", "phase": "1", "lane": "eng-spec", "modifier": None,
            "baseline": {}, "files": files, "behavior": ["writes the CSV export"], "why": {}, "flagged": [],
            "testsRun": "none", "coderStage": "coder", "iter": 1}


class PlanImpactFlowTest(unittest.TestCase):
    def test_review_impact_writes_the_question_to_say_md(self):
        repo = make_repo(self)
        write_state(repo, coder_state(repo, ["a.py"]))
        save_report(repo, "review-loop", "review", REVIEW_PACKET)

        output = run(repo, "after-review")

        self.assertIn("ACTION: ask-user", output)
        self.assertNotIn("AskUserQuestion", output + say_text(repo))
        self.assertIn("## Question for the user", say_text(repo))
        self.assertIn("`decide adopt --by user --ruling \"<the decision in one line>\"`", say_text(repo))
        self.assertEqual(
            read_state(repo)["impact"],
            "PLAN-IMPACT:\n  assumed: the CSV has a header row\n\n  found: the importer rejects a header row",
        )

    def test_resume_verb_clears_old_say_text(self):
        repo = make_repo(self)
        state = coder_state(repo, ["a.py"])
        state.update({"stage": "impact-review", "impact": "PLAN-IMPACT:\n  found: no header row"})
        write_state(repo, state)
        (repo / ".git" / "code-step" / "say.md").write_text("Implemented: old summary\n\n")

        run(repo, "decide", "keep", "--by", "user", "--ruling", RULING)

        self.assertNotIn("old summary", say_text(repo))
        self.assertEqual(say_text(repo).count("Implemented:"), 1)

    def test_discuss_hands_the_question_back(self):
        repo = make_repo(self)
        state = coder_state(repo, ["a.py"])
        state.update({"stage": "impact-review", "impact": "PLAN-IMPACT:\n  found: no header row"})
        write_state(repo, state)

        output = run(repo, "decide", "discuss")

        self.assertIn("ACTION: ask-user", output)
        self.assertIn("found: no header row", say_text(repo))
        self.assertEqual(read_state(repo)["stage"], "impact-review")

    def test_adopt_dispatches_a_plan_coder_then_the_review(self):
        repo = make_repo(self)
        state = coder_state(repo, ["a.py"])
        state.update({"stage": "impact-review", "impact": "PLAN-IMPACT:\n  found: no header row"})
        write_state(repo, state)
        (repo / "a.py").write_text("a = 2\n")

        adopt_output = run(repo, "decide", "adopt", "--by", "user", "--ruling", RULING)
        state_after_adopt = read_state(repo)
        (repo / "plan.md").write_text((repo / "plan.md").read_text().replace("with a header row", "with no header row"))
        review_output = run(repo, "resume")
        state_after_edit = read_state(repo)

        self.assertIn("AGENT: coder", adopt_output)
        self.assertIn("Edit only the plan file plan.md", adopt_output)
        self.assertIn("code_step.py resume", adopt_output)
        self.assertEqual(state_after_adopt["stage"], "plan-coder")
        self.assertIn("## Plan Deviations", (repo / "plan.md").read_text())
        self.assertIn("AGENT: review-loop", review_output)
        self.assertEqual(state_after_edit["stage"], "review")
        self.assertEqual(state_after_edit["flagged"], [])
        self.assertNotIn("planEditBaseline", state_after_edit)
        self.assertIn("Decision: Adopt plan change", review_output)

    def test_plan_coder_code_edit_is_flagged_and_reviewed(self):
        repo = make_repo(self)
        state = coder_state(repo, ["a.py"])
        state.update({"stage": "impact-review", "impact": "PLAN-IMPACT:\n  found: no header row"})
        write_state(repo, state)

        run(repo, "decide", "adopt", "--by", "user", "--ruling", RULING)
        (repo / "b.py").write_text("b = 2\n")
        run(repo, "after-plan-edit")
        state_after_edit = read_state(repo)

        self.assertIn("b.py", state_after_edit["files"])
        self.assertTrue(any("b.py" in flag for flag in state_after_edit["flagged"]))

    def test_keep_goes_straight_to_review(self):
        repo = make_repo(self)
        state = coder_state(repo, ["a.py"])
        state.update({"stage": "impact-coder", "impact": "PLAN-IMPACT:\n  found: no header row"})
        write_state(repo, state)

        output = run(repo, "decide", "keep", "--by", "user", "--ruling", RULING)

        self.assertIn("AGENT: review-loop", output)
        self.assertEqual(read_state(repo)["stage"], "review")

    def test_ruling_words_reach_the_plan_deviation(self):
        repo = make_repo(self)
        state = coder_state(repo, ["a.py"])
        state.update({"stage": "impact-review", "impact": "PLAN-IMPACT:\n  found: no header row"})
        write_state(repo, state)

        run(repo, "decide", "adopt", "--by", "user", "--ruling", RULING)

        plan_text = (repo / "plan.md").read_text()
        self.assertIn("## Plan Deviations", plan_text)
        self.assertIn("  The ruling: " + RULING + "\n", plan_text)
        self.assertNotIn("  > " + RULING, plan_text)
        self.assertIn("Ruled by t at", plan_text)
        self.assertEqual(read_state(repo)["ruling"]["words"], RULING)

    def test_review_dispatch_after_decide_carries_the_resolved_block(self):
        repo = make_repo(self)
        state = coder_state(repo, ["a.py"])
        state.update({"stage": "impact-coder", "impact": "PLAN-IMPACT:\n  found: no header row"})
        write_state(repo, state)

        output = run(repo, "decide", "keep", "--by", "user", "--ruling", RULING)

        self.assertIn("AGENT: review-loop", output)
        self.assertIn("RESOLVED: the user ruled on this disagreement", output)
        self.assertIn("Decision: Keep plan as written", output)
        self.assertIn(RULING, output)
        self.assertIn("found: no header row", output)

    def test_decide_without_a_ruling_stops_and_changes_nothing(self):
        repo = make_repo(self)
        state = coder_state(repo, ["a.py"])
        state.update({"stage": "impact-review", "impact": "PLAN-IMPACT:\n  found: no header row"})
        write_state(repo, state)

        output = run(repo, "decide", "adopt")

        self.assertIn("ACTION: stop", output)
        self.assertIn("--ruling", output)
        self.assertNotIn("AGENT:", output)
        self.assertEqual(read_state(repo)["stage"], "impact-review")
        self.assertNotIn("## Plan Deviations", (repo / "plan.md").read_text())


class ChangeFallbackTest(unittest.TestCase):
    def test_several_files_do_not_share_one_behavior_sentence(self):
        repo = make_repo(self)
        state = coder_state(repo, ["a.py", "b.py"])
        state.update({"stage": "impact-coder", "impact": "PLAN-IMPACT:\n  found: x"})
        write_state(repo, state)

        output = run(repo, "decide", "keep", "--by", "user", "--ruling", RULING)

        self.assertNotIn("change: writes the CSV export", output)
        self.assertEqual(output.count("change: changed by the coder"), 2)

    def test_one_file_keeps_the_behavior_sentence(self):
        repo = make_repo(self)
        state = coder_state(repo, ["a.py"])
        state.update({"stage": "impact-coder", "impact": "PLAN-IMPACT:\n  found: x"})
        write_state(repo, state)

        output = run(repo, "decide", "keep", "--by", "user", "--ruling", RULING)

        self.assertIn("change: writes the CSV export", output)


class ReviewReportEdgeTest(unittest.TestCase):
    # Defect: after-review re-reads the old packet when the reviewer saved no new one.
    @unittest.expectedFailure
    def test_after_review_refuses_a_packet_older_than_the_review_dispatch(self):
        repo = make_repo(self)
        write_state(repo, coder_state(repo, ["a.py"]))
        save_report(repo, "review-loop", "review", REVIEW_PACKET)
        first_output = run(repo, "after-review")
        run(repo, "decide", "keep", "--by", "user", "--ruling", RULING)

        output = run(repo, "after-review")

        self.assertIn("ACTION: ask-user", first_output)
        self.assertIn("ACTION: stop", output)
        self.assertNotIn("ACTION: ask-user", output)
        self.assertIn("review-loop", say_text(repo))

    # Defect: an ask with a non-string field crashes after-review with a TypeError.
    @unittest.expectedFailure
    def test_ask_with_a_non_string_field_stops_without_a_crash(self):
        repo = make_repo(self)
        write_state(repo, coder_state(repo, ["a.py"]))
        save_report(repo, "review-loop", "review",
                    'status: converged\niter: 1\nfixed: []\nask: {"file_line": ["a.py:1"], "question": "keep it?"}\n')

        output = run(repo, "after-review")

        self.assertNotIn("Traceback", output)
        self.assertIn("ACTION: stop", output)
        self.assertIn("ask", say_text(repo))


if __name__ == "__main__":
    unittest.main(verbosity=1)
