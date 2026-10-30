"""Checks for install/check-script-links, which names every script in scripts/.local/bin that ~/.local/bin does not
link to the file itself."""
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

import toolkit_paths  # noqa: F401  (guards the real ledger for every test process)

DOTFILES_DIR = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = DOTFILES_DIR / "install" / "check-script-links"
SOURCE_DIR = DOTFILES_DIR / "scripts" / ".local" / "bin"


class CheckScriptLinksTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = pathlib.Path(self.tmp.name)
        self.target_dir = self.home / ".local" / "bin"
        self.target_dir.mkdir(parents=True)
        self.scripts = sorted(path for path in SOURCE_DIR.iterdir() if path.is_file())
        for script in self.scripts:
            (self.target_dir / script.name).symlink_to(script)

    def run_check(self):
        environment = {"PATH": os.environ["PATH"], "HOME": str(self.home)}
        return subprocess.run([str(SCRIPT)], capture_output=True, text=True, env=environment)

    def test_every_script_linked_passes(self):
        finished = self.run_check()
        self.assertEqual(finished.returncode, 0, finished.stdout + finished.stderr)
        self.assertNotIn("not linked", finished.stdout)

    def test_relative_links_pass(self):
        for script in self.scripts:
            link = self.target_dir / script.name
            link.unlink()
            os.symlink(os.path.relpath(script, self.target_dir), link)

        finished = self.run_check()

        self.assertEqual(finished.returncode, 0, finished.stdout + finished.stderr)
        self.assertNotIn("not linked", finished.stdout)

    def test_folded_target_dir_passes(self):
        shutil.rmtree(self.target_dir)
        self.target_dir.symlink_to(SOURCE_DIR)

        finished = self.run_check()

        self.assertEqual(finished.returncode, 0, finished.stdout + finished.stderr)
        self.assertNotIn("not linked", finished.stdout)

    def test_a_missing_script_is_named_and_fails(self):
        missing = self.scripts[0].name
        (self.target_dir / missing).unlink()

        finished = self.run_check()

        self.assertEqual(finished.returncode, 1)
        self.assertIn(f"{missing} is not linked", finished.stdout)
        self.assertIn("default ignore list", finished.stdout)
        for script in self.scripts[1:]:
            self.assertNotIn(f"{script.name} is not linked", finished.stdout)

    def test_an_entry_pointing_elsewhere_is_flagged(self):
        elsewhere = self.scripts[0].name
        other_file = self.home / "other-file"
        other_file.write_text("#!/bin/sh\n")
        (self.target_dir / elsewhere).unlink()
        (self.target_dir / elsewhere).symlink_to(other_file)

        finished = self.run_check()

        self.assertEqual(finished.returncode, 1)
        self.assertIn(f"{elsewhere} is not linked", finished.stdout)

    def test_a_dangling_link_is_named_and_fails(self):
        dangling = self.scripts[0].name
        (self.target_dir / dangling).unlink()
        (self.target_dir / dangling).symlink_to(self.home / "gone")

        finished = self.run_check()

        self.assertEqual(finished.returncode, 1)
        self.assertIn(f"{dangling} is not linked", finished.stdout)


if __name__ == "__main__":
    unittest.main()
