"""The post-merge hook links a script that a merge added, and only in the stowed main checkout."""
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

import toolkit_paths

REPO_ROOT = toolkit_paths.REPO_ROOT
HOOK = pathlib.Path(os.environ.get("POST_MERGE_HOOK") or REPO_ROOT / ".githooks" / "post-merge")
MAIN_CHECKOUT_LIB = REPO_ROOT / "scripts" / ".local" / "lib" / "main-checkout.bash"
CHECK_SCRIPT = REPO_ROOT / "install" / "check-script-links"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "script-tests.yml"


def run(args, cwd, env, check=True):
    return subprocess.run(args, cwd=cwd, env=env, check=check, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


@unittest.skipUnless(shutil.which("stow"), "stow is not installed")
class PostMergeHookTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = pathlib.Path(tmp.name).resolve()
        self.repo = self.home / "dotfiles"
        self.env = {
            "HOME": str(self.home),
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
            "PATH": os.environ["PATH"],
        }
        self.repo.mkdir()
        self.git(self.repo, "init", "-q", "-b", "master")
        self.git(self.repo, "config", "core.hooksPath", ".githooks")
        self.add_file(self.repo / "install" / "check-script-links", CHECK_SCRIPT.read_text(), 0o755)
        self.add_file(self.repo / ".githooks" / "post-merge", HOOK.read_text(), 0o755)
        self.add_file(self.repo / "scripts" / ".local" / "bin" / "one", "#!/bin/sh\n", 0o755)
        lib_file = self.repo / "scripts" / ".local" / "lib" / "main-checkout.bash"
        self.add_file(lib_file, MAIN_CHECKOUT_LIB.read_text(), 0o644)
        self.git(self.repo, "add", ".")
        self.git(self.repo, "commit", "-q", "-m", "base")

        self.bin_dir = self.home / ".local" / "bin"
        self.bin_dir.mkdir(parents=True)
        (self.bin_dir / "foreign").write_text("not ours\n")
        run(["stow", "-R", "-t", str(self.home), "scripts"], self.repo, self.env)
        self.assertFalse(self.bin_dir.is_symlink())
        self.assertTrue((self.bin_dir / "one").is_symlink())

        self.git(self.repo, "checkout", "-q", "-b", "feature")
        self.add_file(self.repo / "scripts" / ".local" / "bin" / "two", "#!/bin/sh\n", 0o755)
        self.git(self.repo, "add", ".")
        self.git(self.repo, "commit", "-q", "-m", "add two")
        self.git(self.repo, "checkout", "-q", "master")

    def git(self, cwd, *args):
        return run(["git", *args], cwd, self.env)

    def add_file(self, path, text, mode):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        path.chmod(mode)

    def stow_stub(self):
        """A STOW program that only logs its calls; returns (stub path, log path)."""
        log = self.home / "stow.log"
        log.write_text("")
        stub = self.home / "stow-stub"
        self.add_file(stub, f'#!/bin/sh\necho "$@" >> "{log}"\n', 0o755)
        return stub, log

    def merge(self, cwd, *args, stow=None):
        env = dict(self.env)
        if stow is not None:
            env["STOW"] = str(stow)
        return run(["git", "merge", "-q", *args, "feature"], cwd, env, check=False)

    def test_a_merge_that_adds_a_script_links_it(self):
        result = self.merge(self.repo, "--no-ff", "-m", "merge")
        self.assertEqual(0, result.returncode, result.stdout)
        linked = self.bin_dir / "two"
        self.assertTrue(linked.samefile(self.repo / "scripts" / ".local" / "bin" / "two"))
        self.assertIn("Every script in scripts/.local/bin is linked", result.stdout)

    def test_a_fast_forward_merge_that_adds_a_script_links_it(self):
        result = self.merge(self.repo, "--ff-only")
        self.assertEqual(0, result.returncode, result.stdout)
        linked = self.bin_dir / "two"
        self.assertTrue(linked.samefile(self.repo / "scripts" / ".local" / "bin" / "two"))

    def test_a_merge_in_a_linked_worktree_restows_nothing(self):
        lane = self.home / "lane"
        self.git(self.repo, "worktree", "add", "-q", "-b", "lane-branch", str(lane))
        (self.bin_dir / "one").unlink()
        (self.home / ".local" / "lib").unlink()  # stow folded it into one link to the main checkout
        run(["stow", "-R", "-t", str(self.home), "scripts"], lane, self.env)
        stub, log = self.stow_stub()
        result = self.merge(lane, "--no-ff", "-m", "merge", stow=stub)
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertFalse((self.bin_dir / "two").exists())
        self.assertEqual("", log.read_text())

    def test_a_checkout_that_bin_does_not_link_to_restows_nothing(self):
        other = self.home / "other"
        self.git(self.home, "clone", "-q", str(self.repo), str(other))
        self.git(other, "config", "core.hooksPath", ".githooks")
        self.git(other, "fetch", "-q", "origin", "feature")
        stub, log = self.stow_stub()
        env = dict(self.env, STOW=str(stub))
        result = run(["git", "merge", "-q", "--no-ff", "-m", "merge", "FETCH_HEAD"], other, env, check=False)
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertFalse((self.bin_dir / "two").exists())
        self.assertEqual("", log.read_text())

    def test_a_stow_conflict_is_reported_and_the_hook_exits_0(self):
        (self.bin_dir / "two").write_text("a real file in the way\n")
        result = self.merge(self.repo, "--no-ff", "-m", "merge")
        self.assertEqual(0, result.returncode, result.stdout)
        lines = result.stdout.splitlines()
        self.assertIn("post-merge: stow -R scripts failed:", lines)
        stow_text = "\n".join(lines[lines.index("post-merge: stow -R scripts failed:") + 1:])
        self.assertIn("two", stow_text)
        self.assertFalse((self.bin_dir / "two").is_symlink())

    def test_no_gap_runs_no_stow(self):
        self.git(self.repo, "checkout", "-q", "-b", "docs")
        self.add_file(self.repo / "notes.txt", "notes\n", 0o644)
        self.git(self.repo, "add", ".")
        self.git(self.repo, "commit", "-q", "-m", "notes")
        self.git(self.repo, "checkout", "-q", "master")
        stub, log = self.stow_stub()
        env = dict(self.env, STOW=str(stub))
        result = run(["git", "merge", "-q", "--no-ff", "-m", "merge", "docs"], self.repo, env, check=False)
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertEqual("", log.read_text())

    def test_missing_stow_is_reported_and_the_hook_exits_0(self):
        result = self.merge(self.repo, "--no-ff", "-m", "merge", stow=self.home / "no-such-stow")
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertIn("stow is not installed", result.stdout)
        self.assertFalse((self.bin_dir / "two").exists())


class CiWorkflowTest(unittest.TestCase):
    def test_ci_workflow_installs_stow(self):
        lines = WORKFLOW.read_text().splitlines()
        install_lines = [line for line in lines if "apt-get install" in line]
        self.assertTrue(install_lines, "the workflow has no apt install line")
        for line in install_lines:
            self.assertIn("stow", line.split())


if __name__ == "__main__":
    unittest.main()
