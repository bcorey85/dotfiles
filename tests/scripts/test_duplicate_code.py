"""Checks for tests/duplicate_code.py, the run.sh check that fails when the toolkit scripts hold duplicate code."""
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

HOOK_HANDLER = "def run(raw):\n    return raw\n\n\ndef main():\n    run('')\n"

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

# An import block over the token floor, as every gate opens with, followed by code of its own.
IMPORT_PREAMBLE = '''import contextlib
import json
import os
import pathlib
import re
import subprocess
import sys

sys.path[:0] = [os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib")]
import hook_input
import script_utils
from hook_input import emit_stderr, jq_get, jq_str
'''


class DuplicateCodeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.scripts_dir = self.root / "claude" / ".claude" / "scripts"
        (self.root / "claude" / ".claude" / "hooks").mkdir(parents=True)
        self.write_script("lib/script_utils.py", GIT_OUTPUT_HELPER)
        self.write_script("gates/some_gate.py", HOOK_HANDLER)

    def write_script(self, relative_path, text):
        path = self.scripts_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def run_check(self, with_npx=False):
        # An empty PATH hides npx, so the name check runs alone and fast.
        search_path = os.environ["PATH"] if with_npx else self.tmp.name
        environment = {"PATH": search_path, "HOME": os.environ["HOME"]}
        command = [sys.executable, str(SCRIPT), "--root", str(self.root)]
        return subprocess.run(command, capture_output=True, text=True, env=environment)

    def test_clean_tree_passes(self):
        finished = self.run_check()
        self.assertEqual(finished.returncode, 0, finished.stderr)

    def test_planted_copy_of_a_shared_helper_fails(self):
        self.write_script("gates/some_gate.py", GIT_OUTPUT_HELPER)
        finished = self.run_check()
        self.assertEqual(finished.returncode, 1)
        self.assertIn("def git_output is defined in claude/.claude/scripts/gates/some_gate.py, "
                      "claude/.claude/scripts/lib/script_utils.py", finished.stderr)

    def test_handler_that_main_calls_may_repeat(self):
        self.write_script("review/other_gate.py", HOOK_HANDLER)
        finished = self.run_check()
        self.assertEqual(finished.returncode, 0, finished.stderr)

    def test_handler_name_that_main_does_not_call_fails(self):
        self.write_script("review/one_flow.py", "def run(argv):\n    return argv\n")
        self.write_script("code/other_flow.py", "def run(argv):\n    return argv\n")
        finished = self.run_check()
        self.assertEqual(finished.returncode, 1)
        self.assertIn("def run is defined in", finished.stderr)

    def test_cli_verb_handlers_may_repeat(self):
        self.write_script("review/one_flow.py", "def command_start(args):\n    return args\n")
        self.write_script("code/other_flow.py", "def command_start(args):\n    return args\n")
        finished = self.run_check()
        self.assertEqual(finished.returncode, 0, finished.stderr)

    def test_vendored_skill_copies_are_out_of_scope(self):
        vendored_dir = self.root / "claude" / ".claude" / "skills" / "synced" / "docx" / "scripts" / "office"
        vendored_dir.mkdir(parents=True)
        (vendored_dir / "pack.py").write_text(GIT_OUTPUT_HELPER)
        finished = self.run_check()
        self.assertEqual(finished.returncode, 0, finished.stderr)

    @unittest.skipIf(shutil.which("npx") is None, "npx not installed")
    def test_planted_token_clone_under_another_name_fails(self):
        self.write_script("gates/some_gate.py", COPIED_BLOCK.format(name="ranked_lines"))
        self.write_script("review/other_gate.py", COPIED_BLOCK.format(name="line_counts"))
        finished = self.run_check(with_npx=True)
        self.assertEqual(finished.returncode, 1)
        self.assertIn("jscpd clone claude/.claude/scripts/gates/some_gate.py:", finished.stderr)
        self.assertIn("and claude/.claude/scripts/review/other_gate.py:", finished.stderr)

    @unittest.skipIf(shutil.which("npx") is None, "npx not installed")
    def test_shared_import_block_is_not_a_clone(self):
        self.write_script("gates/some_gate.py", IMPORT_PREAMBLE + HOOK_HANDLER)
        self.write_script("review/other_gate.py", IMPORT_PREAMBLE + "\nLIMIT = 3\n")
        finished = self.run_check(with_npx=True)
        self.assertEqual(finished.returncode, 0, finished.stderr)


if __name__ == "__main__":
    unittest.main()
