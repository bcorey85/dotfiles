"""Scratch checks for the code-step.py fixes: packet block scalars, questions in say.md, say.md cleared on a
resumed run, the plan-edit coder after an adopted change, and the per-file change fallback."""
import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[2] / "claude" / ".claude" / "scripts" / "code-step.py"
spec = importlib.util.spec_from_file_location("code_step", SCRIPT)
codeStep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(codeStep)

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


def git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def make_repo():
    repo = pathlib.Path(tempfile.mkdtemp(prefix="codestep-"))
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
    sayFile = repo / ".git" / "code-step" / "say.md"
    return sayFile.read_text() if sayFile.exists() else ""


def save_report(repo, agentType, stage, message):
    row = {"ts": time.time(), "agent_type": agentType, "agent_id": f"{agentType}-1", "stage": stage, "message": message}
    with (repo / ".git" / "code-step" / "reports.jsonl").open("a") as reportsFile:
        reportsFile.write(json.dumps(row) + "\n")


def run(repo, *args):
    done = subprocess.run(["python3", str(SCRIPT), *args], cwd=repo, capture_output=True, text=True)
    return done.stdout + done.stderr


def coder_state(repo, files):
    return {"stage": "review", "plan": "plan.md", "phase": "1", "lane": "eng-spec", "modifier": None,
            "baseline": {}, "files": files, "behavior": ["writes the CSV export"], "why": {}, "flagged": [],
            "testsRun": "none", "coderStage": "coder", "iter": 1}


class ParsePacketTest(unittest.TestCase):
    def test_block_scalar_drops_indicator_and_indent(self):
        packet = codeStep.parse_packet(REVIEW_PACKET)

        self.assertEqual(packet["plan_impact"],
                         "PLAN-IMPACT:\n  assumed: the CSV has a header row\n\n  found: the importer rejects a header row")
        self.assertEqual(packet["fixed"], "[]")
        self.assertEqual(packet["trailer"], "The loop stopped on a plan question.")

    def test_plain_value_is_unchanged(self):
        packet = codeStep.parse_packet("status: converged\nplan_impact: none\niter: 2\n")

        self.assertEqual(packet["plan_impact"], "none")
        self.assertEqual(packet["iter"], "2")


class PlanImpactFlowTest(unittest.TestCase):
    def test_review_impact_writes_the_question_to_say_md(self):
        repo = make_repo()
        write_state(repo, coder_state(repo, ["a.py"]))
        save_report(repo, "review-loop", "review", REVIEW_PACKET)

        output = run(repo, "after-review")

        self.assertIn("ACTION: ask-user", output)
        self.assertNotIn("AskUserQuestion", output + say_text(repo))
        self.assertIn("## Question for the user", say_text(repo))
        self.assertIn("`decide adopt`", say_text(repo))
        self.assertNotIn("|", read_state(repo)["impact"])

    def test_resume_verb_clears_old_say_text(self):
        repo = make_repo()
        state = coder_state(repo, ["a.py"])
        state.update({"stage": "impact-review", "impact": "PLAN-IMPACT:\n  found: no header row"})
        write_state(repo, state)
        (repo / ".git" / "code-step" / "say.md").write_text("Implemented: old summary\n\n")

        run(repo, "decide", "keep")

        self.assertNotIn("old summary", say_text(repo))
        self.assertEqual(say_text(repo).count("Implemented:"), 1)

    def test_discuss_hands_the_question_back(self):
        repo = make_repo()
        state = coder_state(repo, ["a.py"])
        state.update({"stage": "impact-review", "impact": "PLAN-IMPACT:\n  found: no header row"})
        write_state(repo, state)

        output = run(repo, "decide", "discuss")

        self.assertIn("ACTION: ask-user", output)
        self.assertIn("found: no header row", say_text(repo))
        self.assertEqual(read_state(repo)["stage"], "impact-review")

    def test_adopt_dispatches_a_plan_coder_then_the_review(self):
        repo = make_repo()
        state = coder_state(repo, ["a.py"])
        state.update({"stage": "impact-review", "impact": "PLAN-IMPACT:\n  found: no header row"})
        write_state(repo, state)
        (repo / "a.py").write_text("a = 2\n")

        adoptOutput = run(repo, "decide", "adopt")
        stateAfterAdopt = read_state(repo)
        (repo / "plan.md").write_text((repo / "plan.md").read_text().replace("with a header row", "with no header row"))
        reviewOutput = run(repo, "after-plan-edit")
        stateAfterEdit = read_state(repo)

        self.assertIn("AGENT: coder", adoptOutput)
        self.assertIn("Edit only the plan file plan.md", adoptOutput)
        self.assertIn("after-plan-edit", adoptOutput)
        self.assertEqual(stateAfterAdopt["stage"], "plan-coder")
        self.assertIn("## Plan Deviations", (repo / "plan.md").read_text())
        self.assertIn("AGENT: review-loop", reviewOutput)
        self.assertEqual(stateAfterEdit["stage"], "review")
        self.assertEqual(stateAfterEdit["flagged"], [])
        self.assertNotIn("planEditBaseline", stateAfterEdit)
        self.assertIn("Decision: Adopt plan change", reviewOutput)

    def test_plan_coder_code_edit_is_flagged_and_reviewed(self):
        repo = make_repo()
        state = coder_state(repo, ["a.py"])
        state.update({"stage": "impact-review", "impact": "PLAN-IMPACT:\n  found: no header row"})
        write_state(repo, state)

        run(repo, "decide", "adopt")
        (repo / "b.py").write_text("b = 2\n")
        run(repo, "after-plan-edit")
        stateAfterEdit = read_state(repo)

        self.assertIn("b.py", stateAfterEdit["files"])
        self.assertTrue(any("b.py" in flag for flag in stateAfterEdit["flagged"]))

    def test_keep_goes_straight_to_review(self):
        repo = make_repo()
        state = coder_state(repo, ["a.py"])
        state.update({"stage": "impact-coder", "impact": "PLAN-IMPACT:\n  found: no header row"})
        write_state(repo, state)

        output = run(repo, "decide", "keep")

        self.assertIn("AGENT: review-loop", output)
        self.assertEqual(read_state(repo)["stage"], "review")


class ChangeFallbackTest(unittest.TestCase):
    def test_several_files_do_not_share_one_behavior_sentence(self):
        repo = make_repo()
        state = coder_state(repo, ["a.py", "b.py"])
        state.update({"stage": "impact-coder", "impact": "PLAN-IMPACT:\n  found: x"})
        write_state(repo, state)

        output = run(repo, "decide", "keep")

        self.assertNotIn("change: writes the CSV export", output)
        self.assertEqual(output.count("change: changed by the coder"), 2)

    def test_one_file_keeps_the_behavior_sentence(self):
        repo = make_repo()
        state = coder_state(repo, ["a.py"])
        state.update({"stage": "impact-coder", "impact": "PLAN-IMPACT:\n  found: x"})
        write_state(repo, state)

        output = run(repo, "decide", "keep")

        self.assertIn("change: writes the CSV export", output)


if __name__ == "__main__":
    unittest.main(verbosity=1)
