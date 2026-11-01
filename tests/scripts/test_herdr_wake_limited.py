"""Runs herdr-wake-limited against a stub herdr-api that plays a few Claude panes.

Checks that only a pane showing both usage-limit-reset phrases gets Enter.
"""
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

from stubs import write_stub

HERDR_WAKE_LIMITED = pathlib.Path(__file__).resolve().parents[2] / "scripts" / ".local" / "bin" / "herdr-wake-limited"

# Panes live in $STATE_DIR/panes.json ({pane_id: {"cwd", "text"}}); every
# send-keys call is appended to $STATE_DIR/keys. A `no-answer` file makes every
# call fail, as when no herdr socket answers.
STUB_HERDR_API = r"""
state="$STATE_DIR"
[ -f "$state/no-answer" ] && exit 1
case "$1 $2" in
    "agent list")
        python3 -I - "$state/panes.json" <<'PY'
import json, sys
panes = json.load(open(sys.argv[1]))
agents = [{"agent": pane.get("kind", "claude"), "pane_id": pid, "cwd": pane["cwd"],
           "agent_status": pane.get("status", "idle")}
          for pid, pane in panes.items()]
print(json.dumps({"result": {"agents": agents}}))
PY
        ;;
    "agent read")
        python3 -I - "$state/panes.json" "$3" <<'PY'
import json, sys
panes = json.load(open(sys.argv[1]))
print(panes[sys.argv[2]]["text"])
PY
        ;;
    "agent send-keys")
        if python3 -I - "$state/panes.json" "$3" <<'PY'
import json, sys
panes = json.load(open(sys.argv[1]))
sys.exit(0 if panes[sys.argv[2]].get("fail_keys") else 1)
PY
        then
            exit 1
        fi
        echo "$3 $4" >> "$state/keys"
        echo '{"result":{}}'
        ;;
esac
"""

RESET_PROMPT = "Your usage limit has reset\nPress enter to continue"
NORMAL_WAIT = "Usage limit reached · limit resets 3:45pm\nContinuing automatically at 3:45pm · Esc to cancel"


DEFAULT_STATE_HOME = object()


class HerdrWakeLimitedTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = pathlib.Path(scratch.name)

        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        shutil.copy(HERDR_WAKE_LIMITED, self.bin_dir / "herdr-wake-limited")
        write_stub(self.bin_dir / "herdr-api", STUB_HERDR_API)

        self.state_dir = self.root / "state"
        self.state_dir.mkdir()
        self.keys = self.state_dir / "keys"
        self.log_file = self.root / "xdg-state" / "herdr-wake-limited.log"

    def set_panes(self, panes):
        (self.state_dir / "panes.json").write_text(json.dumps(panes))

    def run_wake(self, *args, state_home=DEFAULT_STATE_HOME):
        env = dict(os.environ)
        env["HOME"] = str(self.root)
        env["PATH"] = f"{self.bin_dir}:{env['PATH']}"
        env["STATE_DIR"] = str(self.state_dir)
        env.pop("XDG_STATE_HOME", None)
        if state_home is DEFAULT_STATE_HOME:
            state_home = self.root / "xdg-state"
        if state_home is not None:
            env["XDG_STATE_HOME"] = str(state_home)
        return subprocess.run([str(self.bin_dir / "herdr-wake-limited"), *args], env=env,
                              capture_output=True, text=True, timeout=30)

    def sent_keys(self):
        if not self.keys.exists():
            return []
        return self.keys.read_text().splitlines()

    def test_a_pane_at_the_reset_prompt_gets_one_enter_and_one_log_line(self):
        self.set_panes({"wS:p1": {"cwd": "/work/a", "text": RESET_PROMPT},
                        "wS:p2": {"cwd": "/work/b", "text": "all done"}})

        finished = self.run_wake()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(self.sent_keys(), ["wS:p1 enter"])
        self.assertIn("wS:p1", finished.stdout)
        self.assertIn("/work/a", finished.stdout)
        log_lines = self.log_file.read_text().splitlines()
        self.assertEqual(len(log_lines), 1)
        self.assertTrue(log_lines[0].endswith(" wS:p1 /work/a"), log_lines[0])

    def test_panes_without_both_phrases_get_no_keys(self):
        self.set_panes({"wS:p1": {"cwd": "/work/a", "text": NORMAL_WAIT},
                        "wS:p2": {"cwd": "/work/b", "text": "idle prompt\n>"},
                        "wS:p3": {"cwd": "/work/c", "text": "Your usage limit has reset"},
                        "wS:p4": {"cwd": "/work/d", "text": "Press enter to continue"}})

        finished = self.run_wake()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(self.sent_keys(), [])
        self.assertFalse(self.log_file.exists())

    def test_a_pane_quoting_the_phrases_above_its_bottom_lines_gets_no_keys(self):
        quoted = RESET_PROMPT + "\n" + "\n".join(f"later line {n}" for n in range(8))
        self.set_panes({"wS:p1": {"cwd": "/work/a", "text": quoted}})

        finished = self.run_wake()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(self.sent_keys(), [])

    def test_a_phrase_wrapped_by_a_narrow_pane_still_gets_enter(self):
        wrapped = "Your usage limit has\nreset\nPress enter to\ncontinue"
        self.set_panes({"wS:p1": {"cwd": "/work/a", "text": wrapped}})

        finished = self.run_wake()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(self.sent_keys(), ["wS:p1 enter"])

    def test_working_and_blocked_panes_get_no_keys_even_at_the_reset_prompt(self):
        self.set_panes({"wS:p1": {"cwd": "/work/a", "text": RESET_PROMPT, "status": "working"},
                        "wS:p2": {"cwd": "/work/b", "text": RESET_PROMPT, "status": "blocked"}})

        finished = self.run_wake()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(self.sent_keys(), [])
        self.assertFalse(self.log_file.exists())

    def test_a_done_pane_at_the_reset_prompt_gets_enter(self):
        self.set_panes({"wS:p1": {"cwd": "/work/a", "text": RESET_PROMPT, "status": "done"}})

        finished = self.run_wake()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(self.sent_keys(), ["wS:p1 enter"])

    def test_a_non_claude_pane_at_the_reset_prompt_gets_no_keys(self):
        self.set_panes({"wS:p1": {"cwd": "/work/a", "text": RESET_PROMPT, "kind": "shell"}})

        finished = self.run_wake()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(self.sent_keys(), [])
        self.assertFalse(self.log_file.exists())

    def test_a_failed_send_keys_is_named_and_the_next_pane_still_gets_enter(self):
        self.set_panes({"wS:p1": {"cwd": "/work/a", "text": RESET_PROMPT, "fail_keys": True},
                        "wS:p2": {"cwd": "/work/b", "text": RESET_PROMPT}})

        finished = self.run_wake()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertIn("wS:p1", finished.stderr)
        self.assertEqual(self.sent_keys(), ["wS:p2 enter"])
        self.assertEqual(finished.stdout, "woke wS:p2 /work/b\n")
        log_lines = self.log_file.read_text().splitlines()
        self.assertEqual(len(log_lines), 1)
        self.assertTrue(log_lines[0].endswith(" wS:p2 /work/b"), log_lines[0])

    def test_an_unwritable_log_is_named_and_the_pane_still_gets_enter(self):
        blocker = self.root / "not-a-dir"
        blocker.write_text("")
        unwritable_log = blocker / "herdr-wake-limited.log"
        self.set_panes({"wS:p1": {"cwd": "/work/a", "text": RESET_PROMPT}})

        finished = self.run_wake(state_home=blocker)

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(self.sent_keys(), ["wS:p1 enter"])
        self.assertIn(str(unwritable_log), finished.stderr)
        self.assertEqual(finished.stdout, "woke wS:p1 /work/a\n")

    def test_without_xdg_state_home_the_log_lands_under_home(self):
        self.set_panes({"wS:p1": {"cwd": "/work/a", "text": RESET_PROMPT}})

        finished = self.run_wake(state_home=None)

        self.assertEqual(finished.returncode, 0, finished.stderr)
        home_log = self.root / ".local" / "state" / "herdr-wake-limited.log"
        log_lines = home_log.read_text().splitlines()
        self.assertEqual(len(log_lines), 1)
        self.assertTrue(log_lines[0].endswith(" wS:p1 /work/a"), log_lines[0])

    def test_no_herdr_answer_exits_quietly_with_no_keys(self):
        (self.state_dir / "no-answer").write_text("")

        finished = self.run_wake()

        self.assertEqual(finished.returncode, 0)
        self.assertEqual(finished.stdout, "")
        self.assertEqual(self.sent_keys(), [])

    def test_help_prints_usage_and_sends_nothing(self):
        self.set_panes({"wS:p1": {"cwd": "/work/a", "text": RESET_PROMPT}})

        finished = self.run_wake("--help")

        self.assertEqual(finished.returncode, 0)
        self.assertIn("Usage: herdr-wake-limited", finished.stdout)
        self.assertEqual(self.sent_keys(), [])
        self.assertFalse(self.log_file.exists())


if __name__ == "__main__":
    unittest.main()
