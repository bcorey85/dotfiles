"""Checks for tests/duplicate_code.py, the run.sh check that fails when the toolkit scripts gain duplicate code."""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPT = pathlib.Path(os.environ.get("DUPLICATE_CODE_SCRIPT")
                      or pathlib.Path(__file__).resolve().parents[1] / "duplicate_code.py")

GIT_OUTPUT_HELPER = '''import subprocess


def git_output(cwd, *args):
    finished = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)
    return finished.stdout.strip()
'''

# Long enough to pass jscpd's default 50-token floor; planted under two different function names.
COPIED_BLOCK = '''
def {name}(path, limit):
    lines = path.read_text().splitlines()
    kept = [line.strip() for line in lines if line.strip() and not line.startswith("#")]
    if len(kept) > limit:
        raise ValueError(f"{{path}} holds {{len(kept)}} lines, over the limit of {{limit}}")
    counts = {{}}
    for line in kept:
        counts[line] = counts.get(line, 0) + 1
    return sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
'''


class DuplicateCodeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.scripts_dir = self.root / "claude" / ".claude" / "scripts"
        (self.root / "claude" / ".claude" / "hooks").mkdir(parents=True)
        self.write_script("lib/script_utils.py", GIT_OUTPUT_HELPER)
        self.write_script("gates/some_gate.py", "def run(raw):\n    return raw\n\n\ndef main():\n    run('')\n")
        self.write_baseline({}, {})

    def write_script(self, relative_path, text):
        path = self.scripts_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def write_baseline(self, same_name_functions, jscpd_clone_pairs):
        baseline = {"same_name_functions": same_name_functions, "jscpd_clone_pairs": jscpd_clone_pairs}
        baseline_path = self.root / "tests" / "duplicate_code_baseline.json"
        baseline_path.parent.mkdir(exist_ok=True)
        baseline_path.write_text(json.dumps(baseline))

    def read_baseline(self):
        return json.loads((self.root / "tests" / "duplicate_code_baseline.json").read_text())

    def run_check(self, *extra_arguments, with_npx=False):
        # An empty PATH hides npx, so the name check runs alone and fast.
        search_path = os.environ["PATH"] if with_npx else self.tmp.name
        environment = {"PATH": search_path, "HOME": os.environ["HOME"]}
        command = [sys.executable, str(SCRIPT), "--root", str(self.root), *extra_arguments]
        return subprocess.run(command, capture_output=True, text=True, env=environment)

    def test_clean_tree_passes(self):
        finished = self.run_check()
        self.assertEqual(finished.returncode, 0, finished.stderr)

    def test_planted_copy_of_a_shared_helper_fails(self):
        self.write_script("gates/some_gate.py", GIT_OUTPUT_HELPER)
        finished = self.run_check()
        self.assertEqual(finished.returncode, 1)
        self.assertIn("def git_output", finished.stderr)
        self.assertIn("new: claude/.claude/scripts/gates/some_gate.py", finished.stderr)

    def test_repeat_in_the_baseline_passes(self):
        self.write_script("gates/some_gate.py", GIT_OUTPUT_HELPER)
        repeat_files = ["claude/.claude/scripts/gates/some_gate.py", "claude/.claude/scripts/lib/script_utils.py"]
        self.write_baseline({"git_output": repeat_files}, {})
        finished = self.run_check()
        self.assertEqual(finished.returncode, 0, finished.stderr)

    def test_third_file_joining_a_baseline_repeat_fails(self):
        self.write_script("gates/some_gate.py", GIT_OUTPUT_HELPER)
        self.write_script("review/other_gate.py", GIT_OUTPUT_HELPER)
        repeat_files = ["claude/.claude/scripts/gates/some_gate.py", "claude/.claude/scripts/lib/script_utils.py"]
        self.write_baseline({"git_output": repeat_files}, {})
        finished = self.run_check()
        self.assertEqual(finished.returncode, 1)
        self.assertIn("new: claude/.claude/scripts/review/other_gate.py", finished.stderr)

    def test_entry_point_names_may_repeat(self):
        self.write_script("review/other_gate.py", "def run(raw):\n    return raw\n\n\ndef main():\n    run('')\n")
        finished = self.run_check()
        self.assertEqual(finished.returncode, 0, finished.stderr)

    def test_vendored_skill_copies_are_out_of_scope(self):
        vendored_dir = self.root / "claude" / ".claude" / "skills" / "synced" / "docx" / "scripts" / "office"
        vendored_dir.mkdir(parents=True)
        (vendored_dir / "pack.py").write_text(GIT_OUTPUT_HELPER)
        finished = self.run_check()
        self.assertEqual(finished.returncode, 0, finished.stderr)

    def test_shrunk_baseline_fails_until_shrink_removes_it(self):
        repeat_files = ["claude/.claude/scripts/gates/some_gate.py", "claude/.claude/scripts/lib/script_utils.py"]
        self.write_baseline({"git_output": repeat_files}, {})
        finished = self.run_check()
        self.assertEqual(finished.returncode, 1)
        self.assertIn("baseline shrank: def git_output", finished.stderr)

        shrunk = self.run_check("--shrink")
        self.assertEqual(shrunk.returncode, 0, shrunk.stderr)
        self.assertEqual(self.read_baseline()["same_name_functions"], {})

    def test_shrink_never_adds_a_new_repeat(self):
        self.write_script("gates/some_gate.py", GIT_OUTPUT_HELPER)
        finished = self.run_check("--shrink")
        self.assertEqual(finished.returncode, 1)
        self.assertEqual(self.read_baseline()["same_name_functions"], {})

    @unittest.skipIf(shutil.which("npx") is None, "npx not installed")
    def test_planted_token_clone_under_another_name_fails(self):
        self.write_script("gates/some_gate.py", COPIED_BLOCK.format(name="ranked_lines"))
        self.write_script("review/other_gate.py", COPIED_BLOCK.format(name="line_counts"))
        finished = self.run_check(with_npx=True)
        self.assertEqual(finished.returncode, 1)
        self.assertIn("claude/.claude/scripts/gates/some_gate.py | claude/.claude/scripts/review/other_gate.py: "
                      "1 clones, baseline 0", finished.stderr)


if __name__ == "__main__":
    unittest.main()
