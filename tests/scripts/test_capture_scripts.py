"""bookmark and research stop with a message that says the capture was kept when detach is not installed."""
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

from stubs import write_stub

BIN_DIR = pathlib.Path(__file__).resolve().parents[2] / "scripts" / ".local" / "bin"
RUN_TIMEOUT_SECONDS = 20

CASES = (
    ("bookmark", ["https://example.com/page"], "bookmarks.org",
     "bookmark: logged to bookmarks.org, no source stub:"),
    ("research", ["why", "is", "the", "sky", "blue"], "questions.org",
     "research: logged to questions.org, no answer stub:"),
)


class CaptureWithoutDetachTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = pathlib.Path(os.path.realpath(scratch.name))
        self.script_dir = self.root / "bin"
        self.script_dir.mkdir()
        self.stub_dir = self.root / "stubs"
        self.stub_dir.mkdir()
        self.claude_ran = self.root / "claude-ran"
        write_stub(self.stub_dir / "claude", f"echo ran >> {self.claude_ran}")
        write_stub(self.stub_dir / "sleep", "exit 0")
        self.vault = self.root / "vault"
        # The scripts list notes/ under pipefail, so the folder has to exist.
        (self.vault / "notes").mkdir(parents=True)
        self.env = {
            **os.environ,
            "PATH": f"{self.stub_dir}{os.pathsep}{os.environ['PATH']}",
            "VAULT_DIR": str(self.vault),
            "HOME": str(self.root),
            "XDG_STATE_HOME": str(self.root / "state"),
        }

    def test_a_missing_detach_fails_naming_the_kept_capture_and_starts_no_runner(self):
        for name, args, org_file, message in CASES:
            with self.subTest(script=name):
                shutil.copy(BIN_DIR / name, self.script_dir / name)

                finished = subprocess.run([str(self.script_dir / name), *args], env=self.env,
                                          capture_output=True, text=True, timeout=RUN_TIMEOUT_SECONDS)

                self.assertNotEqual(finished.returncode, 0)
                self.assertIn(message, finished.stderr)
                self.assertIn("detach missing; run install/stow", finished.stderr)
                self.assertTrue((self.vault / "org" / org_file).read_text().strip())
                self.assertFalse(self.claude_ran.exists())


if __name__ == "__main__":
    unittest.main()
