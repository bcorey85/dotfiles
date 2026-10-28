import pathlib
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths

CODE_STEP = toolkit_paths.CODE_DIR / "code_step.py"
FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures" / "spec_ac_check"
sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import plan_format  # noqa: E402


def fixture(name):
    return (FIXTURES / name).read_text()


class AcReferenceFailuresTest(unittest.TestCase):
    def failures(self, spec_name, criteria_text=None):
        criteria = fixture("criteria.md") if criteria_text is None else criteria_text
        return plan_format.ac_reference_failures(fixture(spec_name), criteria)

    def test_reference_to_the_same_criterion_passes(self):
        self.assertEqual(self.failures("spec_match.md"), [])

    def test_reference_to_a_different_criterion_than_the_ticket_numbered_fails(self):
        failures = self.failures("spec_mismatch.md")
        self.assertEqual(len(failures), 1)
        self.assertIn("spec.md:2:", failures[0])
        self.assertIn("Write `ticket ", failures[0])

    def test_ticket_prefixed_reference_is_not_checked(self):
        self.assertEqual(self.failures("spec_ticket_prefixed.md"), [])

    def test_reference_to_an_id_the_criteria_file_lacks_fails(self):
        failures = self.failures("spec_missing_id.md")
        self.assertEqual(len(failures), 1)
        self.assertIn("not an id", failures[0])

    def test_every_bare_reference_fails_when_there_is_no_criteria_file(self):
        failures = plan_format.ac_reference_failures(fixture("spec_two_refs.md"), None)
        self.assertEqual(len(failures), 2)

    def test_reference_in_a_fenced_block_is_skipped(self):
        self.assertEqual(self.failures("spec_fenced.md"), [])

    def test_wording_on_the_next_line_counts(self):
        self.assertEqual(self.failures("spec_next_line.md"), [])

    def test_duplicate_criteria_id_raises(self):
        repeated = fixture("criteria.md") + "\n" + fixture("criteria.md").splitlines()[2] + "\n"
        with self.assertRaises(plan_format.PlanFormatError):
            self.failures("spec_match.md", repeated)


class PlanCheckAcTest(unittest.TestCase):
    def plan_check(self, spec_name, file_name="spec.md"):
        with tempfile.TemporaryDirectory() as task_dir:
            task_path = pathlib.Path(task_dir)
            spec_path = task_path / file_name
            spec_path.write_text(fixture(spec_name))
            (task_path / "acceptance-criteria.md").write_text(fixture("criteria.md"))
            return subprocess.run([sys.executable, str(CODE_STEP), "plan", "check", str(spec_path)],
                                  cwd=task_dir, capture_output=True, text=True, check=False)

    def test_mismatched_reference_fails_the_check_and_names_the_line(self):
        done = self.plan_check("spec_mismatch.md")
        self.assertEqual(done.returncode, 1, done.stderr)
        self.assertIn("spec.md:2:", done.stdout)

    def test_matching_reference_passes_the_check(self):
        done = self.plan_check("spec_match.md")
        self.assertNotIn("AC", done.stdout)

    def test_a_file_not_named_spec_is_not_read_against_the_criteria(self):
        done = self.plan_check("spec_mismatch.md", "check.md")
        self.assertNotIn("shares no wording", done.stdout)


class FinalPlanCheckTest(unittest.TestCase):
    SPEC_WITH_CRITERIA_SECTION = "# Spec\n\n## Acceptance Criteria\n\nSee the criteria file.\n"

    def final_check(self, criteria_text, final=True):
        with tempfile.TemporaryDirectory() as task_dir:
            task_path = pathlib.Path(task_dir)
            spec_path = task_path / "spec.md"
            spec_path.write_text(self.SPEC_WITH_CRITERIA_SECTION)
            if criteria_text is not None:
                (task_path / "acceptance-criteria.md").write_text(criteria_text)

            flags = ["--final"] if final else []
            return subprocess.run([sys.executable, str(CODE_STEP), "plan", "check", *flags, str(spec_path)],
                                  cwd=task_dir, capture_output=True, text=True, check=False)

    def test_final_check_fails_a_spec_whose_criteria_file_is_missing_and_names_the_step(self):
        done = self.final_check(None)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("acceptance-criteria.md: missing or empty", done.stdout)
        self.assertIn("dispatch spec-criteria", done.stdout)

    def test_final_check_fails_an_empty_criteria_file(self):
        done = self.final_check("  \n")
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("acceptance-criteria.md: missing or empty", done.stdout)

    def test_final_check_passes_the_missing_file_row_once_criteria_exist(self):
        done = self.final_check(fixture("criteria.md"))
        self.assertEqual((done.returncode, done.stdout, done.stderr), (0, "", ""))

    def test_final_check_with_no_criteria_section_and_no_file_does_not_report_a_missing_file(self):
        with tempfile.TemporaryDirectory() as task_dir:
            spec_path = pathlib.Path(task_dir) / "spec.md"
            spec_path.write_text("# Spec\n\n## Approach\n\nx\n")
            done = subprocess.run([sys.executable, str(CODE_STEP), "plan", "check", "--final", str(spec_path)],
                                  cwd=task_dir, capture_output=True, text=True, check=False)
        self.assertEqual((done.returncode, done.stdout, done.stderr), (0, "", ""))

    def test_plain_check_does_not_ask_for_the_criteria_file_written_after_the_spec(self):
        done = self.final_check(None, final=False)
        self.assertEqual((done.returncode, done.stdout, done.stderr), (0, "", ""))



class PlanHelpTest(unittest.TestCase):
    def test_a_help_flag_after_plan_or_a_plan_subcommand_prints_usage_and_exits_zero(self):
        for words in (["--help"], ["-h"], ["check", "--help"], ["check", "--final", "--help"], ["parse", "--help"]):
            with self.subTest(words=words), tempfile.TemporaryDirectory() as empty_dir:
                done = subprocess.run([sys.executable, str(CODE_STEP), "plan", *words], cwd=empty_dir,
                                      capture_output=True, text=True, check=False)

                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertIn("usage: code_step.py plan", done.stdout)
                self.assertNotIn("Traceback", done.stderr)


if __name__ == "__main__":
    unittest.main()
