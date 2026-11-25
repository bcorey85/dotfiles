"""Runs herdr-dev against a stub herdr-api and checks the command typed into the claude pane.

A leading --resume resumes the session itself; the positional form still forks it. --headless leaves out the hunk
pane; without it the layout splits the claude pane and starts hunk-review-pane.
"""
import os
import pathlib
import re
import subprocess
import tempfile
import unittest

from stubs import run_through_stow_symlink, write_stub

BIN_DIR = pathlib.Path(__file__).resolve().parents[2] / "scripts" / ".local" / "bin"
HERDR_DEV = pathlib.Path(os.environ.get("HERDR_DEV", BIN_DIR / "herdr-dev"))
# A lane starts with the cron scheduler off so it never fires the parent session's jobs.
NO_CRON = "CLAUDE_CODE_DISABLE_CRON=1"

# herdr-dev runs under set -e, so every verb it calls answers {} with exit 0 unless it reads the reply.
HERDR_API_BODY = """printf '%s\\n' "$*" >> "$HERDR_API_LOG"
case "$1 $2" in
    "pane send-text") printf '%s\\n' "$*" >> "$HERDR_API_CALLS" ;;
esac
case "$1 $2" in
    "workspace get") echo '{"result":{"workspace":{"active_tab_id":"t1"}}}' ;;
    "pane list") echo '{"result":{"panes":[{"tab_id":"t1","pane_id":"p1"}]}}' ;;
    "pane split") echo '{"result":{"pane":{"pane_id":"p2"}}}' ;;
    "pane wait-output") echo '{"result":{}}' ;;
    *) echo '{}' ;;
esac
exit 0"""


class HerdrDevTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = pathlib.Path(os.path.realpath(scratch.name))
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        write_stub(self.bin_dir / "herdr-api", HERDR_API_BODY)
        self.api_calls = self.root / "api-calls"
        self.worktree = self.root / "my-lane"
        self.worktree.mkdir()

    def run_dev(self, *args, extra_env=None):
        env = {key: value for key, value in os.environ.items() if key != "TUIOS_SOCKET"}
        env.update(extra_env or {})
        if "TUIOS_SOCKET" in env:
            write_stub(self.bin_dir / "tuios", """case "$1" in
    ls) echo '[]' ;;
    split-window) echo '{"window_id":"win2"}' ;;
esac""")
        env["HOME"] = str(self.root)
        env["PATH"] = f"{self.bin_dir}:{env['PATH']}"
        env["HERDR_API_CALLS"] = str(self.api_calls)
        env["HERDR_API_LOG"] = str(self.root / "api-log")
        return subprocess.run(["bash", str(HERDR_DEV), *args], env=env, capture_output=True, text=True,
                              timeout=60)

    def typed_into_claude_pane(self):
        """The commands sent to pane p1, the claude pane."""
        lines = self.api_calls.read_text().splitlines()
        prefix = "pane send-text p1 "
        return [line[len(prefix):] for line in lines if line.startswith(prefix)]

    def test_resume_types_resume_without_fork(self):
        result = self.run_dev("--resume", str(self.worktree), "w1", "s1")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.typed_into_claude_pane(), [f"{NO_CRON} claude --resume s1 --name my-lane"])
        self.assertEqual(result.stdout.splitlines(), ["p1", f"{NO_CRON} claude --resume s1 --name my-lane"])

    def test_resume_with_a_brief_types_it_after_the_double_dash(self):
        result = self.run_dev("--resume", str(self.worktree), "w1", "s1", "go on")

        self.assertEqual(result.returncode, 0, result.stderr)
        typed = self.typed_into_claude_pane()[0]
        self.assertTrue(typed.startswith(f"{NO_CRON} claude --resume s1 --name my-lane -- "), typed)
        self.assertNotIn("--fork-session", typed)
        prompt_file = re.search(r"cat '([^']+)'", typed)
        if prompt_file is None:
            self.fail(f"no prompt file in: {typed}")
        prompt_path = pathlib.Path(prompt_file.group(1))
        self.addCleanup(prompt_path.unlink, missing_ok=True)
        self.assertEqual(prompt_path.read_text(), "go on")

    def test_positional_form_still_forks(self):
        result = self.run_dev(str(self.worktree), "w1", "s1")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.typed_into_claude_pane(), [f"{NO_CRON} claude --resume s1 --fork-session --name my-lane"])

    def test_a_start_with_no_session_types_plain_claude(self):
        result = self.run_dev(str(self.worktree), "w1")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.typed_into_claude_pane(), ["claude"])

    def test_the_script_finds_its_library_when_run_through_a_stow_symlink(self):
        finished = run_through_stow_symlink(HERDR_DEV, self.root / "symlink-run", "/nonexistent")

        self.assertEqual(finished.returncode, 1)
        self.assertIn("herdr-dev: no such directory: /nonexistent", finished.stderr)
        self.assertNotIn("toolkit-tools.bash", finished.stderr)

    def layout_calls(self):
        """Every herdr-api call the run made, minus the commands typed into the claude pane."""
        lines = (self.root / "api-log").read_text().splitlines()
        return [line for line in lines if not line.startswith("pane send-text p1 ")]

    def test_default_splits_the_claude_pane_and_starts_hunk(self):
        result = self.run_dev(str(self.worktree), "w1", "s1")

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.layout_calls()
        self.assertIn(f"pane split p1 --direction right --ratio 0.4 --cwd {self.worktree} --no-focus", calls)
        self.assertIn("pane send-text p2 hunk-review-pane", calls)
        self.assertIn("pane focus --direction right --pane p1", calls)

    def test_headless_leaves_out_the_hunk_pane(self):
        result = self.run_dev("--headless", str(self.worktree), "w1", "s1")

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.layout_calls()
        self.assertFalse([call for call in calls if call.startswith("pane split p1 ")], calls)
        self.assertFalse([call for call in calls if "hunk-review-pane" in call], calls)
        self.assertNotIn("pane focus --direction right --pane p1", calls)
        self.assertIn("tab focus t1", calls)
        self.assertEqual(result.stdout.splitlines(), ["p1", "claude --resume s1 --fork-session --name my-lane"])

    def test_headless_under_tuios_does_not_resize_a_missing_editor_pane(self):
        result = self.run_dev("--headless", str(self.worktree), "w1", "s1", extra_env={"TUIOS_SOCKET": "/tmp/x"})

        self.assertEqual(result.returncode, 0, result.stderr)
        resizes = [call for call in self.layout_calls() if call.startswith("pane resize") and "--amount 0.1 " in call]
        self.assertFalse(resizes, resizes)

    def test_default_under_tuios_narrows_the_claude_pane_to_forty_percent(self):
        result = self.run_dev(str(self.worktree), "w1", "s1", extra_env={"TUIOS_SOCKET": "/tmp/x"})

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("pane resize --direction left --amount 0.1 --pane p2", self.layout_calls())

    def test_headless_keeps_the_console_tab(self):
        result = self.run_dev("--headless", str(self.worktree), "w1", "s1")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"tab create --workspace w1 --label console --cwd {self.worktree} --no-focus",
                      self.layout_calls())

    def test_headless_and_resume_combine_in_either_order(self):
        for flags in (("--headless", "--resume"), ("--resume", "--headless")):
            with self.subTest(flags=flags):
                self.api_calls.unlink(missing_ok=True)
                (self.root / "api-log").unlink(missing_ok=True)

                result = self.run_dev(*flags, str(self.worktree), "w1", "s1")

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.typed_into_claude_pane(), ["claude --resume s1 --name my-lane"])
                self.assertFalse([call for call in self.layout_calls() if "hunk-review-pane" in call])


if __name__ == "__main__":
    unittest.main()
