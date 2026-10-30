"""Runs herdr-worktree and herdr-dev against stub herdr commands.

Checks the checkout herdr-worktree asks herdr to branch from, the brief it hands herdr-dev, its check that the fork
started, and how herdr-dev types the claude command.
"""
import os
import pathlib
import re
import shlex
import shutil
import subprocess
import tempfile
import unittest

from stubs import write_stub

BIN_DIR = pathlib.Path(__file__).resolve().parents[2] / "scripts" / ".local" / "bin"
HERDR_WORKTREE = BIN_DIR / "herdr-worktree"
HERDR_DEV = BIN_DIR / "herdr-dev"
CREATED_WORKSPACE = '{"result":{"workspace":{"workspace_id":"w1"}}}'
CLAUDE_PANE = '{"result":{"pane":{"agent":"claude","agent_session":{"value":"s1"}}}}'
SHELL_PANE = '{"result":{"pane":{"agent":null}}}'
FORK_COMMAND = "claude --resume s1 --fork-session -- \"$(cat '/tmp/brief')\" && rm -f '/tmp/brief'"


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
        write_stub(self.bin_dir / "herdr", f"""printf "%s\\n" "$@" > {self.herdr_args}
while [ $# -gt 0 ]; do
    case "$1" in
        --branch) branch="$2"; shift ;;
        --path) path="$2"; shift ;;
        --base) base="$2"; shift ;;
    esac
    shift
done
git -C {self.main_checkout} worktree add -q -b "$branch" "$path" "$base"
echo '{CREATED_WORKSPACE}'""")
        write_stub(self.bin_dir / "herdr-api", "exit 0")
        write_stub(self.bin_dir / "herdr-dev", "exit 0")

    def run_herdr_worktree(self, cwd, *args, fork_start_timeout="30"):
        env = {key: value for key, value in os.environ.items() if key != "TUIOS_SOCKET"}
        env["HOME"] = str(self.root)
        env["HERDR_WORKTREE_FORK_TIMEOUT"] = fork_start_timeout
        env["PATH"] = f"{self.bin_dir}:{env['PATH']}"
        return subprocess.run([str(self.bin_dir / "herdr-worktree"), *args], cwd=cwd, env=env,
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

    def stub_installers(self, npm_status=0):
        """npm and pnpm log their folder and arguments to installs."""
        installs = self.root / "installs"
        write_stub(self.bin_dir / "npm", f'echo "$PWD npm $*" >> {installs}\nexit {npm_status}')
        write_stub(self.bin_dir / "pnpm", f'echo "$PWD pnpm $*" >> {installs}')
        return installs

    def commit_lockfiles(self, *lockfiles):
        for lockfile in lockfiles:
            lockfile_path = self.main_checkout / lockfile
            lockfile_path.parent.mkdir(parents=True, exist_ok=True)
            lockfile_path.write_text("{}\n")
        git(self.main_checkout, "add", *lockfiles)
        git(self.main_checkout, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "lockfiles")

    def test_a_new_worktree_gets_node_dependencies_for_each_lockfile_at_the_root_or_one_folder_down(self):
        installs = self.stub_installers()
        self.commit_lockfiles("package-lock.json", "frontend/pnpm-lock.yaml", "fixtures/app/package-lock.json")

        finished = self.run_herdr_worktree(self.main_checkout, "fix/new-thing")

        self.assertEqual(finished.returncode, 0, finished.stderr)
        worktree = self.root / "repo-new-thing"
        self.assertEqual(sorted(installs.read_text().splitlines()), [
            f"{worktree} npm ci --no-audit --no-fund",
            f"{worktree}/frontend pnpm install --frozen-lockfile",
        ])

    def test_an_installer_that_reads_stdin_does_not_swallow_the_remaining_lockfiles(self):
        installs = self.root / "installs"
        write_stub(self.bin_dir / "npm", f'cat >/dev/null\necho "$PWD npm $*" >> {installs}')
        write_stub(self.bin_dir / "pnpm", f'cat >/dev/null\necho "$PWD pnpm $*" >> {installs}')
        self.commit_lockfiles("package-lock.json", "frontend/pnpm-lock.yaml")

        finished = self.run_herdr_worktree(self.main_checkout, "fix/new-thing")

        self.assertEqual(finished.returncode, 0, finished.stderr)
        worktree = self.root / "repo-new-thing"
        self.assertEqual(sorted(installs.read_text().splitlines()), [
            f"{worktree} npm ci --no-audit --no-fund",
            f"{worktree}/frontend pnpm install --frozen-lockfile",
        ])

    def test_a_failed_install_warns_with_the_command_and_the_run_goes_on(self):
        self.stub_installers(npm_status=1)
        self.commit_lockfiles("package-lock.json")

        finished = self.run_herdr_worktree(self.main_checkout, "fix/new-thing")

        self.assertEqual(finished.returncode, 0, finished.stderr)
        worktree = self.root / "repo-new-thing"
        install_log = self.main_checkout / ".git" / "worktrees" / "repo-new-thing" / "herdr-worktree-install.log"
        self.assertIn(f"dependency install failed (output in {install_log}); "
                      f"run in {worktree}: npm ci --no-audit --no-fund", finished.stderr)

    def test_install_output_goes_to_the_log_and_a_clean_install_prints_no_log_path(self):
        write_stub(self.bin_dir / "npm", 'echo "npm says added 3 packages"\necho "npm warns deprecated" >&2')
        self.commit_lockfiles("package-lock.json")

        finished = self.run_herdr_worktree(self.main_checkout, "fix/new-thing")

        self.assertEqual(finished.returncode, 0, finished.stderr)
        install_log = self.main_checkout / ".git" / "worktrees" / "repo-new-thing" / "herdr-worktree-install.log"
        self.assertEqual(install_log.read_text(), "npm says added 3 packages\nnpm warns deprecated\n")
        self.assertNotIn("npm", finished.stdout + finished.stderr)
        self.assertNotIn("herdr-worktree-install.log", finished.stderr)

    def test_each_install_prints_one_progress_line(self):
        self.stub_installers()
        self.commit_lockfiles("package-lock.json", "frontend/pnpm-lock.yaml")

        finished = self.run_herdr_worktree(self.main_checkout, "fix/new-thing")

        self.assertEqual(finished.returncode, 0, finished.stderr)
        worktree = self.root / "repo-new-thing"
        progress_lines = [line for line in finished.stderr.splitlines() if "installing dependencies" in line]
        self.assertEqual(sorted(progress_lines), [
            f"herdr-worktree: installing dependencies in {worktree}",
            f"herdr-worktree: installing dependencies in {worktree}/frontend",
        ])

    def stub_fork(self, fork_pane):
        """The current pane runs claude; the new workspace's claude pane w1:p1 answers `pane get` with fork_pane."""
        write_stub(self.bin_dir / "herdr-api", f"""case "$1 $2" in
    "pane current") echo '{CLAUDE_PANE}' ;;
    "pane get") echo '{fork_pane}' ;;
esac""")
        herdr_dev_args = self.root / "herdr-dev-args"
        write_stub(self.bin_dir / "herdr-dev", f'printf "%s\\0" "$@" > {herdr_dev_args}\n'
                                               f'echo w1:p1\nprintf "%s\\n" {shlex.quote(FORK_COMMAND)}')
        return herdr_dev_args

    def test_a_fork_from_a_linked_worktree_starts_the_forked_session_on_the_prompt_file(self):
        herdr_dev_args = self.stub_fork(CLAUDE_PANE)
        brief = "Fix the \"limit\" bug.\nThe fork owns it now.\n"
        brief_file = self.root / "brief.md"
        brief_file.write_text(brief)

        finished = self.run_herdr_worktree(self.linked_worktree, "--fork", "--prompt-file", str(brief_file),
                                           "fix/new-thing")

        self.assertEqual(finished.returncode, 0, finished.stderr)
        herdr_dev_values = herdr_dev_args.read_text().split("\0")
        self.assertEqual(herdr_dev_values[2:4], ["s1", brief.rstrip("\n")])

    def test_a_fork_whose_pane_never_shows_claude_exits_non_zero_naming_the_pane_and_its_command(self):
        self.stub_fork(SHELL_PANE)

        finished = self.run_herdr_worktree(self.linked_worktree, "--fork", "--prompt", "Fix it.", "fix/new-thing",
                                           fork_start_timeout="1")

        self.assertNotEqual(finished.returncode, 0)
        self.assertIn("w1:p1", finished.stderr)
        self.assertIn(FORK_COMMAND, finished.stderr)


class HerdrDevTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = pathlib.Path(os.path.realpath(scratch.name))
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        self.herdr_calls = self.root / "herdr-calls"
        write_stub(self.bin_dir / "herdr-api", f"""printf '%s\\n' "$*" >> {self.herdr_calls}
case "$1 $2" in
    "workspace get") echo '{{"result":{{"workspace":{{"active_tab_id":"w1:t1"}}}}}}' ;;
    "pane list") echo '{{"result":{{"panes":[{{"tab_id":"w1:t1","pane_id":"w1:p1"}}]}}}}' ;;
    "pane split") echo '{{"result":{{"pane":{{"pane_id":"w1:p2"}}}}}}' ;;
    "tab create") echo '{{"result":{{"tab":{{"tab_id":"w1:t2"}},"root_pane":{{"pane_id":"w1:p3"}}}}}}' ;;
esac""")

    def run_herdr_dev(self, *args, directory=None):
        env = {key: value for key, value in os.environ.items() if key != "TUIOS_SOCKET"}
        env["HOME"] = str(self.root)
        env["PATH"] = f"{self.bin_dir}:{env['PATH']}"
        return subprocess.run([str(HERDR_DEV), str(directory or self.root), "w1", *args], env=env,
                              capture_output=True, text=True)

    def test_the_claude_command_is_typed_after_the_shell_prompt_shows_and_the_input_line_is_cleared(self):
        finished = self.run_herdr_dev("s1", "Fix it.")

        self.assertEqual(finished.returncode, 0, finished.stderr)
        claude_pane_calls = [call for call in self.herdr_calls.read_text().splitlines() if " w1:p1" in call]
        typed = next(index for index, call in enumerate(claude_pane_calls) if call.startswith("pane send-text"))
        self.assertTrue(claude_pane_calls[typed - 2].startswith("pane wait-output"), claude_pane_calls)
        self.assertEqual(claude_pane_calls[typed - 1], "pane send-keys w1:p1 ctrl+u")

    def test_the_prompt_file_is_removed_only_after_claude_succeeds_and_both_go_to_stdout(self):
        finished = self.run_herdr_dev("s1", "Fix it.")

        self.assertEqual(finished.returncode, 0, finished.stderr)
        claude_pane, claude_command = finished.stdout.splitlines()
        self.assertEqual(claude_pane, "w1:p1")
        prompt_file = re.search(r"cat '([^']+)'", claude_command).group(1)
        self.addCleanup(os.remove, prompt_file)
        self.assertEqual(pathlib.Path(prompt_file).read_text(), "Fix it.")
        self.assertTrue(claude_command.endswith(f"&& rm -f '{prompt_file}'"), claude_command)

    def test_the_fork_is_named_for_its_worktree_so_peers_can_tell_it_from_its_parent(self):
        finished = self.run_herdr_dev("s1", "Fix it.")

        self.assertEqual(finished.returncode, 0, finished.stderr)
        claude_command = finished.stdout.splitlines()[1]
        prompt_file = re.search(r"cat '([^']+)'", claude_command).group(1)
        self.addCleanup(os.remove, prompt_file)
        self.assertTrue(claude_command.startswith(f"claude --resume s1 --fork-session --name {self.root.name} -- "),
                        claude_command)

    def test_a_worktree_folder_with_shell_special_characters_is_typed_as_one_name_argument(self):
        folder_name = "my repo $x's"
        worktree = self.root / folder_name
        worktree.mkdir()

        finished = self.run_herdr_dev("s1", "Fix it.", directory=worktree)

        self.assertEqual(finished.returncode, 0, finished.stderr)
        claude_command = finished.stdout.splitlines()[1]
        prompt_file = re.search(r"cat '([^']+)'", claude_command).group(1)
        self.addCleanup(os.remove, prompt_file)
        typed_words = shlex.split(claude_command)
        self.assertEqual(typed_words[typed_words.index("--name") + 1], folder_name)


if __name__ == "__main__":
    unittest.main()
