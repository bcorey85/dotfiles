"""Runs herdr-phase-change against a stub herdr-api that plays one Claude pane.

Checks that the next phase's prompt goes out only after /clear has taken effect.
"""
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest

import toolkit_paths
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
    "pane current")
        [ -f "$state/no-current-pane" ] && exit 1
        echo '{"result":{"pane":{"pane_id":"wS:pA9"}}}'
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
            ("session-done verb", ("/code session-done 2",), "/code session-done 2"),
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

    def test_a_plain_prompt_goes_out_marked_with_the_sending_pane(self):
        (self.state_dir / "clear-delay").write_text("0\n")

        finished = self.run_phase_change("worker", "Option 2. Go on.")

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(self.submitted_prompts(), ["/clear", "[from orchestrator pane wS:pA9] Option 2. Go on."])

    def test_a_slash_prompt_goes_out_unmarked(self):
        (self.state_dir / "clear-delay").write_text("0\n")

        finished = self.run_phase_change("worker", "/eng-spec docs/tickets/x.md +fast")

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(self.submitted_prompts(), ["/clear", "/eng-spec docs/tickets/x.md +fast"])

    def test_a_plain_prompt_with_no_sending_pane_sends_nothing(self):
        (self.state_dir / "no-current-pane").write_text("")

        finished = self.run_phase_change("worker", "Option 2. Go on.")

        self.assertEqual(finished.returncode, 1)
        self.assertEqual(self.submitted_prompts(), [])
        self.assertIn("cannot name the sending pane", finished.stderr)

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

    def test_the_code_verbs_the_script_keeps_are_the_ones_the_code_skill_names(self):
        script_text = HERDR_PHASE_CHANGE.read_text()
        verb_alternatives = [line.strip().split(")")[0] for line in script_text.splitlines()
                             if line.strip().startswith('""|')]
        self.assertEqual(len(verb_alternatives), 1, "expected one case line that starts with the empty prompt")
        script_verbs = set(verb_alternatives[0].split("|")) - {'""'}

        skill_text = (toolkit_paths.CLAUDE_DIR / "skills" / "code" / "SKILL.md").read_text()
        skill_lines = [line for line in skill_text.splitlines() if line.startswith("1. If the task text")]
        self.assertEqual(len(skill_lines), 1, "expected one step 1 line in the code skill")
        verbs_part = skill_lines[0].split("Otherwise run")[0]
        backticked_words = re.findall(r"`([^`]*)`", verbs_part)
        skill_verbs = {word for word in backticked_words if re.fullmatch(r"[a-z]+(-[a-z]+)*", word)}

        self.assertEqual(script_verbs, skill_verbs)
        self.assertIn("task text is empty", skill_lines[0])


if __name__ == "__main__":
    unittest.main()
