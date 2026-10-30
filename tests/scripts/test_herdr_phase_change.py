"""Runs herdr-phase-change against a stub herdr-api that plays one Claude pane.

Checks that the next phase's prompt goes out only after /clear has taken effect.
"""
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

from stubs import write_stub

HERDR_PHASE_CHANGE = pathlib.Path(__file__).resolve().parents[2] / "scripts" / ".local" / "bin" / "herdr-phase-change"

# The pane's state lives in files: its status, its session id, and every prompt
# submitted, one per line. A /clear swaps the session id only after
# `clear_delay` further `agent get` reads, the way the SessionStart hook reports
# the new id a moment after the prompt is accepted.
STUB_HERDR_API = r"""
state="$STATE_DIR"
case "$1 $2" in
    "agent get")
        if [ -f "$state/clear-pending" ]; then
            left=$(cat "$state/clear-pending")
            if [ "$left" -le 0 ]; then
                echo "s2" > "$state/session"
                rm "$state/clear-pending"
            else
                echo $((left - 1)) > "$state/clear-pending"
            fi
        fi
        printf '{"result":{"agent":{"agent_status":"%s","agent_session":{"value":"%s"}}}}\n' \
            "$(cat "$state/status")" "$(cat "$state/session")"
        ;;
    "agent prompt")
        printf '%s\n' "$4" >> "$state/prompts"
        if [ "$4" = "/clear" ] && [ -f "$state/clear-delay" ]; then
            cp "$state/clear-delay" "$state/clear-pending"
        fi
        echo '{"result":{}}'
        ;;
    "agent wait")
        echo "$@" >> "$state/wait-args"
        [ -f "$state/wait-fails" ] && exit 1
        echo '{"result":{}}'
        ;;
esac
"""


class HerdrPhaseChangeTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = pathlib.Path(scratch.name)

        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        shutil.copy(HERDR_PHASE_CHANGE, self.bin_dir / "herdr-phase-change")
        write_stub(self.bin_dir / "herdr-api", STUB_HERDR_API)

        self.state_dir = self.root / "state"
        self.state_dir.mkdir()
        (self.state_dir / "status").write_text("done\n")
        (self.state_dir / "session").write_text("s1\n")
        self.prompts = self.state_dir / "prompts"

    def run_phase_change(self, *args):
        env = dict(os.environ)
        env["HOME"] = str(self.root)
        env["PATH"] = f"{self.bin_dir}:{env['PATH']}"
        env["STATE_DIR"] = str(self.state_dir)
        return subprocess.run([str(self.bin_dir / "herdr-phase-change"), *args], env=env,
                              capture_output=True, text=True, timeout=30)

    def submitted_prompts(self):
        if not self.prompts.exists():
            return []
        return self.prompts.read_text().splitlines()

    def test_a_done_pane_gets_clear_and_the_prompt_as_two_submissions_after_the_session_changes(self):
        (self.state_dir / "clear-delay").write_text("2\n")

        finished = self.run_phase_change("--watched", "worker", "/code docs/plans/x/plan.md")

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(self.submitted_prompts(), ["/clear", "/code docs/plans/x/plan.md"])
        self.assertEqual((self.state_dir / "session").read_text().strip(), "s2")
        self.assertIn("--until idle --until done", (self.state_dir / "wait-args").read_text())

    def test_a_code_prompt_goes_out_headless_unless_it_already_is_or_the_pane_is_watched(self):
        cases = (
            ("plain", ("/code docs/plans/x/plan.md",), "/code --headless docs/plans/x/plan.md"),
            ("already headless", ("/code --headless docs/plans/x/plan.md",), "/code --headless docs/plans/x/plan.md"),
            ("modifier", ("/code +fast plan.md",), "/code --headless +fast plan.md"),
            ("bare code", ("/code",), "/code"),
            ("resume verb", ("/code resume",), "/code resume"),
            ("tick verb", ("/code tick 2",), "/code tick 2"),
            ("headless in task text", ("/code fix the --headless flag",), "/code --headless fix the --headless flag"),
            ("headless after task", ("/code --task drop --headless from restart",),
             "/code --headless --task drop --headless from restart"),
            ("watched", ("--watched", "/code docs/plans/x/plan.md"), "/code docs/plans/x/plan.md"),
            ("other phase", ("/eng-spec docs/tickets/x.md",), "/eng-spec docs/tickets/x.md"),
            ("verify", ("/verify-branch",), "/verify-branch"),
        )
        for name, args, sent in cases:
            with self.subTest(case=name):
                self.prompts.unlink(missing_ok=True)
                (self.state_dir / "session").write_text("s1\n")
                (self.state_dir / "clear-delay").write_text("0\n")

                finished = self.run_phase_change(*args[:-1], "worker", args[-1])

                self.assertEqual(finished.returncode, 0, finished.stderr)
                self.assertEqual(self.submitted_prompts(), ["/clear", sent])

    def test_a_pane_that_does_not_settle_after_clear_gets_no_prompt(self):
        (self.state_dir / "clear-delay").write_text("0\n")
        (self.state_dir / "wait-fails").write_text("")

        finished = self.run_phase_change("worker", "/code docs/plans/x/plan.md")

        self.assertEqual(finished.returncode, 1)
        self.assertEqual(self.submitted_prompts(), ["/clear"])
        self.assertIn("did not settle", finished.stderr)

    def test_a_clear_that_never_takes_effect_stops_before_the_prompt(self):
        finished = self.run_phase_change("--timeout", "1", "worker", "/code docs/plans/x/plan.md")

        self.assertEqual(finished.returncode, 1)
        self.assertEqual(self.submitted_prompts(), ["/clear"])
        self.assertIn("/clear did not take effect", finished.stderr)

    def test_a_timeout_that_is_not_whole_seconds_sends_nothing(self):
        for bad_timeout in ("abc", "0", "-1", "1.5"):
            with self.subTest(timeout=bad_timeout):
                finished = self.run_phase_change("--timeout", bad_timeout, "worker", "/code docs/plans/x/plan.md")

                self.assertEqual(finished.returncode, 1)
                self.assertEqual(self.submitted_prompts(), [])
                self.assertIn("--timeout needs whole seconds", finished.stderr)

    def test_a_pane_that_is_not_settled_gets_nothing(self):
        for status in ("working", "blocked"):
            with self.subTest(status=status):
                (self.state_dir / "status").write_text(f"{status}\n")

                finished = self.run_phase_change("worker", "/code docs/plans/x/plan.md")

                self.assertEqual(finished.returncode, 1)
                self.assertEqual(self.submitted_prompts(), [])
                self.assertIn(f"worker is {status}", finished.stderr)


if __name__ == "__main__":
    unittest.main()
