"""Runs herdr-phase-change against a stub herdr-api that plays one Claude pane.

Checks that the next phase's prompt goes out only after /clear has taken effect.
"""
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

import toolkit_paths
from stubs import copy_toolkit_tools_lib, run_through_stow_symlink, write_stub

LANES_CLI = pathlib.Path(os.environ.get("HERDR_LANES_CLI", toolkit_paths.TOOLS_DIR / "lanes.py"))
SESSION_PANE = pathlib.Path(os.environ.get("SESSION_PANE_SCRIPT", toolkit_paths.TOOLS_DIR / "session_pane.py"))
HERDR_PHASE_CHANGE = pathlib.Path(__file__).resolve().parents[2] / "scripts" / ".local" / "bin" / "herdr-phase-change"
REPORT_TO = " [report to session orchestrator-a]"

# A session_pane.py that finds the pane as given but names no sending session.
STUB_SESSION_PANE_NO_SENDER = """import json
import sys

if sys.argv[1] == "resolve":
    print(json.dumps({"pane_id": sys.argv[2], "via": "as-given"}))
    sys.exit(0)
print(json.dumps({"name": None, "reason": "no session"}))
sys.exit(1)
"""

# The pane's state lives in files: its status, its session id, and every prompt
# submitted, one per line. A /clear swaps the session id only after
# `clear_delay` further `agent get` reads, the way the SessionStart hook reports
# the new id a moment after the prompt is accepted.
STUB_HERDR_API = r"""
state="$STATE_DIR"
case "$1 $2" in
    "agent list")
        first='{"agent":"claude","pane_id":"wS:pL1","cwd":"'$state'/wt","agent_session":{"value":"s1"}}'
        second='{"agent":"claude","pane_id":"wS:pL2","cwd":"'$state'/other","agent_session":{"value":"s9"}}'
        echo '{"result":{"agents":['"$first,$second"']}}'
        ;;
    "agent get")
        echo "$3" >> "$state/get-targets"
        if [ -f "$state/clear-pending" ]; then
            left=$(cat "$state/clear-pending")
            if [ "$left" -le 0 ]; then
                echo "s2" > "$state/session"
                rm "$state/clear-pending"
            else
                echo $((left - 1)) > "$state/clear-pending"
            fi
        fi
        cwd_field=""
        [ -f "$state/cwd" ] && cwd_field=",\"cwd\":\"$(cat "$state/cwd")\""
        printf '{"result":{"agent":{"agent_status":"%s","agent_session":{"value":"%s"}%s}}}\n' \
            "$(cat "$state/status")" "$(cat "$state/session")" "$cwd_field"
        ;;
    "agent prompt")
        echo "$3" >> "$state/prompt-targets"
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
        copy_toolkit_tools_lib(self.root)
        write_stub(self.bin_dir / "herdr-api", STUB_HERDR_API)

        self.state_dir = self.root / "state"
        self.state_dir.mkdir()
        (self.state_dir / "status").write_text("done\n")
        (self.state_dir / "session").write_text("s1\n")
        self.prompts = self.state_dir / "prompts"
        self.get_targets = self.state_dir / "get-targets"
        self.prompt_targets = self.state_dir / "prompt-targets"

        # A live registry row for session s1: the pid is a `sleep` child that the cleanup kills.
        sleeper = subprocess.Popen(["sleep", "600"])
        self.addCleanup(sleeper.wait)
        self.addCleanup(sleeper.kill)
        sessions = self.root / ".claude" / "sessions"
        sessions.mkdir(parents=True)
        row = {"pid": sleeper.pid, "sessionId": "s1", "name": "lane-x"}
        (sessions / f"{sleeper.pid}.json").write_text(json.dumps(row))

        # The sending session: CLAUDE_CODE_SESSION_ID names it, and its registry row needs its own live pid.
        orchestrator = subprocess.Popen(["sleep", "600"])
        self.addCleanup(orchestrator.wait)
        self.addCleanup(orchestrator.kill)
        orchestrator_row = {"pid": orchestrator.pid, "sessionId": "orch", "name": "orchestrator-a"}
        (sessions / f"{orchestrator.pid}.json").write_text(json.dumps(orchestrator_row))

    def run_phase_change(self, *args, cwd=None, lanes_cli=LANES_CLI, session_pane=SESSION_PANE):
        env = dict(os.environ)
        env["HOME"] = str(self.root)
        env["PATH"] = f"{self.bin_dir}:{env['PATH']}"
        env["STATE_DIR"] = str(self.state_dir)
        env["HERDR_LANES_CLI"] = str(lanes_cli)
        env["HERDR_SESSION_PANE"] = str(session_pane)
        env["CLAUDE_CODE_SESSION_ID"] = "orch"
        env.pop("CLAUDE_CONFIG_DIR", None)
        env["XDG_STATE_HOME"] = str(self.root / "lane-state")
        return subprocess.run([str(self.bin_dir / "herdr-phase-change"), *args], env=env, cwd=cwd,
                              capture_output=True, text=True, timeout=30)

    def submitted_prompts(self):
        if not self.prompts.exists():
            return []
        return self.prompts.read_text().splitlines()

    def add_lane(self, name, worktree):
        env = dict(os.environ, XDG_STATE_HOME=str(self.root / "lane-state"))
        subprocess.run(["python3", str(LANES_CLI), "add", "--name", name, "--worktree", str(worktree),
                        "--main-checkout", str(self.root), "--branch", "b", "--reports-to", "boss"],
                       input="original brief", env=env, check=True, capture_output=True, text=True)

    def lane_entry(self, name):
        env = dict(os.environ, XDG_STATE_HOME=str(self.root / "lane-state"))
        finished = subprocess.run(["python3", str(LANES_CLI), "get", name], env=env,
                                  check=True, capture_output=True, text=True)
        return json.loads(finished.stdout)["entry"]

    def test_a_phase_change_stores_the_new_session_id_and_the_sent_prompt_in_the_lane_of_the_agents_worktree(self):
        worktree = pathlib.Path(os.path.realpath(self.state_dir)) / "wt"
        worktree.mkdir()
        self.add_lane("lane-a", worktree)
        (self.state_dir / "cwd").write_text(str(worktree))
        (self.state_dir / "clear-delay").write_text("0\n")

        finished = self.run_phase_change("worker", "Option 2. Go on.")

        self.assertEqual(finished.returncode, 0, finished.stderr)
        sent = self.submitted_prompts()[-1]
        self.assertEqual(sent, "[from orchestrator pane wS:pA9] Option 2. Go on." + REPORT_TO)
        entry = self.lane_entry("lane-a")
        self.assertEqual(entry["session_id"], "s2")
        self.assertEqual(entry["brief"], sent)

    def test_an_agent_outside_every_lane_writes_nothing(self):
        worktree = pathlib.Path(os.path.realpath(self.state_dir)) / "wt"
        worktree.mkdir()
        elsewhere = pathlib.Path(os.path.realpath(self.state_dir)) / "elsewhere"
        elsewhere.mkdir()
        self.add_lane("lane-a", worktree)
        (self.state_dir / "cwd").write_text(str(elsewhere))
        (self.state_dir / "clear-delay").write_text("0\n")

        finished = self.run_phase_change("worker", "/code docs/plans/x/plan.md")

        self.assertEqual(finished.returncode, 0, finished.stderr)
        entry = self.lane_entry("lane-a")
        self.assertEqual(entry["session_id"], "")
        self.assertEqual(entry["brief"], "original brief")

    def test_an_agent_that_reports_no_cwd_writes_nothing_even_when_the_callers_folder_is_a_lane(self):
        worktree = pathlib.Path(os.path.realpath(self.state_dir)) / "wt"
        worktree.mkdir()
        self.add_lane("lane-a", worktree)
        (self.state_dir / "clear-delay").write_text("0\n")

        finished = self.run_phase_change("worker", "/code docs/plans/x/plan.md", cwd=worktree)

        self.assertEqual(finished.returncode, 0, finished.stderr)
        entry = self.lane_entry("lane-a")
        self.assertEqual(entry["session_id"], "")
        self.assertEqual(entry["brief"], "original brief")

    def test_a_lane_update_that_fails_warns_and_still_exits_0_after_the_prompt_went_out(self):
        lanes_stub = self.root / "stub-lanes.py"
        lanes_stub.write_text("import sys\n"
                              "if sys.argv[1] == 'get':\n"
                              "    print('{\"entry\": {\"name\": \"lane-a\"}}')\n"
                              "else:\n"
                              "    sys.exit(1)\n")
        (self.state_dir / "cwd").write_text(str(self.root))
        (self.state_dir / "clear-delay").write_text("0\n")

        finished = self.run_phase_change("worker", "/code docs/plans/x/plan.md", lanes_cli=lanes_stub)

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertIn("herdr-phase-change: lane lane-a not updated", finished.stderr)
        self.assertEqual(self.submitted_prompts(), ["/clear", "/code docs/plans/x/plan.md" + REPORT_TO])

    def test_a_done_pane_gets_clear_and_the_prompt_as_two_submissions_after_the_session_changes(self):
        (self.state_dir / "clear-delay").write_text("2\n")

        finished = self.run_phase_change("worker", "/code docs/plans/x/plan.md")

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(self.submitted_prompts(), ["/clear", "/code docs/plans/x/plan.md" + REPORT_TO])
        self.assertEqual((self.state_dir / "session").read_text().strip(), "s2")
        self.assertIn("--until idle --until done", (self.state_dir / "wait-args").read_text())

    def test_a_slash_command_goes_out_as_given_followed_by_the_report_to_session(self):
        cases = (
            ("plain code", ("/code docs/plans/x/plan.md",), "/code docs/plans/x/plan.md"),
            ("modifier", ("/code +fast plan.md",), "/code +fast plan.md"),
            ("bare code", ("/code",), "/code"),
            ("resume verb", ("/code resume",), "/code resume"),
            ("task text", ("/code fix the flag",), "/code fix the flag"),
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
                self.assertEqual(self.submitted_prompts(), ["/clear", sent + REPORT_TO])

    def test_a_plain_prompt_goes_out_marked_with_the_sending_pane(self):
        (self.state_dir / "clear-delay").write_text("0\n")

        finished = self.run_phase_change("worker", "Option 2. Go on.")

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(self.submitted_prompts(),
                         ["/clear", "[from orchestrator pane wS:pA9] Option 2. Go on." + REPORT_TO])

    def test_a_slash_prompt_goes_out_without_the_pane_prefix(self):
        (self.state_dir / "clear-delay").write_text("0\n")

        finished = self.run_phase_change("worker", "/eng-spec docs/tickets/x.md +fast")

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(self.submitted_prompts(), ["/clear", "/eng-spec docs/tickets/x.md +fast" + REPORT_TO])

    def test_no_resolvable_sending_session_sends_nothing_and_says_why(self):
        stub = self.root / "stub-session-pane.py"
        stub.write_text(STUB_SESSION_PANE_NO_SENDER)
        (self.state_dir / "clear-delay").write_text("0\n")

        finished = self.run_phase_change("worker", "/code docs/plans/x/plan.md", session_pane=stub)

        self.assertEqual(finished.returncode, 1)
        self.assertEqual(self.submitted_prompts(), [])
        self.assertIn("(no session)", finished.stderr)

    def test_a_sender_lookup_that_prints_no_json_sends_nothing_and_says_so(self):
        stub = self.root / "stub-session-pane-silent.py"
        stub.write_text("import json\n"
                        "import sys\n"
                        "\n"
                        "if sys.argv[1] == 'resolve':\n"
                        "    print(json.dumps({'pane_id': sys.argv[2], 'via': 'as-given'}))\n"
                        "    sys.exit(0)\n"
                        "sys.exit(1)\n")
        (self.state_dir / "clear-delay").write_text("0\n")

        finished = self.run_phase_change("worker", "/code docs/plans/x/plan.md", session_pane=stub)

        self.assertEqual(finished.returncode, 1)
        self.assertEqual(self.submitted_prompts(), [])
        self.assertIn("session_pane.py printed no JSON", finished.stderr)

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

    def test_a_session_name_or_a_worktree_path_reaches_the_agents_pane(self):
        worktree = self.state_dir / "wt"
        worktree.mkdir()
        (self.state_dir / "clear-delay").write_text("0\n")
        for label, target in (("session name", "lane-x"), ("worktree path", str(worktree))):
            with self.subTest(case=label):
                self.prompts.unlink(missing_ok=True)
                self.get_targets.unlink(missing_ok=True)
                self.prompt_targets.unlink(missing_ok=True)
                (self.state_dir / "session").write_text("s1\n")

                finished = self.run_phase_change(target, "/code docs/plans/x/plan.md")

                self.assertEqual(finished.returncode, 0, finished.stderr)
                self.assertEqual(set(self.get_targets.read_text().split()), {"wS:pL1"}, label)
                self.assertEqual(set(self.prompt_targets.read_text().split()), {"wS:pL1"}, label)
                self.assertEqual(self.submitted_prompts(), ["/clear", "/code docs/plans/x/plan.md" + REPORT_TO])

    def test_a_directory_with_two_agents_or_a_session_with_no_pane_sends_nothing(self):
        (self.state_dir / "other").mkdir()
        sessions = self.root / ".claude" / "sessions"
        no_pane_row = {"pid": os.getpid(), "sessionId": "s-none", "name": "lane-none"}
        (sessions / f"{os.getpid()}.json").write_text(json.dumps(no_pane_row))
        cases = (
            ("two agents in one directory", str(self.state_dir), "2 claude agents run in"),
            ("session with no pane", "lane-none", "session lane-none has no herdr pane"),
        )
        for label, target, expected_message in cases:
            with self.subTest(case=label):
                finished = self.run_phase_change(target, "/code docs/plans/x/plan.md")

                self.assertEqual(finished.returncode, 1)
                self.assertEqual(self.submitted_prompts(), [], label)
                self.assertIn(expected_message, finished.stderr)

    def test_a_pane_that_is_not_settled_gets_nothing(self):
        for status in ("working", "blocked"):
            with self.subTest(status=status):
                (self.state_dir / "status").write_text(f"{status}\n")

                finished = self.run_phase_change("worker", "/code docs/plans/x/plan.md")

                self.assertEqual(finished.returncode, 1)
                self.assertEqual(self.submitted_prompts(), [])
                self.assertIn(f"worker is {status}", finished.stderr)

    def test_the_script_finds_its_library_when_run_through_a_stow_symlink(self):
        finished = run_through_stow_symlink(HERDR_PHASE_CHANGE, self.root / "symlink-run")

        self.assertEqual(finished.returncode, 1)
        self.assertTrue(finished.stderr.startswith("Clear a settled Claude agent's conversation"), finished.stderr)
        self.assertNotIn("toolkit-tools.bash", finished.stderr)


if __name__ == "__main__":
    unittest.main()
