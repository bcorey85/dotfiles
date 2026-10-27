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


if __name__ == "__main__":
    unittest.main()
