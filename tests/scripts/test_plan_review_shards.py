import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

from toolkit_paths import TOOLS_DIR

SCRIPT = pathlib.Path(os.environ.get("PLAN_REVIEW_SHARDS_SCRIPT") or TOOLS_DIR / "plan_review_shards.py")
PHASE_BODY_LINES = 120


def phase(number, body_lines=PHASE_BODY_LINES):
    body = [f"phase {number} line {index}" for index in range(body_lines)]
    return [f"## Phase {number}: step {number}", *body]


def long_plan(phase_count=4):
    lines = ["# Plan", "front matter line"]
    for number in range(1, phase_count + 1):
        lines += phase(number)
    lines += ["## Phase Status", "back matter line"]
    return lines


class PlanReviewShardsTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.task_dir = pathlib.Path(temp.name)
        self.plan = self.task_dir / "spec.md"

    def write_plan(self, lines):
        self.plan.write_text("\n".join(lines) + "\n")

    def run_script(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)

    def cut(self):
        result = self.run_script("cut", str(self.plan))
        paths = [pathlib.Path(line) for line in result.stdout.splitlines()]
        for path in paths:
            if path != self.plan:
                self.addCleanup(self.run_script, "clean", str(path.parent))
        return result, paths

    def test_a_plan_at_or_under_400_lines_is_reviewed_whole(self):
        self.write_plan(long_plan(phase_count=2))
        result, paths = self.cut()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(paths, [self.plan])

    def test_the_400_line_limit_is_inclusive(self):
        for total, expected_paths in ((400, 1), (401, 2)):
            with self.subTest(total=total):
                first = 200
                second = total - 3 - first
                self.write_plan(["# Plan", *phase(1, first), *phase(2, second)])
                self.assertEqual(len(self.plan.read_text().splitlines()), total)
                result, paths = self.cut()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(len(paths), expected_paths, f"{total} lines")

    def test_a_block_between_phases_lands_in_both_shards_in_file_order(self):
        lines = ["# Plan", *phase(1), *phase(2), "## Notes", "notes line", *phase(3), *phase(4),
                 "## Phase Status", "back matter line"]
        self.write_plan(lines)
        _, (shard_a, shard_b) = self.cut()
        text_a = shard_a.read_text()
        text_b = shard_b.read_text()
        self.assertEqual(len(text_a.splitlines()), len(lines) - 2 * (PHASE_BODY_LINES + 1))
        for text in (text_a, text_b):
            self.assertLess(text.index("# Plan"), text.index("## Notes"))
            self.assertLess(text.index("## Notes\nnotes line\n"), text.index("## Phase Status"))
        self.assertLess(text_a.index("## Phase 2:"), text_a.index("## Notes"))
        self.assertLess(text_b.index("## Notes"), text_b.index("## Phase 3:"))

    def test_a_long_plan_cuts_two_shards_outside_the_plan_folder(self):
        self.write_plan(long_plan())
        result, paths = self.cut()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(paths), 2)
        for path in paths:
            self.assertFalse(path.is_relative_to(self.task_dir), path)
            self.assertTrue(path.is_file(), path)
        self.assertEqual(sorted(child.name for child in self.task_dir.iterdir()), ["spec.md"])

    def test_each_shard_holds_front_matter_half_the_phases_and_back_matter(self):
        self.write_plan(long_plan())
        _, (shard_a, shard_b) = self.cut()
        text_a = shard_a.read_text()
        text_b = shard_b.read_text()
        for text in (text_a, text_b):
            self.assertTrue(text.startswith("# Plan\nfront matter line\n"))
            self.assertTrue(text.endswith("## Phase Status\nback matter line\n"))
        self.assertIn("## Phase 2: step 2", text_a)
        self.assertNotIn("## Phase 3: step 3", text_a)
        self.assertIn("## Phase 3: step 3", text_b)
        self.assertNotIn("## Phase 2: step 2", text_b)

    def test_the_split_falls_at_the_phase_boundary_nearest_the_midpoint(self):
        lines = ["# Plan", *phase(1, 300), *phase(2, 40), *phase(3, 40), *phase(4, 40)]
        self.write_plan(lines)
        _, (shard_a, shard_b) = self.cut()
        self.assertNotIn("## Phase 2:", shard_a.read_text())
        self.assertIn("## Phase 2:", shard_b.read_text())

    def test_a_long_plan_with_one_phase_is_reviewed_whole(self):
        self.write_plan(["# Plan", *phase(1, 450)])
        result, paths = self.cut()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(paths, [self.plan])

    def test_a_phase_id_with_two_sections_stops_the_cut(self):
        self.write_plan([*long_plan(), *phase(2)])
        result, paths = self.cut()
        self.assertEqual(result.returncode, 1)
        self.assertIn("Phase 2 has two sections", result.stderr)
        self.assertEqual(paths, [])

    def test_clean_removes_the_shard_folder(self):
        self.write_plan(long_plan())
        _, (shard_a, _) = self.cut()
        result = self.run_script("clean", str(shard_a.parent))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(shard_a.parent.exists())

    def test_clean_refuses_a_folder_cut_did_not_make(self):
        result = self.run_script("clean", str(self.task_dir))
        self.assertEqual(result.returncode, 1)
        self.assertTrue(self.plan.parent.exists())

    def test_clean_refuses_a_prefixed_folder_outside_the_temp_dir(self):
        decoy = self.task_dir / "plan-review-shards-x"
        decoy.mkdir()
        result = self.run_script("clean", str(decoy))
        self.assertEqual(result.returncode, 1)
        self.assertTrue(decoy.exists())

    def test_clean_of_a_missing_shard_folder_fails_loudly(self):
        missing = pathlib.Path(tempfile.gettempdir()) / "plan-review-shards-doesnotexist"
        result = self.run_script("clean", str(missing))
        self.assertEqual(result.returncode, 1)
        self.assertIn(str(missing), result.stderr)


if __name__ == "__main__":
    unittest.main()
