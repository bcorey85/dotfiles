"""Runs herdr-worktree-watch against stub herdr commands.

Checks what the watcher logs and shows when the forked workspace is still open and when it is gone.
"""
import os
import pathlib
import subprocess
import tempfile
import time
import unittest

from stubs import write_stub

BIN_DIR = pathlib.Path(__file__).resolve().parents[2] / "scripts" / ".local" / "bin"
HERDR_WORKTREE_WATCH = pathlib.Path(os.environ.get("HERDR_WORKTREE_WATCH", BIN_DIR / "herdr-worktree-watch"))
PANE_WITH_SESSION = '{"result":{"pane":{"agent":"claude","agent_session":{"value":"s1"}}}}'
PARENT_PANE = '{"result":{"pane":{"agent":"claude","agent_session":{"value":"parent1"}}}}'
PANE_WITHOUT_SESSION = '{"result":{"pane":null}}'
RESUME_PROMPT = "Go on with the work in this worktree; your brief is already in context."
WORKSPACE_ID_FIELD = "jq -r '.result.workspace.workspace_id // empty')"
RESUME_STEP = ("ws=$({reopen} | " + WORKSPACE_ID_FIELD
               + " && [ -n \"$ws\" ]{focus} && herdr-dev {worktree} \"$ws\" s1 '" + RESUME_PROMPT + "'")
