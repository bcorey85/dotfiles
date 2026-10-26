import pathlib
import sys
import tempfile
import unittest

import toolkit_paths

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures" / "plan_finalization"
sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import plan_format  # noqa: E402


def fixture(name):
    return (FIXTURES / name).read_text()


class AcDriftTest(unittest.TestCase):
    def failures(self, criteria_name, spec_name="spec_plain.md"):
        return plan_format.ac_drift_failures(fixture("ticket.md"), fixture(criteria_name), fixture(spec_name))

    def test_an_exact_match_after_markdown_and_whitespace_normalising_passes(self):
        self.assertEqual(self.failures("criteria_exact.md"), [])

    def test_criteria_in_another_order_with_an_extra_one_pass(self):
        self.assertEqual(self.failures("criteria_reordered.md"), [])

    def test_a_reworded_criterion_with_no_sign_off_fails_and_quotes_the_ticket_text(self):
        failures = self.failures("criteria_drifted.md")
        self.assertEqual(len(failures), 1)
        self.assertIn("reuses the cached", failures[0])
        self.assertIn("no AC in the criteria file carries this wording and no sign-off names it", failures[0])

    def test_a_criterion_split_in_two_with_no_sign_off_fails(self):
        self.assertEqual(len(self.failures("criteria_split.md")), 1)

    def test_a_reworded_criterion_with_a_sign_off_naming_it_passes(self):
        self.assertEqual(self.failures("criteria_signed.md"), [])

    def test_a_ticket_with_no_criteria_heading_has_nothing_to_drift_from(self):
        ticket_text = "# LED-37\n\n## Background\n\nSome words.\n"
        failures = plan_format.ac_drift_failures(ticket_text, fixture("criteria_exact.md"), fixture("spec_plain.md"))
        self.assertEqual(failures, [])
        with self.assertRaises(plan_format.NoCriteriaHeadingError):
            plan_format.ticket_criteria(ticket_text)

    def test_a_missing_criterion_fails(self):
        self.assertEqual(len(self.failures("criteria_missing.md")), 1)

    def test_a_missing_criterion_with_a_sign_off_in_plan_deviations_passes(self):
        self.assertEqual(self.failures("criteria_missing.md", "spec_signs_off.md"), [])


class SpecFailuresTest(unittest.TestCase):
    def failures(self, criteria_name):
        with tempfile.TemporaryDirectory() as task_dir:
            task_path = pathlib.Path(task_dir)
            (task_path / "00-ticket.md").write_text(fixture("ticket.md"))
            (task_path / "acceptance-criteria.md").write_text(fixture(criteria_name))
            (task_path / "spec.md").write_text(fixture("spec_plain.md"))
            return plan_format.spec_ac_failures(task_path / "spec.md")

    def test_the_plan_check_reads_the_ticket_beside_the_spec(self):
        self.assertEqual(self.failures("criteria_exact.md"), [])
        self.assertEqual(len(self.failures("criteria_drifted.md")), 1)


if __name__ == "__main__":
    unittest.main()
