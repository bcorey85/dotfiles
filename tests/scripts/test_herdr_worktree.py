"""Runs herdr-worktree against stub herdr commands and checks which checkout it asks herdr to branch from."""
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

HERDR_WORKTREE = pathlib.Path(__file__).resolve().parents[2] / "scripts" / ".local" / "bin" / "herdr-worktree"
CREATED_WORKSPACE = '{"result":{"workspace":{"workspace_id":"w1"}}}'


def write_stub(path, body):
    path.write_text("#!/bin/bash\n" + body + "\n")
    path.chmod(0o755)


def git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


class HerdrWorktreeTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = pathlib.Path(os.path.realpath(scratch.name))

        self.main_checkout = self.root / "repo"
        self.main_checkout.mkdir()
        git(self.main_checkout, "init", "-q", "-b", "master")
        git(self.main_checkout, "-c", "user.name=t", "-c", "user.email=t@t",
            "commit", "-q", "--allow-empty", "-m", "base")
        self.linked_worktree = self.root / "repo-linked"
        git(self.main_checkout, "worktree", "add", "-q", "-b", "linked", str(self.linked_worktree))

        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        shutil.copy(HERDR_WORKTREE, self.bin_dir / "herdr-worktree")
        self.herdr_args = self.root / "herdr-args"
        write_stub(self.bin_dir / "herdr", f'printf "%s\\n" "$@" > {self.herdr_args}\necho \'{CREATED_WORKSPACE}\'')
        write_stub(self.bin_dir / "herdr-api", "exit 0")
        write_stub(self.bin_dir / "herdr-dev", "exit 0")

    def run_herdr_worktree(self, cwd, branch):
        env = {key: value for key, value in os.environ.items() if key != "TUIOS_SOCKET"}
        env["HOME"] = str(self.root)
        env["PATH"] = f"{self.bin_dir}:{env['PATH']}"
        return subprocess.run([str(self.bin_dir / "herdr-worktree"), branch], cwd=cwd, env=env,
                              capture_output=True, text=True)

    def test_a_run_from_a_linked_worktree_asks_herdr_to_branch_from_the_main_checkout(self):
        finished = self.run_herdr_worktree(self.linked_worktree, "fix/new-thing")

        self.assertEqual(finished.returncode, 0, finished.stderr)
        herdr_args = self.herdr_args.read_text().splitlines()
        cwd_value = herdr_args[herdr_args.index("--cwd") + 1]
        self.assertEqual(cwd_value, str(self.main_checkout))
        path_value = herdr_args[herdr_args.index("--path") + 1]
        self.assertEqual(path_value, str(self.root / "repo-new-thing"))

    def test_a_run_from_a_linked_worktree_resolves_head_there_not_in_the_main_checkout(self):
        git(self.linked_worktree, "-c", "user.name=t", "-c", "user.email=t@t",
            "commit", "-q", "--allow-empty", "-m", "linked work")
        linked_head = subprocess.run(["git", "-C", str(self.linked_worktree), "rev-parse", "HEAD"],
                                     check=True, capture_output=True, text=True).stdout.strip()

        finished = self.run_herdr_worktree(self.linked_worktree, "fix/new-thing")

        self.assertEqual(finished.returncode, 0, finished.stderr)
        herdr_args = self.herdr_args.read_text().splitlines()
        self.assertEqual(herdr_args[herdr_args.index("--base") + 1], linked_head)


if __name__ == "__main__":
    unittest.main()
