"""The zshrc keeps the real `ls` inside Claude Code's Bash tool and aliases it everywhere else."""
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

import toolkit_paths

ZSHRC = pathlib.Path(os.environ.get("ZSHRC_FILE") or toolkit_paths.REPO_ROOT / "zsh" / ".zshrc")
SYSTEM_PATH = "/usr/local/bin:/usr/bin:/bin"


@unittest.skipUnless(shutil.which("zsh"), "zsh is not installed")
class ZshrcLsAliasTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        root = pathlib.Path(scratch.name)
        self.home = root / "home"
        zdotdir = root / "zdotdir"
        stub_dir = root / "stub"
        for folder in (self.home / "run", zdotdir, stub_dir):
            folder.mkdir(parents=True)
        (zdotdir / ".zshrc").symlink_to(ZSHRC)
        keychain = stub_dir / "keychain"
        keychain.write_text("#!/bin/sh\nexit 0\n")
        keychain.chmod(0o755)
        self.env = {
            "HOME": str(self.home),
            "ZDOTDIR": str(zdotdir),
            "PATH": f"{stub_dir}:{SYSTEM_PATH}",
            "NO_MUX": "1",
            "TERM": "dumb",
            "XDG_RUNTIME_DIR": str(self.home / "run"),
        }

    def whence_word(self, name, **extra):
        """Run an interactive zsh that loads the zshrc and return the last line `whence -w <name>` prints."""
        result = subprocess.run(
            ["zsh", "-i", "-c", f"whence -w {name}"],
            env={**self.env, **extra},
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=60,
        )
        lines = result.stdout.strip().splitlines()
        self.assertTrue(lines, f"zsh printed nothing; stderr: {result.stderr}")
        return lines[-1]

    def test_claude_code_shell_resolves_guarded_names_to_the_command(self):
        for name in ("ls", "cat"):
            with self.subTest(name=name):
                self.assertEqual(self.whence_word(name, CLAUDECODE="1"), f"{name}: command")

    def test_interactive_shell_without_claudecode_aliases_guarded_names(self):
        for name in ("ls", "cat"):
            with self.subTest(name=name):
                self.assertEqual(self.whence_word(name), f"{name}: alias")


if __name__ == "__main__":
    unittest.main()
