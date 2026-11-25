"""Runs herdr-wake-limited against a stub herdr-api that plays a few Claude panes.

Checks that only a pane showing both usage-limit-reset phrases gets Enter.
Also covers login-expired notices and the noticed-state file:
- one notice per stuck pane, with no keys sent;
- the noticed-state file: kept on a herdr outage or failed read, a cleared
  pane notifies again, a corrupt file is rewritten;
- the login line must be a whole line within the bottom ten lines;
- tuios panes are not notified;
- a line led by the corner glyph is matched and named in the notice;
- resume prompts: one per error record to a pane whose transcript ends on a cleared usage-limit or server
  error (records written after the error are skipped), none for a login error or a pane at a screen prompt,
  and the resumed file (last answered uuid and resume count per session) kept, pruned and left alone under
  tuios; at most three resumes in a row per session, then one `gave up` line.
"""
import datetime
import importlib.machinery
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest import mock

import toolkit_paths
from stubs import write_stub

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import process_group

# A usage-limit reset an hour ago: past its margin, inside the resume age cap.
RESET_AN_HOUR_AGO = int(datetime.datetime.now(datetime.timezone.utc).timestamp()) - 3600

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
           "agent_status": pane.get("status", "idle"),
           **({"agent_session": {"value": pane["session"]}} if pane.get("session") else {})}
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
    "agent prompt")
        [ -f "$state/no-prompt" ] && exit 1
        printf '%s %s\n' "$3" "$4" >> "$state/prompts"
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
        # A link, not a copy: the script finds the toolkit lib from its real path.
        (self.bin_dir / "herdr-wake-limited").symlink_to(HERDR_WAKE_LIMITED)
        write_stub(self.bin_dir / "herdr-api", STUB_HERDR_API)

        self.state_dir = self.root / "state"
        self.state_dir.mkdir()
        self.keys = self.state_dir / "keys"
        self.log_file = self.root / "xdg-state" / "herdr-wake-limited.log"
        self.noticed_file = self.root / "xdg-state" / "herdr-wake-limited.noticed"

    def set_panes(self, panes):
        (self.state_dir / "panes.json").write_text(json.dumps(panes))

    def run_wake(self, *args, state_home=DEFAULT_STATE_HOME, tuios=False, stub_on_path=True):
        env = dict(os.environ)
        env.pop("TUIOS_SOCKET", None)
        if tuios:
            env["TUIOS_SOCKET"] = str(self.root / "tuios.sock")
        env["HOME"] = str(self.root)
        if stub_on_path:
            env["PATH"] = f"{self.bin_dir}:{env['PATH']}"
        else:
            # Drop every entry that holds a herdr-api, so only the script's own prepend can find one.
            entries = env["PATH"].split(os.pathsep)
            kept = [entry for entry in entries if not shutil.which("herdr-api", path=entry)]
            env["PATH"] = os.pathsep.join(kept)
        env["STATE_DIR"] = str(self.state_dir)
        env.pop("XDG_STATE_HOME", None)
        env.pop("CLAUDE_CONFIG_DIR", None)
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

    def stub_sweep(self, body="exit 0"):
        """A herdr-lane-sweep beside the script that appends a line to the returned file on each call."""
        sweep_calls = self.root / "sweep-calls"
        write_stub(self.bin_dir / "herdr-lane-sweep", f"echo called >> {sweep_calls}\n{body}")
        return sweep_calls

    def sweep_log(self):
        return (self.root / "xdg-state" / "herdr-lane-sweep.log").read_text()

    def sweep_calls(self, sweep_calls):
        return sweep_calls.read_text().splitlines() if sweep_calls.exists() else []

    def test_the_lane_sweep_runs_on_the_first_call_not_within_ten_minutes_and_again_once_the_stamp_is_old(self):
        sweep_calls = self.stub_sweep("echo swept")
        stamp = self.root / "xdg-state" / "herdr-lane-sweep.stamp"
        self.set_panes({})

        first = self.run_wake()
        second = self.run_wake()

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(len(self.sweep_calls(sweep_calls)), 1)
        self.assertEqual(first.stdout, "")
        self.assertEqual(self.sweep_log(), "swept\n")

        recent = time.time() - 9 * 60
        os.utime(stamp, (recent, recent))
        self.run_wake()
        self.assertEqual(len(self.sweep_calls(sweep_calls)), 1)

        old = time.time() - 11 * 60
        os.utime(stamp, (old, old))
        self.run_wake()
        self.assertEqual(len(self.sweep_calls(sweep_calls)), 2)

    def test_the_wake_run_waits_for_the_lane_sweep_to_finish(self):
        self.stub_sweep("sleep 1; echo finished >> " + str(self.root / "sweep-done"))
        self.set_panes({})

        finished = self.run_wake()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertTrue((self.root / "sweep-done").exists(), "the wake run returned before the sweep finished")

    def test_a_hung_lane_sweep_and_its_children_are_killed_at_the_cap_and_the_kill_is_logged(self):
        child_pid_file = self.root / "child-pid"
        self.stub_sweep(f"sleep 60 &\necho $! > {child_pid_file}\nsleep 60")
        loader = importlib.machinery.SourceFileLoader("herdr_wake_limited_under_test",
                                                      str(self.bin_dir / "herdr-wake-limited"))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        wake = importlib.util.module_from_spec(spec)
        loader.exec_module(wake)
        wake.SWEEP_TIMEOUT_SECONDS = 1

        started = time.monotonic()
        with mock.patch.dict(os.environ, {"XDG_STATE_HOME": str(self.root / "xdg-state")}):
            wake.run_lane_sweep()
        elapsed = time.monotonic() - started

        self.assertLess(elapsed, 10, "the wake run did not return after the cap")
        self.assertIn("killed after 1s", self.sweep_log())
        child_pid = int(child_pid_file.read_text())
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and process_group.pid_is_alive(child_pid):
            time.sleep(0.1)
        self.assertFalse(process_group.pid_is_alive(child_pid), "the sweep's child survived the kill")

    def test_an_unwritable_sweep_stamp_is_named_and_the_wake_run_is_unchanged(self):
        sweep_calls = self.stub_sweep()
        self.set_panes({"wS:p1": {"cwd": "/work/a", "text": RESET_PROMPT}})
        stamp = self.root / "xdg-state" / "herdr-lane-sweep.stamp"
        stamp.parent.mkdir(parents=True)
        # A dangling link: touching it tries to create a file in a folder that does not exist.
        stamp.symlink_to(self.root / "no-such-dir" / "x")

        finished = self.run_wake()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(finished.stdout, "woke wS:p1 /work/a\n")
        self.assertIn("could not write", finished.stderr)
        self.assertEqual(self.sweep_calls(sweep_calls), [])

    def test_an_unwritable_sweep_log_is_named_and_the_wake_run_is_unchanged(self):
        sweep_calls = self.stub_sweep()
        self.set_panes({"wS:p1": {"cwd": "/work/a", "text": RESET_PROMPT}})
        (self.root / "xdg-state" / "herdr-lane-sweep.log").mkdir(parents=True)

        finished = self.run_wake()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(finished.stdout, "woke wS:p1 /work/a\n")
        self.assertIn("herdr-lane-sweep.log", finished.stderr)
        self.assertEqual(self.sweep_calls(sweep_calls), [])

    def test_a_failing_lane_sweep_leaves_the_wake_run_and_its_exit_code_as_before(self):
        sweep_calls = self.stub_sweep("echo sweep-broke >&2; exit 3")
        self.set_panes({"wS:p1": {"cwd": "/work/a", "text": RESET_PROMPT}})

        finished = self.run_wake()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(self.sent_keys(), ["wS:p1 enter"])
        self.assertEqual(finished.stdout, "woke wS:p1 /work/a\n")
        self.assertEqual(finished.stderr, "")
        self.assertEqual(len(self.sweep_calls(sweep_calls)), 1)
        self.assertIn("sweep-broke", self.sweep_log())

        self.run_wake()
        self.assertEqual(
            len(self.sweep_calls(sweep_calls)), 1, "a failed sweep is stamped, so it waits for the interval"
        )

    def test_a_missing_lane_sweep_is_logged_and_the_wake_run_is_unchanged(self):
        self.set_panes({"wS:p1": {"cwd": "/work/a", "text": RESET_PROMPT}})

        finished = self.run_wake()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(self.sent_keys(), ["wS:p1 enter"])
        self.assertEqual(finished.stderr, "")
        self.assertEqual(finished.stdout, "woke wS:p1 /work/a\n")
        self.assertIn("could not run", self.sweep_log())

    def test_no_lane_sweep_runs_under_tuios(self):
        sweep_calls = self.stub_sweep()
        self.set_panes({})

        finished = self.run_wake(tuios=True)

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(self.sweep_calls(sweep_calls), [])
        self.assertFalse((self.root / "xdg-state" / "herdr-lane-sweep.stamp").exists())

    def test_no_lane_sweep_runs_when_herdr_gives_no_agent_list(self):
        sweep_calls = self.stub_sweep()
        (self.state_dir / "no-answer").write_text("")

        finished = self.run_wake()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(self.sweep_calls(sweep_calls), [])
        self.assertFalse((self.root / "xdg-state" / "herdr-lane-sweep.stamp").exists())

    # Resume prompts for panes whose transcript ends on an API error.

    def prompts(self):
        prompts_file = self.state_dir / "prompts"
        if not prompts_file.exists():
            return []
        return prompts_file.read_text().splitlines()

    def write_transcript(self, session, last_record, trailing=()):
        transcript = self.root / ".claude" / "projects" / "-work-a" / f"{session}.jsonl"
        transcript.parent.mkdir(parents=True, exist_ok=True)
        first = {"type": "user", "uuid": "u-1", "message": {"role": "user", "content": "go"}}
        records = [first, last_record, *trailing]
        transcript.write_text("".join(json.dumps(record) + "\n" for record in records))

    def resumed_file(self):
        return self.root / "xdg-state" / "herdr-wake-limited.resumed"

    def resumed_uuids(self):
        if not self.resumed_file().exists():
            return []
        state = json.loads(self.resumed_file().read_text())
        return [entry["uuid"] for entry in state.values()]

    def resumed_counts(self):
        state = json.loads(self.resumed_file().read_text())
        return {session_id: entry["count"] for session_id, entry in state.items()}

    def api_error(self, uuid, error, **fields):
        return {"type": "assistant", "uuid": uuid, "isApiErrorMessage": True, "error": error,
                "timestamp": (datetime.datetime.now(datetime.timezone.utc)
                              - datetime.timedelta(hours=1)).isoformat(),
                "message": {"role": "assistant", "content": [{"type": "text", "text": "API Error"}]},
                **fields}

    def stopped_pane(self, session="s-1", text="> "):
        return {"wS:p1": {"cwd": "/work/a", "text": text, "session": session}}

    def test_a_pane_past_its_usage_limit_reset_gets_one_resume_prompt(self):
        self.write_transcript("s-1", self.api_error("e-1", "rate_limit", apiErrorStatus=429,
                                                    quotaLimits={"resetsAt": RESET_AN_HOUR_AGO}))
        self.set_panes(self.stopped_pane())

        first = self.run_wake()
        second = self.run_wake()

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(len(self.prompts()), 1)
        self.assertRegex(self.prompts()[0], r"^wS:p1 Your last turn stopped on an API error .*Go on with the task")
        self.assertIn("resumed wS:p1 /work/a", first.stdout)
        self.assertEqual(self.sent_keys(), [])

    def test_a_reset_in_rate_limit_info_is_read(self):
        self.write_transcript("s-1", self.api_error(
            "e-1", "rate_limit", apiErrorParams={"rate_limit_info": {"resetsAt": RESET_AN_HOUR_AGO}}))
        self.set_panes(self.stopped_pane())

        self.run_wake()

        self.assertEqual(len(self.prompts()), 1)

    def test_an_overloaded_pane_gets_a_resume_prompt(self):
        self.write_transcript("s-1", self.api_error("e-1", "server_error", apiErrorStatus=529))
        self.set_panes(self.stopped_pane())

        self.run_wake()

        self.assertEqual(len(self.prompts()), 1)

    def test_a_usage_limit_that_has_not_reset_gets_nothing(self):
        self.write_transcript("s-1", self.api_error("e-1", "rate_limit",
                                                    quotaLimits={"resetsAt": 4000000000}))
        self.set_panes(self.stopped_pane())

        self.run_wake()

        self.assertEqual(self.prompts(), [])

    def test_a_pane_whose_turn_ended_normally_gets_nothing(self):
        self.write_transcript("s-1", {"type": "assistant", "uuid": "a-1",
                                      "message": {"role": "assistant", "content": [{"type": "text", "text": "Done."}]}})
        self.set_panes(self.stopped_pane())

        finished = self.run_wake()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(self.prompts(), [])

    def test_a_login_or_billing_error_gets_no_resume_prompt(self):
        for error in ("authentication_failed", "billing_error"):
            with self.subTest(error=error):
                self.write_transcript("s-1", self.api_error(f"e-{error}", error))
                self.set_panes(self.stopped_pane())

                self.run_wake()

                self.assertEqual(self.prompts(), [])

    def test_a_working_pane_gets_no_resume_prompt(self):
        self.write_transcript("s-1", self.api_error("e-1", "server_error"))
        panes = self.stopped_pane()
        panes["wS:p1"]["status"] = "working"
        self.set_panes(panes)

        self.run_wake()

        self.assertEqual(self.prompts(), [])

    def test_a_pane_at_the_reset_prompt_gets_enter_and_no_resume_prompt(self):
        self.write_transcript("s-1", self.api_error("e-1", "rate_limit",
                                                    quotaLimits={"resetsAt": RESET_AN_HOUR_AGO}))
        self.set_panes(self.stopped_pane(text=RESET_PROMPT))

        self.run_wake()

        self.assertEqual(self.sent_keys(), ["wS:p1 enter"])
        self.assertEqual(self.prompts(), [])

    def test_under_tuios_no_resume_prompt_goes_out(self):
        self.write_transcript("s-1", self.api_error("e-1", "server_error"))
        self.set_panes(self.stopped_pane())

        self.run_wake(tuios=True)

        self.assertEqual(self.prompts(), [])

    def test_a_failed_prompt_is_named_and_retried_next_run(self):
        self.write_transcript("s-1", self.api_error("e-1", "server_error"))
        self.set_panes(self.stopped_pane())
        (self.state_dir / "no-prompt").touch()

        failed = self.run_wake()
        (self.state_dir / "no-prompt").unlink()
        self.run_wake()

        self.assertIn("wS:p1", failed.stderr)
        self.assertEqual(len(self.prompts()), 1)

    def test_an_error_record_with_no_string_uuid_gets_no_prompt(self):
        for label, change in (("missing", None), ("integer", 7)):
            with self.subTest(label):
                record = self.api_error("e-1", "server_error")
                del record["uuid"]
                if change is not None:
                    record["uuid"] = change
                self.write_transcript("s-1", record)
                self.set_panes(self.stopped_pane())

                result = self.run_wake()

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.prompts(), [])
                self.assertEqual(self.resumed_uuids(), [])

    def test_a_pane_with_no_session_or_no_transcript_gets_no_prompt(self):
        no_session = {"wS:p1": {"cwd": "/work/a", "text": "> "}}
        no_transcript = self.stopped_pane(session="s-missing")
        for label, panes in (("no session", no_session), ("no transcript", no_transcript)):
            with self.subTest(label):
                self.set_panes(panes)

                result = self.run_wake()

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.prompts(), [])
                self.assertEqual(self.resumed_uuids(), [])

    @unittest.skipIf(os.geteuid() == 0, "root ignores chmod 0")
    def test_a_failed_transcript_read_keeps_the_answered_uuid_so_the_pane_is_not_prompted_twice(self):
        self.write_transcript("s-1", self.api_error("e-1", "server_error"))
        self.set_panes(self.stopped_pane())
        self.run_wake()
        transcript = next((self.root / ".claude" / "projects").rglob("s-1.jsonl"))

        transcript.chmod(0)
        try:
            unreadable = self.run_wake()
        finally:
            transcript.chmod(0o644)
        self.run_wake()

        self.assertEqual(unreadable.returncode, 0, unreadable.stderr)
        self.assertIn("could not read", unreadable.stderr)
        self.assertEqual(len(self.prompts()), 1)
        resumed = self.resumed_uuids()
        self.assertEqual(resumed, ["e-1"])

    def test_a_working_pane_keeps_its_answered_uuid_so_it_is_not_prompted_again_when_idle(self):
        self.write_transcript("s-1", self.api_error("e-1", "server_error"))
        panes = self.stopped_pane()
        self.set_panes(panes)
        self.run_wake()

        panes["wS:p1"]["status"] = "working"
        self.set_panes(panes)
        self.run_wake()
        panes["wS:p1"]["status"] = "idle"
        self.set_panes(panes)
        self.run_wake()

        self.assertEqual(len(self.prompts()), 1)
        resumed = self.resumed_uuids()
        self.assertEqual(resumed, ["e-1"])

    def test_a_new_error_after_a_resume_gets_its_own_prompt(self):
        self.write_transcript("s-1", self.api_error("e-1", "server_error"))
        self.set_panes(self.stopped_pane())
        self.run_wake()

        self.write_transcript("s-1", self.api_error("e-2", "server_error"))
        self.run_wake()

        self.assertEqual(len(self.prompts()), 2)
        resumed = self.resumed_uuids()
        self.assertEqual(resumed, ["e-2"])

    def test_a_pane_whose_every_resume_hits_a_new_server_error_gets_at_most_3_prompts(self):
        self.set_panes(self.stopped_pane())
        runs = []
        error_number = 1
        self.write_transcript("s-1", self.api_error("e-1", "server_error"))
        for _ in range(8):
            prompts_before = len(self.prompts())
            runs.append(self.run_wake())
            if len(self.prompts()) > prompts_before:
                # The resumed turn hits the outage again and writes a new error record.
                error_number += 1
                self.write_transcript("s-1", self.api_error(f"e-{error_number}", "server_error"))

        gave_up = [run.stdout for run in runs if "gave up wS:p1 /work/a" in run.stdout]
        self.assertEqual(len(self.prompts()), 3)
        self.assertEqual(len(gave_up), 1)
        self.assertEqual(self.resumed_counts(), {"s-1": 3})

    def test_the_count_resets_after_a_turn_that_ends_normally(self):
        self.set_panes(self.stopped_pane())
        for number in (1, 2):
            self.write_transcript("s-1", self.api_error(f"e-{number}", "server_error"))
            self.run_wake()
        work = {"type": "assistant", "uuid": "a-1",
                "message": {"role": "assistant", "content": [{"type": "text", "text": "Done."}]}}
        self.write_transcript("s-1", work)
        self.run_wake()
        self.assertEqual(json.loads(self.resumed_file().read_text()), {})

        for number in (3, 4, 5, 6):
            self.write_transcript("s-1", self.api_error(f"e-{number}", "server_error"))
            self.run_wake()

        self.assertEqual(len(self.prompts()), 5)
        self.assertEqual(self.resumed_counts(), {"s-1": 3})

    def test_a_resumed_file_in_the_old_uuid_list_format_is_read_as_one_resume(self):
        self.resumed_file().parent.mkdir(parents=True, exist_ok=True)
        self.resumed_file().write_text('["e-1"]')
        self.write_transcript("s-1", self.api_error("e-1", "server_error"))
        self.set_panes(self.stopped_pane())

        first = self.run_wake()
        self.write_transcript("s-1", self.api_error("e-2", "server_error"))
        second = self.run_wake()

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(len(self.prompts()), 1)
        self.assertEqual(self.resumed_counts(), {"s-1": 2})

    def test_records_written_after_the_error_do_not_hide_it(self):
        # The tail Claude Code writes after a usage-limit error: a turn duration, a last prompt, a cost state.
        trailing = [{"type": "system", "subtype": "turn_duration", "durationMs": 10},
                    {"type": "last-prompt", "lastPrompt": "go"},
                    {"type": "cost-state", "cost": 0.1}]
        self.write_transcript("s-1", self.api_error("e-1", "rate_limit", quotaLimits={"resetsAt": RESET_AN_HOUR_AGO}),
                              trailing=trailing)
        self.set_panes(self.stopped_pane())

        self.run_wake()

        self.assertEqual(len(self.prompts()), 1)

    def test_a_login_text_under_a_server_error_gets_no_resume_prompt(self):
        login_message = {"role": "assistant", "content": [{"type": "text", "text": "Please run /login"}]}
        self.write_transcript("s-1", self.api_error("e-1", "server_error", message=login_message))
        self.set_panes(self.stopped_pane())

        self.run_wake()

        self.assertEqual(self.prompts(), [])

    def test_a_usage_limit_waits_a_minute_past_its_reset(self):
        now = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
        cases = {"reset 30 seconds ago": (now - 30, 0), "reset 2 minutes ago": (now - 120, 1)}
        for name, (resets_at, expected) in cases.items():
            with self.subTest(name):
                (self.state_dir / "prompts").unlink(missing_ok=True)
                self.resumed_file().unlink(missing_ok=True)
                self.write_transcript("s-1", self.api_error("e-1", "rate_limit",
                                                            quotaLimits={"resetsAt": resets_at}))
                self.set_panes(self.stopped_pane())

                self.run_wake()

                self.assertEqual(len(self.prompts()), expected)

    def test_a_server_error_waits_five_minutes(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        cases = {"just now": (now, 0), "six minutes ago": (now - datetime.timedelta(minutes=6), 1)}
        for name, (stamp, expected) in cases.items():
            with self.subTest(name):
                (self.state_dir / "prompts").unlink(missing_ok=True)
                self.resumed_file().unlink(missing_ok=True)
                self.write_transcript("s-1", self.api_error("e-1", "server_error", timestamp=stamp.isoformat()))
                self.set_panes(self.stopped_pane())

                self.run_wake()

                self.assertEqual(len(self.prompts()), expected)

    def test_a_usage_limit_with_no_reset_time_gets_nothing(self):
        self.write_transcript("s-1", self.api_error("e-1", "rate_limit"))
        self.set_panes(self.stopped_pane())

        self.run_wake()

        self.assertEqual(self.prompts(), [])

    def test_a_pane_that_shows_a_reset_prompt_after_its_resume_is_not_prompted_again(self):
        self.write_transcript("s-1", self.api_error("e-1", "server_error"))
        self.set_panes(self.stopped_pane())
        self.run_wake()
        self.set_panes(self.stopped_pane(text=RESET_PROMPT))
        self.run_wake()
        self.set_panes(self.stopped_pane())

        self.run_wake()

        self.assertEqual(len(self.prompts()), 1)
        self.assertEqual(self.resumed_uuids(), ["e-1"])

    def test_a_login_expired_pane_with_a_server_error_is_noticed_and_not_prompted(self):
        self.write_transcript("s-1", self.api_error("e-1", "server_error"))
        self.set_panes(self.stopped_pane(text=LOGIN_EXPIRED_TAIL))

        self.run_wake()

        self.assertEqual(len(self.notifications()), 1)
        self.assertEqual(self.prompts(), [])

    def test_under_tuios_the_resumed_file_is_neither_read_nor_written(self):
        self.write_transcript("s-1", self.api_error("e-1", "server_error"))
        self.set_panes(self.stopped_pane())

        self.run_wake(tuios=True)
        self.assertFalse(self.resumed_file().exists())

        self.resumed_file().parent.mkdir(parents=True, exist_ok=True)
        self.resumed_file().write_text('["old"]')
        self.run_wake(tuios=True)
        self.assertEqual(self.resumed_file().read_text(), '["old"]')

    def test_an_error_id_is_dropped_once_its_pane_no_longer_ends_on_it(self):
        self.write_transcript("s-1", self.api_error("e-1", "server_error"))
        self.set_panes(self.stopped_pane())
        self.run_wake()
        self.assertEqual(self.resumed_uuids(), ["e-1"])
        work = {"type": "assistant", "uuid": "a-1",
                "message": {"role": "assistant", "content": [{"type": "text", "text": "Done."}]}}
        self.write_transcript("s-1", self.api_error("e-1", "server_error"), trailing=[work])

        self.run_wake()
        self.assertEqual(self.resumed_uuids(), [])

    def test_a_corrupt_resumed_file_is_rewritten_after_one_prompt(self):
        self.resumed_file().parent.mkdir(parents=True, exist_ok=True)
        self.resumed_file().write_text("not json")
        self.write_transcript("s-1", self.api_error("e-1", "server_error"))
        self.set_panes(self.stopped_pane())

        first = self.run_wake()
        second = self.run_wake()

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(len(self.prompts()), 1)
        self.assertEqual(self.resumed_uuids(), ["e-1"])

    def test_an_unwritable_resumed_file_is_named_and_the_pane_is_still_prompted(self):
        blocker = self.root / "not-a-dir"
        blocker.write_text("")
        self.write_transcript("s-1", self.api_error("e-1", "server_error"))
        self.set_panes(self.stopped_pane())

        finished = self.run_wake(state_home=blocker)

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(len(self.prompts()), 1)
        self.assertIn(str(blocker / "herdr-wake-limited.resumed"), finished.stderr)

    def test_an_error_id_is_dropped_once_its_pane_is_gone(self):
        self.write_transcript("s-1", self.api_error("e-1", "server_error"))
        self.set_panes(self.stopped_pane())
        self.run_wake()
        self.assertEqual(self.resumed_uuids(), ["e-1"])

        self.set_panes({})
        self.run_wake()
        self.assertEqual(self.resumed_uuids(), [])

    def test_a_pane_whose_screen_read_fails_gets_no_resume_prompt_that_run(self):
        self.write_transcript("s-1", self.api_error("e-1", "server_error"))
        unreadable = self.stopped_pane()
        unreadable["wS:p1"]["fail_read"] = True
        self.set_panes(unreadable)

        failed = self.run_wake()

        self.assertEqual(failed.returncode, 0, failed.stderr)
        self.assertEqual(self.prompts(), [])
        self.set_panes(self.stopped_pane())
        self.run_wake()
        self.assertEqual(len(self.prompts()), 1)

    def test_a_pane_with_a_half_typed_reply_gets_no_resume_prompt(self):
        self.write_transcript("s-1", self.api_error("e-1", "server_error"))
        boxed = "● API Error\n╭──────────────╮\n│ > half a rep │\n╰──────────────╯\n  ? for shortcuts"
        bare = "● API Error\n────────\n\N{HEAVY RIGHT-POINTING ANGLE QUOTATION MARK ORNAMENT} half a reply\n────────"
        for screen in (boxed, bare):
            self.set_panes(self.stopped_pane(text=screen))
            self.run_wake()
            self.assertEqual(self.prompts(), [], screen)

    def test_a_multi_row_draft_above_the_real_footer_gets_no_resume_prompt(self):
        self.write_transcript("s-1", self.api_error("e-1", "server_error"))
        rule = "─" * 20
        footer = (f"{rule}\n➜ [Opus 5.5] repo git:(main)\n[███ 112k]\n⏵⏵ auto mode on")
        marker = "\N{HEAVY RIGHT-POINTING ANGLE QUOTATION MARK ORNAMENT}"
        drafts = {
            "three rows": f"{marker} first row\nsecond row\nthird row",
            "two rows": f"{marker} first row\nsecond row",
            "four rows": f"{marker} first row\nsecond row\nthird row\nfourth row",
        }
        for name, draft in drafts.items():
            with self.subTest(name):
                self.set_panes(self.stopped_pane(text=f"● API Error\n{rule}\n{draft}\n{footer}"))
                self.run_wake()
                self.assertEqual(self.prompts(), [], name)

    def test_an_empty_input_line_above_a_tall_footer_gets_the_resume_prompt(self):
        self.write_transcript("s-1", self.api_error("e-1", "server_error"))
        marker = "\N{HEAVY RIGHT-POINTING ANGLE QUOTATION MARK ORNAMENT}"
        footer = "\n".join(f"status row {number}" for number in range(8))
        self.set_panes(self.stopped_pane(text=f"● API Error\n────\n{marker} \n────\n{footer}"))

        self.run_wake()

        self.assertEqual(len(self.prompts()), 1)

    def test_a_screen_with_no_input_line_gets_no_resume_prompt(self):
        self.write_transcript("s-1", self.api_error("e-1", "server_error"))
        self.set_panes(self.stopped_pane(text="● API Error\nsome output"))

        self.run_wake()

        self.assertEqual(self.prompts(), [])

    @unittest.skipIf(os.geteuid() == 0, "root ignores chmod 0")
    def test_a_run_with_an_unreadable_transcript_keeps_every_answered_uuid(self):
        self.write_transcript("s-1", self.api_error("e-1", "server_error"))
        self.write_transcript("s-2", self.api_error("e-2", "server_error"))
        panes = {"wS:p1": {"cwd": "/work/a", "text": "> ", "session": "s-1"},
                 "wS:p2": {"cwd": "/work/a", "text": "> ", "session": "s-2"}}
        self.set_panes(panes)
        self.run_wake()
        transcript = next((self.root / ".claude" / "projects").rglob("s-1.jsonl"))

        transcript.chmod(0)
        try:
            self.run_wake()
        finally:
            transcript.chmod(0o644)

        self.assertEqual(len(self.prompts()), 2)
        self.assertEqual(sorted(self.resumed_uuids()), ["e-1", "e-2"])

    def test_the_last_marker_line_decides_whether_the_input_holds_text(self):
        self.write_transcript("s-1", self.api_error("e-1", "server_error"))
        marker = "\N{HEAVY RIGHT-POINTING ANGLE QUOTATION MARK ORNAMENT}"
        screens = {
            "quoted marker above an empty input": (
                f"{marker} an old quoted line\n● API Error\n────\n{marker} \n────", 1),
            "empty marker above a typed input": (f"{marker} \n● API Error\n────\n{marker} half a reply\n────", 0),
        }
        for name, (screen, expected_prompts) in screens.items():
            with self.subTest(name):
                self.resumed_file().unlink(missing_ok=True)
                (self.state_dir / "prompts").unlink(missing_ok=True)
                self.set_panes(self.stopped_pane(text=screen))
                self.run_wake()
                self.assertEqual(len(self.prompts()), expected_prompts, name)

    def test_an_empty_or_placeholder_input_line_still_gets_the_resume_prompt(self):
        self.write_transcript("s-1", self.api_error("e-1", "server_error"))
        empty = "● API Error\n╭──────────────╮\n│ >            │\n╰──────────────╯"
        marker = "\N{HEAVY RIGHT-POINTING ANGLE QUOTATION MARK ORNAMENT}"
        placeholder = f'● API Error\n────────\n{marker} Try "fix lint errors"\n────────'
        for screen in (empty, placeholder):
            self.resumed_file().unlink(missing_ok=True)
            (self.state_dir / "prompts").unlink(missing_ok=True)
            self.set_panes(self.stopped_pane(text=screen))
            self.run_wake()
            self.assertEqual(len(self.prompts()), 1, screen)

    def test_an_error_whose_resume_time_passed_over_a_day_ago_gets_no_prompt(self):
        week_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)
        cases = {
            "server error": self.api_error("e-1", "server_error", timestamp=week_ago.isoformat()),
            "usage limit": self.api_error("e-2", "rate_limit",
                                          quotaLimits={"resetsAt": int(week_ago.timestamp())},
                                          timestamp=week_ago.isoformat()),
        }
        for name, record in cases.items():
            with self.subTest(name):
                self.write_transcript("s-1", record)
                self.set_panes(self.stopped_pane())

                finished = self.run_wake()

                self.assertEqual(finished.returncode, 0, finished.stderr)
                self.assertEqual(self.prompts(), [])

    def test_herdr_api_is_found_in_home_local_bin_when_path_lacks_it(self):
        home_bin = self.root / ".local" / "bin"
        home_bin.mkdir(parents=True)
        (self.bin_dir / "herdr-api").rename(home_bin / "herdr-api")
        self.set_panes({"wS:p1": {"cwd": "/work/a", "text": RESET_PROMPT}})

        finished = self.run_wake(stub_on_path=False)

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(self.sent_keys(), ["wS:p1 enter"])

    def test_a_herdr_api_call_that_hangs_gives_no_answer_after_the_timeout(self):
        hanging_dir = self.root / "hanging-bin"
        hanging_dir.mkdir()
        write_stub(hanging_dir / "herdr-api", "exec sleep 30")
        loader = importlib.machinery.SourceFileLoader("herdr_wake_limited_under_test", str(HERDR_WAKE_LIMITED))
        module = types.ModuleType(loader.name)
        module.__file__ = str(HERDR_WAKE_LIMITED)
        loader.exec_module(module)
        patched_path = f"{hanging_dir}{os.pathsep}{os.environ['PATH']}"

        with mock.patch.object(module.herdr_agents, "HERDR_CALL_TIMEOUT_SECONDS", 0.5), \
                mock.patch.dict(os.environ, {"PATH": patched_path}):
            started = time.monotonic()
            answer = module.herdr_api("agent", "list")
            elapsed = time.monotonic() - started

        self.assertIsNone(answer)
        self.assertLess(elapsed, 10)

    def test_help_prints_usage_and_sends_nothing(self):
        self.set_panes({"wS:p1": {"cwd": "/work/a", "text": RESET_PROMPT}})

        finished = self.run_wake("--help")

        self.assertEqual(finished.returncode, 0)
        self.assertIn("Usage: herdr-wake-limited", finished.stdout)
        self.assertEqual(self.sent_keys(), [])
        self.assertFalse(self.log_file.exists())


if __name__ == "__main__":
    unittest.main()
