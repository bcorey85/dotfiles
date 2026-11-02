"""Checks for the scripted fix_induced tag: lib/diff_ranges.py reads the lines a diff changes, and
review/review_loop_fix_induced.py plus review_loop_script.telemetry tag a round-two finding from the fix before it."""
import difflib
import importlib.util
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
import diff_ranges
import review_loop_fix_induced

OLD = [f"line {number}" for number in range(1, 41)]
NEW = list(OLD)
NEW[19] = "line 20 changed"  # line 20 is rewritten
NEW.insert(30, "inserted after 30")  # becomes line 31


def fix_diff():
    difference = difflib.unified_diff(OLD, NEW, "a/src/mod.py", "b/src/mod.py", n=12, lineterm="")
    return "\n".join(difference)


class ChangedRangesTest(unittest.TestCase):
    def test_context_lines_are_not_changes_and_each_run_is_one_range(self):
        ranges = diff_ranges.changed_ranges(fix_diff())

        self.assertEqual(ranges, {"src/mod.py": [(20, 20), (31, 31)]})

    def test_a_pure_deletion_is_the_one_line_where_it_was(self):
        old = ["a", "b", "c", "d"]
        diff = "\n".join(difflib.unified_diff(old, ["a", "d"], "a/f.py", "b/f.py", n=0, lineterm=""))

        self.assertEqual(diff_ranges.changed_ranges(diff), {"f.py": [(2, 2)]})

    def test_a_removed_line_that_looks_like_a_file_header_is_a_body_line(self):
        diff = "--- a/f.py\n+++ b/f.py\n@@ -1,2 +1,1 @@\n--- a/not-a-header\n keep"

        self.assertEqual(diff_ranges.changed_ranges(diff), {"f.py": [(1, 1)]})

    def test_a_body_line_with_no_marker_is_refused(self):
        diff = "--- a/f.py\n+++ b/f.py\n@@ -1,1 +1,1 @@\n?bad"

        with self.assertRaises(ValueError):
            diff_ranges.changed_ranges(diff)

    def test_the_slack_widens_a_range_by_the_named_constant_each_side(self):
        slack = diff_ranges.RANGE_SLACK

        self.assertTrue(diff_ranges.in_ranges([(20, 22)], 20 - slack))
        self.assertTrue(diff_ranges.in_ranges([(20, 22)], 22 + slack))
        self.assertFalse(diff_ranges.in_ranges([(20, 22)], 20 - slack - 1))
        self.assertFalse(diff_ranges.in_ranges([(20, 22)], 22 + slack + 1))


class FixInducedTagTest(unittest.TestCase):
    def setUp(self):
        self.ranges = diff_ranges.changed_ranges(fix_diff())

    def tag(self, existing, iter_number, path, line):
        return review_loop_fix_induced.fix_induced_tag(existing, iter_number, path, line, self.ranges)

    def test_a_round_two_finding_inside_a_fix_hunk_tags_yes(self):
        self.assertEqual(self.tag("", 2, "src/mod.py", 21), "yes")

    def test_a_round_two_finding_outside_every_fix_hunk_tags_no(self):
        self.assertEqual(self.tag("", 2, "src/mod.py", 5), "no")
        self.assertEqual(self.tag("", 2, "src/other.py", 21), "no")

    def test_a_round_one_finding_stays_untagged(self):
        self.assertEqual(self.tag("", 1, "src/mod.py", 20), "")

    def test_a_finding_with_no_file_or_line_stays_untagged(self):
        self.assertEqual(self.tag("", 2, "", 0), "")
        self.assertEqual(self.tag("", 2, "src/mod.py", 0), "")

    def test_a_value_the_reviewer_set_is_kept(self):
        self.assertEqual(self.tag("bug", 2, "src/mod.py", 5), "bug")
        self.assertEqual(self.tag("no", 2, "src/mod.py", 20), "no")


class TelemetryWiringTest(unittest.TestCase):
    """The loop's finding rows carry the tag, read from the fix diff the earlier round wrote in the state folder."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.out = pathlib.Path(temp.name)
        (self.out / "round1-fix.diff").write_text(fix_diff())

        script = toolkit_paths.REVIEW_DIR / "review_loop_script.py"
        spec = importlib.util.spec_from_file_location("review_loop_script_fix_induced_under_test", script)
        self.loop_script = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.loop_script)

    def finding_commands(self, iter_number, path, line, **extra):
        parsed = self.loop_script.parse_finding(f"`{path}:{line}` [bug] something is wrong")
        entry = {"finding": parsed, "disposition": "nit", "actioned": "none", "source": "", "spot": "s", **extra}
        row = {"iter": iter_number, "gate": "code-reviewer", "loc": 1, "result": "PASS", "findings": [entry]}
        tallies = {"fix": 0, "ask": 0, "nit": 1, "blocker": 0, "fixed": 0, "skipped_fp": 0, "smells": 0,
                   "result": "PASS"}
        calls = []
        def record(_repo, command):
            calls.append(command)
            return 0, ""

        with mock.patch.object(self.loop_script, "log_call", side_effect=record):
            self.loop_script.telemetry("/repo", "sess", "lane", [], iter_number, tallies, [row], self.out)
        return [cmd for cmd in calls if "kind=finding" in cmd]

    def test_a_round_two_finding_in_the_fix_gets_yes_and_one_outside_gets_no(self):
        inside = self.finding_commands(2, "src/mod.py", 21)[0]
        outside = self.finding_commands(2, "src/mod.py", 5)[0]

        self.assertIn("fix_induced=yes", inside)
        self.assertIn("fix_induced=no", outside)

    def test_a_round_one_finding_gets_no_fix_induced_key(self):
        command = self.finding_commands(1, "src/mod.py", 21)[0]

        self.assertFalse([part for part in command if part.startswith("fix_induced=")])

    def test_a_reviewer_set_value_reaches_the_row_unchanged(self):
        command = self.finding_commands(2, "src/mod.py", 5, fix_induced="bug")[0]

        self.assertIn("fix_induced=bug", command)


if __name__ == "__main__":
    unittest.main()