OPEN_OUTPUT = '{"result":{"workspace":{"workspace_id":"w9"}}}'
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
        write_stub(self.bin_dir / "herdr", f"""printf "%s\\n" "$*" >> {self.herdr_calls}
[ "$1 $2" = "worktree open" ] && echo '{OPEN_OUTPUT}'
exit 0""")
        self.herdr_dev_calls = self.root / "herdr-dev-calls"
        write_stub(self.bin_dir / "herdr-dev", f'printf "%s\\n" "$*" >> {self.herdr_dev_calls}')

    def resume_step(self, reopen=None, focus=""):
        reopen = reopen or f"herdr worktree open --cwd {self.main_checkout} --path {self.worktree} --focus"
        return RESUME_STEP.format(reopen=reopen, focus=focus, worktree=self.worktree)

    def stub_herdr_api(self, workspace_open, pane):
        workspace_command = "exit 0" if workspace_open else WORKSPACE_NOT_FOUND_COMMAND
        pane_command = "exit 1" if pane is None else f"echo '{pane}'"
        write_stub(self.bin_dir / "herdr-api", f"""case "$1 $2" in
    "pane get") {pane_command} ;;
    "workspace get") {workspace_command} ;;
esac""")

    def run_watch(self, tuios=False, watch_seconds="0", parent_session=""):
        env = {key: value for key, value in os.environ.items()
               if key not in ("TUIOS_SOCKET", "HERDR_WORKTREE_WATCH_SECONDS")}
        env["HOME"] = str(self.root)
        if watch_seconds is not None:
            env["HERDR_WORKTREE_WATCH_SECONDS"] = watch_seconds
        env["PATH"] = f"{self.bin_dir}:{env['PATH']}"
        if tuios:
            env["TUIOS_SOCKET"] = str(self.root / "tuios.sock")
        return subprocess.run([str(HERDR_WORKTREE_WATCH), "w1", str(self.worktree), str(self.main_checkout), "w1:p1",
                               parent_session],
                              env=env, capture_output=True, text=True)

    def resume_step_line(self):
        return self.log.read_text().splitlines()[1]

    def herdr_calls_text(self):
        return self.herdr_calls.read_text() if self.herdr_calls.exists() else ""

    def test_a_workspace_that_is_still_open_is_logged_and_no_notification_is_shown(self):
        self.stub_herdr_api(workspace_open=True, pane=PANE_WITH_SESSION)

        finished = self.run_watch()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(self.log.read_text(), "workspace w1 still open\n")
        self.assertNotIn("notification", self.herdr_calls_text())

    def test_a_gone_workspace_logs_one_line_with_literal_values_that_captures_the_new_workspace_id(self):
        self.stub_herdr_api(workspace_open=False, pane=PANE_WITH_SESSION)

        finished = self.run_watch()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        log_lines = self.log.read_text().splitlines()
        self.assertIn(self.resume_step(), log_lines)
        self.assertEqual(len(log_lines), 2)
        notification = self.herdr_calls_text()
        self.assertIn("notification show herdr-worktree: workspace closed", notification)
        self.assertIn(str(self.log), notification)

    def test_the_logged_line_passes_the_workspace_id_that_the_reopen_prints_to_herdr_dev(self):
        self.stub_herdr_api(workspace_open=False, pane=PANE_WITH_SESSION)
        self.run_watch()
        logged_line = self.resume_step_line()
        env = {**os.environ, "PATH": f"{self.bin_dir}:{os.environ['PATH']}"}

        pasted = subprocess.run(["bash", "-c", logged_line], env=env,
                                capture_output=True, text=True)

        self.assertEqual(pasted.returncode, 0, pasted.stderr)
        self.assertEqual(self.herdr_dev_calls.read_text().strip(), f"{self.worktree} w9 s1 {RESUME_PROMPT}")

    def test_the_logged_line_does_not_run_herdr_dev_when_the_reopen_prints_no_workspace_id(self):
        self.stub_herdr_api(workspace_open=False, pane=PANE_WITH_SESSION)
        self.run_watch()
        logged_line = self.resume_step_line()
        write_stub(self.bin_dir / "herdr", "exit 1")
        env = {**os.environ, "PATH": f"{self.bin_dir}:{os.environ['PATH']}"}

        pasted = subprocess.run(["bash", "-c", logged_line], env=env,
                                capture_output=True, text=True)

        self.assertNotEqual(pasted.returncode, 0)
        self.assertFalse(self.herdr_dev_calls.exists())

    def test_the_logged_line_does_not_run_herdr_dev_when_the_reopen_prints_json_without_a_workspace_id(self):
        self.stub_herdr_api(workspace_open=False, pane=PANE_WITH_SESSION)
        self.run_watch()
        logged_line = self.resume_step_line()
        write_stub(self.bin_dir / "herdr", "echo '{\"result\":{}}'")
        env = {**os.environ, "PATH": f"{self.bin_dir}:{os.environ['PATH']}"}

        pasted = subprocess.run(["bash", "-c", logged_line], env=env,
                                capture_output=True, text=True)

        self.assertNotEqual(pasted.returncode, 0)
        self.assertFalse(self.herdr_dev_calls.exists())

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
        self.assertIn(self.resume_step(), self.log.read_text())

    def test_the_parent_session_id_reported_first_is_polled_past_and_the_fork_id_is_logged(self):
        pane_calls = self.root / "pane-calls"
        write_stub(self.bin_dir / "sleep", "exit 0")
        write_stub(self.bin_dir / "herdr-api", f"""case "$1 $2" in
    "pane get")
        echo x >> {pane_calls}
        if [ "$(wc -l < {pane_calls})" -ge 3 ]; then
            echo '{PANE_WITH_SESSION}'
        else
            echo '{PARENT_PANE}'
        fi ;;
    "workspace get") {WORKSPACE_NOT_FOUND_COMMAND} ;;
esac""")

        finished = self.run_watch(watch_seconds="5", parent_session="parent1")

        self.assertEqual(finished.returncode, 0, finished.stderr)
        log_text = self.log.read_text()
        self.assertIn(self.resume_step(), log_text)
        self.assertNotIn("parent1", log_text)

    def test_a_pane_that_only_ever_reports_the_parent_session_logs_the_claude_resume_step(self):
        write_stub(self.bin_dir / "sleep", "exit 0")
        self.stub_herdr_api(workspace_open=False, pane=PARENT_PANE)

        finished = self.run_watch(watch_seconds="2", parent_session="parent1")

        self.assertEqual(finished.returncode, 0, finished.stderr)
        log_text = self.log.read_text()
        self.assertIn(f"run claude --resume in {self.worktree}", log_text)
        self.assertNotIn("herdr-dev", log_text)

    def test_a_session_id_that_never_appears_is_polled_for_the_wait_by_wall_time_and_no_longer(self):
        self.stub_herdr_api(workspace_open=False, pane=PANE_WITHOUT_SESSION)
        started = time.monotonic()

        finished = self.run_watch(watch_seconds="2")

        elapsed = time.monotonic() - started
        self.assertEqual(finished.returncode, 0, finished.stderr)
        # SECONDS ticks on shell-start boundaries, so the loop can stop a second early.
        self.assertGreaterEqual(elapsed, 1)
        self.assertLess(elapsed, 3.5)
        self.assertIn("run claude --resume in", self.log.read_text())

    def test_the_wait_counts_time_spent_polling_not_only_the_sleeps(self):
        # Each poll takes a second; the sleeps are instant. A sleep-counting loop would poll 4 times.
        pane_calls = self.root / "pane-calls"
        write_stub(self.bin_dir / "sleep", "exit 0")
        write_stub(self.bin_dir / "herdr-api", f"""case "$1 $2" in
    "pane get") echo x >> {pane_calls}; /bin/sleep 1; echo '{PANE_WITHOUT_SESSION}' ;;
    "workspace get") exit 0 ;;
esac""")

        finished = self.run_watch(watch_seconds="3")

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertLessEqual(len(pane_calls.read_text().splitlines()), 3)

    def test_a_wait_that_is_not_a_whole_number_reports_the_bad_value_on_stderr_and_exits_non_zero(self):
        for bad_value in ("soon", "08"):
            with self.subTest(bad_value=bad_value):
                self.stub_herdr_api(workspace_open=True, pane=PANE_WITH_SESSION)

                finished = self.run_watch(watch_seconds=bad_value)

                self.assertEqual(finished.returncode, 1)
                self.assertIn(f"HERDR_WORKTREE_WATCH_SECONDS must be a whole number of seconds, got: {bad_value}",
                              finished.stderr)

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
        sleeps = sleep_args.read_text().splitlines()
        # The stub sleep is instant; the clock ticks in whole seconds, so a tick can land between the reads.
        self.assertIn(sleeps, (["1", "5"], ["1", "4"]))

    def test_recovery_steps_quote_a_path_with_a_space(self):
        spaced = self.root / "my repo"
        self.main_checkout.rename(spaced)
        git(spaced, "worktree", "repair", str(self.worktree))
        self.main_checkout = spaced
        self.log = spaced / ".git" / "worktrees" / "repo-fork" / "herdr-worktree-watch.log"
        self.stub_herdr_api(workspace_open=False, pane=PANE_WITH_SESSION)

        finished = self.run_watch()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertIn(f"ws=$(herdr worktree open --cwd {str(spaced).replace(' ', chr(92) + ' ')} --path",
                      self.log.read_text().splitlines()[1])

    def test_under_tuios_no_notification_is_shown_and_step_one_creates_the_workspace_through_herdr_api(self):
        self.stub_herdr_api(workspace_open=False, pane=PANE_WITH_SESSION)

        finished = self.run_watch(tuios=True)

        self.assertEqual(finished.returncode, 0, finished.stderr)
        log_text = self.log.read_text()
        reopen = f"herdr-api workspace create --cwd {self.worktree} --label repo-fork --focus"
        focus = ' && herdr-api workspace focus "$ws" >/dev/null'
        self.assertIn(self.resume_step(reopen, focus), log_text.splitlines())
        self.assertNotIn("herdr worktree open", log_text)
        self.assertNotIn("notification", self.herdr_calls_text())

    def test_a_workspace_check_that_fails_for_another_reason_is_not_reported_as_closed(self):
        write_stub(self.bin_dir / "herdr-api", f"""case "$1 $2" in
    "pane get") echo '{PANE_WITH_SESSION}' ;;
    "workspace get") echo '{{"error":{{"code":"server_unavailable"}}}}' >&2; exit 1 ;;
esac""")

        finished = self.run_watch()

        self.assertEqual(finished.returncode, 1)
        self.assertIn("could not check workspace w1: ", finished.stderr)
        self.assertIn("server_unavailable", finished.stderr)
        self.assertNotIn("closed", finished.stderr)
        self.assertNotIn("notification", self.herdr_calls_text())


if __name__ == "__main__":
    unittest.main()
