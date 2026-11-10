"""Runs herdr-worktree-watch against stub herdr commands.

Checks what the watcher logs and shows when the forked workspace is still open and when it is gone.
"""
import os
import pathlib
import subprocess
import tempfile
import unittest

from stubs import write_stub

BIN_DIR = pathlib.Path(__file__).resolve().parents[2] / "scripts" / ".local" / "bin"
HERDR_WORKTREE_WATCH = pathlib.Path(os.environ.get("HERDR_WORKTREE_WATCH", BIN_DIR / "herdr-worktree-watch"))
PANE_WITH_SESSION = '{"result":{"pane":{"agent":"claude","agent_session":{"value":"s1"}}}}'
PANE_WITHOUT_SESSION = '{"result":{"pane":null}}'
WORKSPACE_NOT_FOUND_COMMAND = 'echo \'{"error":{"code":"workspace_not_found"}}\' >&2; exit 1'


def git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


class HerdrWorktreeWatchTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = pathlib.Path(os.path.realpath(scratch.name))

        self.main_checkout = self.root / "repo"
        self.main_checkout.mkdir()
        git(self.main_checkout, "init", "-q", "-b", "master")
        git(self.main_checkout, "-c", "user.name=t", "-c", "user.email=t@t",
            "commit", "-q", "--allow-empty", "-m", "base")
        self.worktree = self.root / "repo-fork"
        git(self.main_checkout, "worktree", "add", "-q", "-b", "fork", str(self.worktree))
        self.log = self.main_checkout / ".git" / "worktrees" / "repo-fork" / "herdr-worktree-watch.log"

        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        self.herdr_calls = self.root / "herdr-calls"
        write_stub(self.bin_dir / "herdr", f'printf "%s\\n" "$*" >> {self.herdr_calls}')

    def stub_herdr_api(self, workspace_open, pane):
        workspace_command = "exit 0" if workspace_open else WORKSPACE_NOT_FOUND_COMMAND
        pane_command = "exit 1" if pane is None else f"echo '{pane}'"
        write_stub(self.bin_dir / "herdr-api", f"""case "$1 $2" in
    "pane get") {pane_command} ;;
    "workspace get") {workspace_command} ;;
esac""")

    def run_watch(self, tuios=False, watch_seconds="0"):
        env = {key: value for key, value in os.environ.items()
               if key not in ("TUIOS_SOCKET", "HERDR_WORKTREE_WATCH_SECONDS")}
        env["HOME"] = str(self.root)
        if watch_seconds is not None:
            env["HERDR_WORKTREE_WATCH_SECONDS"] = watch_seconds
        env["PATH"] = f"{self.bin_dir}:{env['PATH']}"
        if tuios:
            env["TUIOS_SOCKET"] = str(self.root / "tuios.sock")
        return subprocess.run([str(HERDR_WORKTREE_WATCH), "w1", str(self.worktree), str(self.main_checkout), "w1:p1"],
                              env=env, capture_output=True, text=True)

    def herdr_calls_text(self):
        return self.herdr_calls.read_text() if self.herdr_calls.exists() else ""

    def test_a_workspace_that_is_still_open_is_logged_and_no_notification_is_shown(self):
        self.stub_herdr_api(workspace_open=True, pane=PANE_WITH_SESSION)

        finished = self.run_watch()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(self.log.read_text(), "workspace w1 still open\n")
        self.assertNotIn("notification", self.herdr_calls_text())

    def test_a_gone_workspace_logs_literal_worktree_checkout_session_and_placeholder_workspace_id_prompt(self):
        self.stub_herdr_api(workspace_open=False, pane=PANE_WITH_SESSION)

        finished = self.run_watch()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        log_lines = self.log.read_text().splitlines()
        self.assertIn(f"1. herdr worktree open --cwd {self.main_checkout} --path {self.worktree} --focus", log_lines)
        self.assertIn(f'2. herdr-dev {self.worktree} <new workspace id> s1 "<prompt>"', log_lines)
        notification = self.herdr_calls_text()
        self.assertIn("notification show herdr-worktree: workspace closed", notification)
        self.assertIn(str(self.log), notification)

    def test_a_gone_workspace_with_no_session_id_logs_the_claude_resume_step(self):
        self.stub_herdr_api(workspace_open=False, pane=PANE_WITHOUT_SESSION)

        finished = self.run_watch()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        log_text = self.log.read_text()
        self.assertIn(f"run claude --resume in {self.worktree}", log_text)
        self.assertNotIn("herdr-dev", log_text)

    def test_a_pane_that_is_gone_still_logs_the_claude_resume_step(self):
        self.stub_herdr_api(workspace_open=False, pane=None)

        finished = self.run_watch()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertIn(f"run claude --resume in {self.worktree}", self.log.read_text())

    def test_the_watcher_waits_120_seconds_when_no_wait_is_set(self):
        self.stub_herdr_api(workspace_open=True, pane=PANE_WITH_SESSION)
        sleep_args = self.root / "sleep-args"
        write_stub(self.bin_dir / "sleep", f'echo "$*" > {sleep_args}')

        finished = self.run_watch(watch_seconds=None)

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(sleep_args.read_text().strip(), "120")

    def test_a_session_id_reported_after_the_agent_appears_is_polled_for(self):
        pane_calls = self.root / "pane-calls"
        write_stub(self.bin_dir / "sleep", "exit 0")
        write_stub(self.bin_dir / "herdr-api", f"""case "$1 $2" in
    "pane get")
        echo x >> {pane_calls}
        if [ "$(wc -l < {pane_calls})" -ge 2 ]; then
            echo '{PANE_WITH_SESSION}'
        else
            echo '{PANE_WITHOUT_SESSION}'
        fi ;;
    "workspace get") {WORKSPACE_NOT_FOUND_COMMAND} ;;
esac""")

        finished = self.run_watch(watch_seconds="5")

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertIn(f'2. herdr-dev {self.worktree} <new workspace id> s1 "<prompt>"', self.log.read_text())

    def test_a_session_id_that_never_appears_is_polled_only_for_the_wait_and_slept_for_nothing_more(self):
        sleep_args = self.root / "sleep-args"
        write_stub(self.bin_dir / "sleep", f'echo "$*" >> {sleep_args}')
        self.stub_herdr_api(workspace_open=False, pane=PANE_WITHOUT_SESSION)

        finished = self.run_watch(watch_seconds="3")

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(sleep_args.read_text().splitlines(), ["1", "1", "1"])
        self.assertIn("run claude --resume in", self.log.read_text())

    def test_a_session_id_found_after_one_poll_leaves_the_rest_of_the_wait_to_sleep(self):
        sleep_args = self.root / "sleep-args"
        pane_calls = self.root / "pane-calls"
        write_stub(self.bin_dir / "sleep", f'echo "$*" >> {sleep_args}')
        write_stub(self.bin_dir / "herdr-api", f"""case "$1 $2" in
    "pane get")
        echo x >> {pane_calls}
        if [ "$(wc -l < {pane_calls})" -ge 2 ]; then
            echo '{PANE_WITH_SESSION}'
        else
            echo '{PANE_WITHOUT_SESSION}'
        fi ;;
    "workspace get") exit 0 ;;
esac""")

        finished = self.run_watch(watch_seconds="5")

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(sleep_args.read_text().splitlines(), ["1", "4"])

    def test_recovery_steps_quote_a_path_with_a_space(self):
        spaced = self.root / "my repo"
        self.main_checkout.rename(spaced)
        git(spaced, "worktree", "repair", str(self.worktree))
        self.main_checkout = spaced
        self.log = spaced / ".git" / "worktrees" / "repo-fork" / "herdr-worktree-watch.log"
        self.stub_herdr_api(workspace_open=False, pane=PANE_WITH_SESSION)

        finished = self.run_watch()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertIn(f"1. herdr worktree open --cwd {str(spaced).replace(' ', chr(92) + ' ')} --path",
                      self.log.read_text().splitlines()[1])

    def test_under_tuios_no_notification_is_shown_and_step_one_creates_the_workspace_through_herdr_api(self):
        self.stub_herdr_api(workspace_open=False, pane=PANE_WITH_SESSION)

        finished = self.run_watch(tuios=True)

        self.assertEqual(finished.returncode, 0, finished.stderr)
        log_text = self.log.read_text()
        self.assertIn(f"1. herdr-api workspace create --cwd {self.worktree} --label repo-fork --focus",
                      log_text.splitlines())
        self.assertNotIn("herdr worktree open", log_text)
        self.assertNotIn("notification", self.herdr_calls_text())

    def test_a_workspace_check_that_fails_for_another_reason_is_not_reported_as_closed(self):
        write_stub(self.bin_dir / "herdr-api", f"""case "$1 $2" in
    "pane get") echo '{PANE_WITH_SESSION}' ;;
    "workspace get") echo '{{"error":{{"code":"server_unavailable"}}}}' >&2; exit 1 ;;
esac""")

        finished = self.run_watch()

        self.assertEqual(finished.returncode, 1)
        log_text = self.log.read_text()
        self.assertIn("could not check workspace w1: ", log_text)
        self.assertIn("server_unavailable", log_text)
        self.assertNotIn("closed", log_text)
        self.assertNotIn("notification", self.herdr_calls_text())


if __name__ == "__main__":
    unittest.main()
