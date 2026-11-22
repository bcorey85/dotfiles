"""Runs hunk-review-pane against stub herdr and hunk commands.

Checks that a pane started by hand names itself `review` so nvim-jump finds it, and that outside herdr nothing renames.
"""
import os
import pathlib
import subprocess
import tempfile
import unittest

from stubs import write_stub

BIN_DIR = pathlib.Path(__file__).resolve().parents[2] / "scripts" / ".local" / "bin"
HUNK_REVIEW_PANE = BIN_DIR / "hunk-review-pane"


class HunkReviewPaneRenameTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = pathlib.Path(os.path.realpath(scratch.name))
        stub_dir = self.root / "stubs"
        stub_dir.mkdir()
        self.stub_dir = stub_dir
        self.herdr_args = self.root / "herdr-args"
        write_stub(stub_dir / "herdr", f'printf "%s\\n" "$*" >> {self.herdr_args}')
        write_stub(stub_dir / "hunk", "exit 0")
        write_stub(stub_dir / "hunk-untracked-flag", "exit 0")
        self.env = {
            "PATH": f"{stub_dir}:{BIN_DIR}:{os.environ['PATH']}",
            "HOME": str(self.root),
            "XDG_RUNTIME_DIR": str(self.root),
        }

    def run_pane(self, **extra_env):
        env = {**self.env, **extra_env}
        return subprocess.run([str(HUNK_REVIEW_PANE)], env=env, cwd=self.root, capture_output=True, text=True)

    def test_unlabeled_pane_renames_itself_review(self):
        result = self.run_pane(HERDR_PANE_ID="p7")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.herdr_args.read_text().splitlines(), ["pane rename p7 review"])

    def test_outside_herdr_makes_no_rename_call(self):
        result = self.run_pane()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.herdr_args.exists())

    def test_failed_rename_does_not_stop_the_review(self):
        write_stub(self.stub_dir / "herdr", "exit 1")
        result = self.run_pane(HERDR_PANE_ID="p7")
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
