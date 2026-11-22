"""The stowed ripgrep config makes a plain rg search hidden folders, and .zshenv hands it to every zsh."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import toolkit_paths


@unittest.skipUnless(shutil.which("rg"), "rg is not installed")
class RipgrepConfigTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        hidden = self.root / ".hidden_dir"
        hidden.mkdir()
        (hidden / "a.txt").write_text("zebracrossing\n")
        git_dir = self.root / ".git"
        git_dir.mkdir()
        (git_dir / "b.txt").write_text("zebracrossing\n")

    def rg(self, env_config):
        env = {k: v for k, v in os.environ.items() if k != "RIPGREP_CONFIG_PATH"}
        if env_config:
            env["RIPGREP_CONFIG_PATH"] = str(env_config)
        done = subprocess.run(["rg", "-l", "zebracrossing", "."], cwd=self.root, env=env,
                              capture_output=True, text=True)
        return done.stdout.split()

    def test_plain_rg_without_config_skips_hidden_folder(self):
        self.assertEqual(self.rg(None), [])

    def test_config_finds_word_under_hidden_folder_and_skips_git(self):
        self.assertEqual(self.rg(toolkit_paths.RIPGREP_CONFIG), ["./.hidden_dir/a.txt"])

    @unittest.skipUnless(shutil.which("zsh"), "zsh is not installed")
    def test_zshenv_exports_config_path_to_non_interactive_zsh(self):
        home = self.root / "home"
        home.mkdir()
        env = {k: v for k, v in os.environ.items() if k != "RIPGREP_CONFIG_PATH"}
        env.update(HOME=str(home), ZDOTDIR=str(toolkit_paths.ZSHENV_DIR))
        done = subprocess.run(["zsh", "-c", 'print -r -- "$RIPGREP_CONFIG_PATH"'], env=env,
                              capture_output=True, text=True)
        self.assertEqual(done.stdout.strip(), f"{home}/.config/ripgrep/config")


if __name__ == "__main__":
    unittest.main()
