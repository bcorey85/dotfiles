"""Checks the phase commit subject: the plan's named Commit line wins, and a "none" summary is never a subject.

run: python3 tests/scripts/test_code_step_commit_subject.py
"""
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import toolkit_paths

for folder in (toolkit_paths.LIB_DIR, toolkit_paths.REVIEW_DIR, toolkit_paths.CODE_DIR):
    sys.path.insert(0, str(folder))
import code_step_boundary  # noqa: E402
import code_step_state  # noqa: E402

PLAN = "work/ABC-7-checks/spec.md"
PLAN_TEXT = """# Plan

## Phase A1: pin check names

Do the work.
Commit `ABC-7: pin check names as strings in the spec-class oracle`.

## Phase A2: wire the runner

Nothing is named here.
"""


class CommitSubject(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.repo = pathlib.Path(temp_dir.name)
        (self.repo / PLAN).parent.mkdir(parents=True)
        (self.repo / PLAN).write_text(PLAN_TEXT)

    def message(self, phase, behavior):
        state = code_step_state.RunState(stage="review", plan=PLAN, phase=phase, title=f"title of the stage {phase}",
                                         behavior=behavior, branch="main")
        return code_step_boundary.commit_message(self.repo, state)

    def test_the_plan_named_commit_line_beats_the_coder_summary(self):
        self.assertEqual("ABC-7: pin check names as strings in the spec-class oracle",
                         self.message("A1", ["none (test-only change; pins names)"]))
        self.assertEqual("ABC-7: pin check names as strings in the spec-class oracle",
                         self.message("A1", ["adds a runner"]))

    def test_a_phase_without_a_commit_line_uses_the_coder_summary_and_names_the_phase(self):
        self.assertEqual("ABC-7: adds a runner (phase A2)", self.message("A2", ["adds a runner"]))

    def test_a_none_summary_falls_back_to_the_phase_title(self):
        for summary in ("none (test-only change; pins names)", "None", "  none"):
            with self.subTest(summary=summary):
                self.assertEqual("ABC-7: title of the stage A2 (phase A2)", self.message("A2", [summary]))

    def test_a_summary_that_only_starts_with_the_letters_none_is_kept(self):
        self.assertEqual("ABC-7: nonexistent users get a 404 (phase A2)",
                         self.message("A2", ["nonexistent users get a 404"]))

    def test_a_plan_run_with_no_phase_names_the_plan_folder(self):
        self.assertEqual("ABC-7: adds a runner (plan ABC-7-checks)", self.message(None, ["adds a runner"]))

    def test_a_planless_run_keeps_the_bare_summary(self):
        state = code_step_state.RunState(stage="review", title="t", behavior=["adds a runner"], branch="main")

        self.assertEqual("adds a runner", code_step_boundary.commit_message(self.repo, state))


if __name__ == "__main__":
    unittest.main()
