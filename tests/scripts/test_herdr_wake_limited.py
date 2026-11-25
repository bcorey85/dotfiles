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
  and the resumed-uuid file kept, pruned and left alone under tuios.
"""
import datetime
import importlib.machinery
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import time
import types
import unittest
from unittest import mock

from stubs import write_stub

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
        return json.loads(self.resumed_file().read_text())

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
        self.assertTrue(self.prompts()[0].startswith("wS:p1 "))
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
        resumed = json.loads(self.resumed_file().read_text())
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
        resumed = json.loads(self.resumed_file().read_text())
        self.assertEqual(resumed, ["e-1"])

    def test_a_new_error_after_a_resume_gets_its_own_prompt(self):
        self.write_transcript("s-1", self.api_error("e-1", "server_error"))
        self.set_panes(self.stopped_pane())
        self.run_wake()

        self.write_transcript("s-1", self.api_error("e-2", "server_error"))
        self.run_wake()

        self.assertEqual(len(self.prompts()), 2)
        resumed = json.loads((self.root / "xdg-state" / "herdr-wake-limited.resumed").read_text())
        self.assertEqual(resumed, ["e-2"])

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
        self.assertEqual(json.loads(self.resumed_file().read_text()), ["e-1"])

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
        work = {"type": "assistant", "uuid": "a-1",
                "message": {"role": "assistant", "content": [{"type": "text", "text": "Done."}]}}
        self.write_transcript("s-1", self.api_error("e-1", "server_error"), trailing=[work])

        self.run_wake()
        self.assertEqual(json.loads(self.resumed_file().read_text()), [])

    def test_an_error_id_is_dropped_once_its_pane_is_gone(self):
        self.write_transcript("s-1", self.api_error("e-1", "server_error"))
        self.set_panes(self.stopped_pane())
        self.run_wake()
        self.assertEqual(json.loads(self.resumed_file().read_text()), ["e-1"])

        self.set_panes({})
        self.run_wake()
        self.assertEqual(json.loads(self.resumed_file().read_text()), [])

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
