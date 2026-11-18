"""Runs herdr-wake-limited against a stub herdr-api that plays a few Claude panes.

Checks that only a pane showing both usage-limit-reset phrases gets Enter.
Also covers login-expired notices and the noticed-state file:
- one notice per stuck pane, with no keys sent;
- the noticed-state file: kept on a herdr outage or failed read, a cleared
  pane notifies again, a corrupt file is rewritten;
- the login line must be a whole line within the bottom ten lines;
- tuios panes are not notified;
- a line led by the corner glyph is matched and named in the notice.
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
pane = panes[sys.argv[2]]
if pane.get("fail_read"):
    sys.exit(1)
print(pane["text"])
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
    "notification show")
        [ -f "$state/no-notify" ] && exit 1
        echo "$*" >> "$state/notifications"
        echo '{"result":{}}'
        ;;
esac
"""

RESET_PROMPT = "Your usage limit has reset\nPress enter to continue"
NORMAL_WAIT = "Usage limit reached · limit resets 3:45pm\nContinuing automatically at 3:45pm · Esc to cancel"

LOGIN_EXPIRED_TAIL = ("● Login expired · Please run /login\n\n✻ Sautéed for 0s\n"
                      "╭──────────╮\n│ >        │\n╰──────────╯")


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
        self.noticed_file = self.root / "xdg-state" / "herdr-wake-limited.noticed"

    def set_panes(self, panes):
        (self.state_dir / "panes.json").write_text(json.dumps(panes))

    def run_wake(self, *args, state_home=DEFAULT_STATE_HOME, tuios=False):
        env = dict(os.environ)
        env.pop("TUIOS_SOCKET", None)
        if tuios:
            env["TUIOS_SOCKET"] = str(self.root / "tuios.sock")
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

    def notifications(self):
        notified = self.state_dir / "notifications"
        if not notified.exists():
            return []
        return notified.read_text().splitlines()

    def test_a_login_expired_tail_notifies_once_and_sends_no_keys(self):
        self.set_panes({"wS:p1": {"cwd": "/work/a", "text": LOGIN_EXPIRED_TAIL, "status": "done"}})

        finished = self.run_wake()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(self.sent_keys(), [])
        notices = self.notifications()
        self.assertEqual(len(notices), 1)
        self.assertIn("herdr-wake-limited: login expired", notices[0])
        self.assertIn("wS:p1 in /work/a stopped on ● Login expired · Please run /login", notices[0])
        self.assertIn("--sound request", notices[0])
        self.assertEqual(finished.stdout, "login expired wS:p1 /work/a\n")
        log_lines = self.log_file.read_text().splitlines()
        self.assertEqual(len(log_lines), 1)
        self.assertTrue(log_lines[0].endswith(" wS:p1 /work/a login-expired"), log_lines[0])

    def test_a_corner_glyph_login_line_notifies_and_names_the_line(self):
        corner_line = "⎿ Not logged in · Please run /login"
        self.set_panes({"wS:p1": {"cwd": "/work/a", "text": corner_line, "status": "done"}})

        finished = self.run_wake()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(self.sent_keys(), [])
        notices = self.notifications()
        self.assertEqual(len(notices), 1)
        self.assertIn(f"stopped on {corner_line}", notices[0])

    def test_the_second_run_does_not_notify_again(self):
        self.set_panes({"wS:p1": {"cwd": "/work/a", "text": LOGIN_EXPIRED_TAIL}})

        self.run_wake()
        second = self.run_wake()

        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(second.stdout, "")
        self.assertEqual(len(self.notifications()), 1)

    def test_an_unwritable_noticed_file_notifies_on_each_run(self):
        blocker = self.root / "not-a-dir"
        blocker.write_text("")
        self.set_panes({"wS:p1": {"cwd": "/work/a", "text": LOGIN_EXPIRED_TAIL}})

        first = self.run_wake(state_home=blocker)
        second = self.run_wake(state_home=blocker)

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(len(self.notifications()), 2)

    def test_a_pane_that_clears_and_expires_again_notifies_again(self):
        self.set_panes({"wS:p1": {"cwd": "/work/a", "text": LOGIN_EXPIRED_TAIL}})
        self.run_wake()
        self.set_panes({"wS:p1": {"cwd": "/work/a", "text": "all done"}})
        self.run_wake()
        self.assertEqual(len(self.notifications()), 1)
        self.assertEqual(json.loads(self.noticed_file.read_text()), [])
        self.set_panes({"wS:p1": {"cwd": "/work/a", "text": "Not logged in · Please run /login"}})

        self.run_wake()

        self.assertEqual(len(self.notifications()), 2)

    def test_a_pane_that_leaves_idle_is_dropped_even_with_the_login_line_on_screen(self):
        self.set_panes({"wS:p1": {"cwd": "/work/a", "text": LOGIN_EXPIRED_TAIL}})
        self.run_wake()
        self.set_panes({"wS:p1": {"cwd": "/work/a", "text": LOGIN_EXPIRED_TAIL,
                                  "status": "working"}})

        self.run_wake()

        self.assertEqual(json.loads(self.noticed_file.read_text()), [])
        self.set_panes({"wS:p1": {"cwd": "/work/a", "text": LOGIN_EXPIRED_TAIL}})
        self.run_wake()
        self.assertEqual(len(self.notifications()), 2)

    def test_a_pane_that_disappears_is_dropped_from_the_noticed_list(self):
        self.set_panes({"wS:p1": {"cwd": "/work/a", "text": LOGIN_EXPIRED_TAIL}})
        self.run_wake()
        self.set_panes({"wS:p2": {"cwd": "/work/b", "text": "all done"}})

        self.run_wake()

        self.assertEqual(json.loads(self.noticed_file.read_text()), [])

    def test_a_normal_done_pane_does_not_notify(self):
        self.set_panes({"wS:p1": {"cwd": "/work/a", "text": "all done\n>", "status": "done"}})

        finished = self.run_wake()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(self.notifications(), [])

    def test_a_quoted_login_phrase_does_not_notify(self):
        quoted = 'The pane said "Login expired · Please run /login" earlier\n> next'
        self.set_panes({"wS:p1": {"cwd": "/work/a", "text": quoted}})

        finished = self.run_wake()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(self.notifications(), [])

    def test_a_login_expired_pane_under_tuios_is_not_notified(self):
        self.set_panes({"wS:p1": {"cwd": "/work/a", "text": LOGIN_EXPIRED_TAIL}})

        finished = self.run_wake(tuios=True)

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(self.notifications(), [])
        self.assertEqual(finished.stdout, "")
        self.assertFalse(self.noticed_file.exists())
        self.run_wake()
        self.assertEqual(len(self.notifications()), 1)

    def test_a_tuios_run_leaves_the_herdr_noticed_list_alone(self):
        self.set_panes({"wS:p1": {"cwd": "/work/a", "text": LOGIN_EXPIRED_TAIL}})
        self.run_wake()
        self.set_panes({"tuios:1": {"cwd": "/work/t", "text": "all done"}})

        self.run_wake(tuios=True)

        self.assertEqual(json.loads(self.noticed_file.read_text()), ["wS:p1"])

    def test_a_herdr_outage_keeps_the_noticed_list(self):
        self.set_panes({"wS:p1": {"cwd": "/work/a", "text": LOGIN_EXPIRED_TAIL}})
        self.run_wake()
        (self.state_dir / "no-answer").write_text("")

        outage = self.run_wake()

        self.assertEqual(outage.returncode, 0)
        self.assertEqual(json.loads(self.noticed_file.read_text()), ["wS:p1"])
        (self.state_dir / "no-answer").unlink()
        self.run_wake()
        self.assertEqual(len(self.notifications()), 1)

    def test_a_failed_read_of_an_announced_pane_does_not_renotify(self):
        self.set_panes({"wS:p1": {"cwd": "/work/a", "text": LOGIN_EXPIRED_TAIL}})
        self.run_wake()
        self.set_panes({"wS:p1": {"cwd": "/work/a", "text": LOGIN_EXPIRED_TAIL, "fail_read": True}})
        self.run_wake()
        self.set_panes({"wS:p1": {"cwd": "/work/a", "text": LOGIN_EXPIRED_TAIL}})

        self.run_wake()

        self.assertEqual(len(self.notifications()), 1)

    def test_a_failed_notification_is_named_and_retried_next_run(self):
        self.set_panes({"wS:p1": {"cwd": "/work/a", "text": LOGIN_EXPIRED_TAIL}})
        (self.state_dir / "no-notify").write_text("")

        failed = self.run_wake()

        self.assertEqual(failed.returncode, 0, failed.stderr)
        self.assertEqual(failed.stdout, "")
        self.assertFalse(self.log_file.exists())
        self.assertIn("wS:p1", failed.stderr)
        (self.state_dir / "no-notify").unlink()
        retried = self.run_wake()
        self.assertEqual(retried.stdout, "login expired wS:p1 /work/a\n")
        self.assertEqual(len(self.notifications()), 1)

    def test_a_cleared_pane_renotifies_while_a_still_stuck_pane_does_not(self):
        stuck = {"cwd": "/work/a", "text": LOGIN_EXPIRED_TAIL}
        self.set_panes({"wS:p1": stuck, "wS:p2": dict(stuck, cwd="/work/b")})
        self.run_wake()
        self.assertEqual(len(self.notifications()), 2)
        self.set_panes({"wS:p1": dict(stuck, text="all done"), "wS:p2": dict(stuck, cwd="/work/b")})
        self.run_wake()
        self.assertEqual(json.loads(self.noticed_file.read_text()), ["wS:p2"])
        self.assertEqual(len(self.notifications()), 2)
        self.set_panes({"wS:p1": stuck, "wS:p2": dict(stuck, cwd="/work/b")})

        self.run_wake()

        notices = self.notifications()
        self.assertEqual(len(notices), 3)
        self.assertIn("wS:p1", notices[2])

    def test_the_login_line_must_be_whole_and_within_the_bottom_ten_lines(self):
        def lines_below(count):
            return "\n".join(f"line {n}" for n in range(count))

        cases = [
            ("exactly tenth from the bottom", "Login expired · Please run /login\n" + lines_below(9), 1),
            ("eleventh from the bottom", "Login expired · Please run /login\n" + lines_below(10), 0),
            ("leading corner glyph", "⎿ Not logged in · Please run /login", 1),
            ("trailing text", "Login expired · Please run /login now", 0),
        ]
        for label, text, expected in cases:
            with self.subTest(label):
                shutil.rmtree(self.state_dir)
                self.state_dir.mkdir()
                self.noticed_file.unlink(missing_ok=True)
                self.set_panes({"wS:p1": {"cwd": "/work/a", "text": text}})

                self.run_wake()

                self.assertEqual(len(self.notifications()), expected, label)

    def test_a_corrupt_noticed_file_notifies_once_and_is_rewritten(self):
        self.noticed_file.parent.mkdir(parents=True)
        self.noticed_file.write_text("not json")
        self.set_panes({"wS:p1": {"cwd": "/work/a", "text": LOGIN_EXPIRED_TAIL}})

        finished = self.run_wake()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(len(self.notifications()), 1)
        self.assertEqual(json.loads(self.noticed_file.read_text()), ["wS:p1"])

    def test_a_pane_with_both_a_login_line_and_the_reset_prompt_gets_no_keys(self):
        both = RESET_PROMPT + "\nLogin expired · Please run /login"
        self.set_panes({"wS:p1": {"cwd": "/work/a", "text": both}})

        finished = self.run_wake()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(self.sent_keys(), [])
        self.assertEqual(len(self.notifications()), 1)

    def test_an_unwritable_noticed_file_is_named_and_the_pane_is_still_notified(self):
        blocker = self.root / "not-a-dir"
        blocker.write_text("")
        self.set_panes({"wS:p1": {"cwd": "/work/a", "text": LOGIN_EXPIRED_TAIL}})

        finished = self.run_wake(state_home=blocker)

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(len(self.notifications()), 1)
        self.assertIn(str(blocker / "herdr-wake-limited.noticed"), finished.stderr)

    def test_help_prints_usage_and_sends_nothing(self):
        self.set_panes({"wS:p1": {"cwd": "/work/a", "text": RESET_PROMPT}})

        finished = self.run_wake("--help")

        self.assertEqual(finished.returncode, 0)
        self.assertIn("Usage: herdr-wake-limited", finished.stdout)
        self.assertEqual(self.sent_keys(), [])
        self.assertFalse(self.log_file.exists())


if __name__ == "__main__":
    unittest.main()
