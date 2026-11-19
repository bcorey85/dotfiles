"""Tests for lib/check_parts.py: the joined multi-part check command and the readers of what it prints."""
import subprocess
import sys
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import check_parts


class JoinPartsTest(unittest.TestCase):
    def run_joined(self, exit_codes):
        parts = [(f"part{code}", [f"(exit {code})"]) for code in exit_codes]
        return self.run_joined_parts(parts)

    def run_joined_parts(self, parts, shell="sh"):
        return subprocess.run([shell, "-c", check_parts.join_parts(parts)], capture_output=True, text=True)

    def test_a_127_never_replaces_a_failing_code_in_either_order(self):
        for exit_codes in ([3, 127, 0], [127, 3, 0]):
            with self.subTest(exit_codes=exit_codes):
                completed = self.run_joined(exit_codes)

                self.assertEqual(3, completed.returncode)
                names = " ".join(f"part{code}" for code in exit_codes if code != 0)
                self.assertEqual(f"{check_parts.FAILED_PARTS_MARKER} {names}",
                                 completed.stdout.strip().splitlines()[-1])

    def test_each_part_prints_its_own_name_and_exit_code_after_its_output(self):
        completed = self.run_joined([3, 0])

        part_lines = [line for line in completed.stdout.splitlines() if line.startswith("PART ")]
        self.assertEqual(["PART part3 exit 3", "PART part0 exit 0"], part_lines)

    def test_the_joined_command_runs_in_zsh_where_status_is_read_only(self):
        parts = [("first", ["(exit 3)"]), ("second", ["(exit 127)"]), ("third", ["true"])]

        completed = self.run_joined_parts(parts, shell="zsh")

        self.assertEqual(3, completed.returncode, completed.stderr)
        self.assertIn("FAILED PARTS: first second", completed.stdout)

    def test_a_hash_in_a_part_command_does_not_comment_out_the_rest_of_the_part(self):
        parts = [("first", ["echo one # note"]), ("second", ["(exit 4)"])]

        completed = self.run_joined_parts(parts)

        self.assertEqual(4, completed.returncode, completed.stderr)
        self.assertIn("one", completed.stdout)
        self.assertIn("FAILED PARTS: second", completed.stdout)

    def test_parts_that_all_exit_127_exit_127(self):
        completed = self.run_joined([127, 127])

        self.assertEqual(127, completed.returncode)

    def test_a_single_part_is_its_plain_command(self):
        self.assertEqual("a && b", check_parts.join_parts([("only", ["a", "b"])]))

    def test_a_part_name_outside_the_name_pattern_is_refused(self):
        with self.assertRaises(ValueError):
            check_parts.join_parts([("a b", ["true"]), ("c", ["true"])])


class ReadPartsTest(unittest.TestCase):
    def test_failed_part_names_reads_only_the_marker_line(self):
        lines = ["FAILED: lint x", "FAILED PARTS: package python", "tests ok"]

        self.assertEqual(["package", "python"], check_parts.failed_part_names(lines))

    def test_part_results_give_each_part_its_own_section_of_output(self):
        output = "npm out\n\nPART package exit 1\npy out\nmore\n\nPART python exit 127\nFAILED PARTS: package python\n"

        results = check_parts.part_results(output)

        self.assertEqual(["package", "python"], [part.name for part in results])
        self.assertEqual([1, 127], [part.code for part in results])
        self.assertEqual("npm out\n", results[0].text)
        self.assertIn("py out", results[1].text)
        self.assertNotIn("npm out", results[1].text)

    def test_the_output_of_a_command_that_is_not_joined_gives_no_results(self):
        self.assertEqual([], check_parts.part_results("1 failed in 0.1s\n"))

    def test_the_output_of_a_real_joined_run_reads_back(self):
        parts = [("first", ["echo one; (exit 2)"]), ("second", ["echo two"])]
        completed = subprocess.run(["sh", "-c", check_parts.join_parts(parts)], capture_output=True, text=True)

        results = check_parts.part_results(completed.stdout)

        self.assertEqual([("first", 2), ("second", 0)], [(part.name, part.code) for part in results])
        self.assertIn("one", results[0].text)


if __name__ == "__main__":
    unittest.main()
