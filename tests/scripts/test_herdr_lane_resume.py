"""Runs herdr-lane-resume against stub herdr commands and the real lanes.py.

The stubs sit beside a copy of the script, so the script finds herdr-dev and herdr-worktree-prune in its own folder.
Each stub appends what it was called with to one events file, so a test can check the order of the calls.
"""
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

import toolkit_paths
from stubs import copy_sourced_libs, run_through_stow_symlink, write_stub

BIN_DIR = pathlib.Path(__file__).resolve().parents[2] / "scripts" / ".local" / "bin"
HERDR_LANE_RESUME = pathlib.Path(os.environ.get("HERDR_LANE_RESUME", BIN_DIR / "herdr-lane-resume"))
LANES_CLI = pathlib.Path(os.environ.get("HERDR_LANES_CLI", toolkit_paths.TOOLS_DIR / "lanes.py"))
SESSION_PANE = pathlib.Path(os.environ.get("SESSION_PANE_SCRIPT", toolkit_paths.TOOLS_DIR / "session_pane.py"))

BRIEF = "build the thing"
NAME = "repo-fork"
NEW_WORKSPACE = '{"result":{"workspace":{"workspace_id":"wNew"}}}'

# A close stub that exits 1 when told to; otherwise it writes the `closed` marker file and
# empties the agent list unless the agents stay.
CLOSE_BODY = """if [ -e "$STATE_DIR/close-fails" ]; then exit 1; fi
touch "$STATE_DIR/closed"
if [ ! -e "$STATE_DIR/agents-stay" ]; then echo '{"result":{"agents":[]}}' > "$STATE_DIR/agents.json"; fi"""

HERDR_BODY = f"""printf 'herdr %s\\n' "$*" >> "$EVENTS"
case "$1 $2" in
    "worktree open") echo '{NEW_WORKSPACE}' ;;
    "workspace close") {CLOSE_BODY} ;;
esac
exit 0"""

HERDR_API_BODY = f"""case "$1 $2" in
    "agent list") if [ -e "$STATE_DIR/agent-list-fails" ]; then exit 1; fi
        if [ -e "$STATE_DIR/agent-list-fails-after-close" ] && [ -e "$STATE_DIR/closed" ]; then exit 1; fi
        cat "$STATE_DIR/agents.json"; exit 0 ;;
    "workspace list") cat "$STATE_DIR/workspaces.json"; exit 0 ;;
esac
printf 'herdr-api %s\\n' "$*" >> "$EVENTS"
case "$1 $2" in
    "workspace create") echo '{NEW_WORKSPACE}' ;;
    "workspace close") {CLOSE_BODY} ;;
esac
exit 0"""

HERDR_DEV_BODY = """printf 'herdr-dev %s\\n' "$*" >> "$EVENTS"
exit 0"""

PRUNE_BODY = """printf 'prune %s %s lanes=%s\\n' "$PWD" "$*" "$(python3 "$HERDR_LANES_CLI" list)" >> "$EVENTS"
if [ -e "$STATE_DIR/prune-fails" ]; then exit 3; fi
exit 0"""


def agent(pane_id, cwd, status, kind="claude"):
    return {"pane_id": pane_id, "cwd": str(cwd), "agent": kind, "agent_status": status}


# A lanes.py stand-in: `get` reports no entry, every other verb fails.
LANES_LIST_FAILS = """import sys
if sys.argv[1] == "get":
    print('{"entry": null}')
    sys.exit(0)
sys.exit(1)
"""


def workspace(workspace_id, checkout_path):
    return {"workspace_id": workspace_id, "label": NAME, "worktree": {"checkout_path": str(checkout_path)}}


class HerdrLaneResumeTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = pathlib.Path(os.path.realpath(scratch.name))

        self.main_checkout = self.root / "repo"
        self.main_checkout.mkdir()
        self.worktree = self.root / NAME
        self.worktree.mkdir()

        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        self.script = self.bin_dir / "herdr-lane-resume"
        shutil.copy(HERDR_LANE_RESUME, self.script)
        copy_sourced_libs(self.root)
        self.script.chmod(0o755)
        write_stub(self.bin_dir / "herdr", HERDR_BODY)
        write_stub(self.bin_dir / "herdr-api", HERDR_API_BODY)
        write_stub(self.bin_dir / "herdr-dev", HERDR_DEV_BODY)
        write_stub(self.bin_dir / "herdr-worktree-prune", PRUNE_BODY)

        self.state_dir = self.root / "stub-state"
        self.state_dir.mkdir()
        self.state_home = self.root / "state"
        self.events = self.root / "events"
        self.set_agents([])
        self.set_workspaces([])

    def set_agents(self, agents):
        (self.state_dir / "agents.json").write_text(json.dumps({"result": {"agents": agents}}))

    def set_workspaces(self, workspaces):
        (self.state_dir / "workspaces.json").write_text(json.dumps({"result": {"workspaces": workspaces}}))

    def write_state_file(self, name, text):
        stub = self.state_dir / name
        stub.write_text(text)
        return stub

    def env(self, tuios=False):
        env = {key: value for key, value in os.environ.items() if key != "TUIOS_SOCKET"}
        env.update({
            "HOME": str(self.root),
            "PATH": f"{self.bin_dir}:{env['PATH']}",
            "XDG_STATE_HOME": str(self.state_home),
            "HERDR_LANES_CLI": str(LANES_CLI),
            "HERDR_SESSION_PANE": str(SESSION_PANE),
            "HERDR_LANE_CLOSE_WAIT": "0",
            "EVENTS": str(self.events),
            "STATE_DIR": str(self.state_dir),
        })
        if tuios:
            env["TUIOS_SOCKET"] = str(self.root / "tuios.sock")
        return env

    def lanes(self, *args, stdin=""):
        return subprocess.run(["python3", str(LANES_CLI), *args], env=self.env(), input=stdin,
                              capture_output=True, text=True, check=True)

    def add_lane(self, session_id="s1"):
        self.lanes("add", "--name", NAME, "--worktree", str(self.worktree),
                   "--main-checkout", str(self.main_checkout), "--branch", "fork", stdin=BRIEF)
        if session_id:
            self.lanes("set-session", NAME, session_id)

    def lane_names(self):
        return [lane["name"] for lane in json.loads(self.lanes("list").stdout)["lanes"]]

    def run_script(self, *args, tuios=False, extra_env=None, cwd=None):
        env = {**self.env(tuios), **(extra_env or {})}
        return subprocess.run(["bash", str(self.script), *args], env=env, capture_output=True,
                              text=True, timeout=60, cwd=cwd)

    def recorded_events(self):
        if not self.events.exists():
            return []
        return self.events.read_text().splitlines()

    def prune_event(self, lane_names):
        return f"prune {self.main_checkout} --apply lanes={json.dumps({'lanes': lane_names})}"


class ResumeTest(HerdrLaneResumeTest):
    def test_resume_opens_the_workspace_and_runs_herdr_dev_resume(self):
        self.add_lane()

        result = self.run_script(NAME)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.recorded_events(), [
            f"herdr worktree open --cwd {self.main_checkout} --path {self.worktree} --label {NAME} --focus",
            f"herdr-dev --resume {self.worktree} wNew s1 {BRIEF}",
        ])

    def test_resume_under_tuios_creates_and_focuses_the_workspace(self):
        self.add_lane()

        result = self.run_script(NAME, tuios=True)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.recorded_events(), [
            f"herdr-api workspace create --cwd {self.worktree} --label {NAME} --focus",
            "herdr-api workspace focus wNew",
            f"herdr-dev --resume {self.worktree} wNew s1 {BRIEF}",
        ])

    def test_each_stop_exits_1_with_its_message_and_starts_nothing(self):
        def worktree_gone():
            self.add_lane()
            self.worktree.rmdir()

        def no_session_id():
            self.add_lane(session_id="")

        def live_agent():
            self.add_lane()
            self.set_agents([agent("p7", self.worktree / "src", "idle")])

        def open_workspace():
            self.add_lane()
            self.set_workspaces([workspace("wOpen", self.worktree)])

        cases = [
            ("no entry", lambda: None, f"no lane named {NAME}"),
            ("worktree gone", worktree_gone, f"worktree gone; run herdr-lane-resume --close {NAME}"),
            ("no session id", no_session_id, "the fork never reported a session id"),
            ("live agent", live_agent, "lane is live in pane p7"),
            ("open workspace", open_workspace, "workspace wOpen is already open on it; close it, then rerun"),
        ]
        for label, arrange, message in cases:
            with self.subTest(label):
                shutil.rmtree(self.state_home, ignore_errors=True)
                self.worktree.mkdir(exist_ok=True)
                self.set_agents([])
                self.set_workspaces([])
                arrange()

                result = self.run_script(NAME)

                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(message, result.stderr)
                self.assertEqual(self.recorded_events(), [])
                expected_lanes = [] if label == "no entry" else [NAME]
                self.assertEqual(self.lane_names(), expected_lanes)

    def test_label_only_workspace_blocks_resume_under_tuios_only(self):
        self.add_lane()
        self.set_workspaces([{"workspace_id": "wLabel", "label": NAME}])

        blocked = self.run_script(NAME, tuios=True)
        self.assertEqual(blocked.returncode, 1)
        self.assertIn("workspace wLabel is already open on it", blocked.stderr)

        allowed = self.run_script(NAME)
        self.assertEqual(allowed.returncode, 0, allowed.stderr)

    def test_failed_agent_list_stops_resume_and_changes_nothing(self):
        self.add_lane()
        (self.state_dir / "agent-list-fails").write_text("")

        result = self.run_script(NAME)

        self.assertEqual(result.returncode, 1)
        self.assertIn("herdr-api agent list failed", result.stderr)
        self.assertEqual(self.recorded_events(), [])
        self.assertEqual(self.lane_names(), [NAME])

    def test_agent_in_a_sibling_folder_with_a_shared_prefix_does_not_block_resume(self):
        self.add_lane()
        sibling = self.root / f"{NAME}-2"
        sibling.mkdir()
        self.set_agents([agent("p9", sibling, "working")])

        result = self.run_script(NAME)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.recorded_events()), 2)

    def test_agent_cwd_through_a_symlink_blocks_resume(self):
        self.add_lane()
        link = self.root / "link-to-worktree"
        link.symlink_to(self.worktree)
        self.set_agents([agent("p8", link, "idle")])

        result = self.run_script(NAME)

        self.assertEqual(result.returncode, 1)
        self.assertIn("lane is live in pane p8", result.stderr)

    def test_an_agent_with_no_cwd_does_not_count_as_inside_the_lane(self):
        self.add_lane()
        self.set_agents([agent("p6", "", "idle")])

        result = self.run_script(NAME, cwd=self.worktree)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.recorded_events()), 2)

    def test_agent_with_a_null_status_still_blocks_resume(self):
        self.add_lane()
        self.set_agents([agent("p5", self.worktree, None)])

        result = self.run_script(NAME)

        self.assertEqual(result.returncode, 1)
        self.assertIn("lane is live in pane p5", result.stderr)

    def test_agent_that_is_not_claude_blocks_resume(self):
        self.add_lane()
        self.set_agents([agent("p4", self.worktree, "idle", kind="codex")])

        result = self.run_script(NAME)

        self.assertEqual(result.returncode, 1)
        self.assertIn("lane is live in pane p4", result.stderr)
        self.assertEqual(self.recorded_events(), [])

    def test_failing_lanes_cli_stops_with_its_own_message(self):
        failing_get = self.write_state_file("failing_get.py", "import sys\nsys.exit(1)\n")
        failing_list = self.write_state_file("failing_list.py", LANES_LIST_FAILS)
        cases = [
            ("get fails", failing_get, f"lanes.py get {NAME} failed"),
            ("list fails", failing_list, "lanes.py list failed"),
        ]
        for label, cli, message in cases:
            with self.subTest(label):
                result = self.run_script(NAME, extra_env={"HERDR_LANES_CLI": str(cli)})

                self.assertEqual(result.returncode, 1)
                self.assertIn(message, result.stderr)
                self.assertNotIn("no lane named", result.stderr)
                self.assertEqual(self.recorded_events(), [])

    def test_unknown_name_lists_the_known_lanes(self):
        self.add_lane()

        result = self.run_script("other")

        self.assertEqual(result.returncode, 1)
        self.assertIn(f"known lanes: {NAME}", result.stderr)


class CloseTest(HerdrLaneResumeTest):
    def arrange_open_lane(self, status="idle"):
        self.add_lane()
        self.set_agents([agent("p1", self.worktree, status)])
        self.set_workspaces([workspace("wX", self.worktree)])

    def test_close_closes_the_workspace_then_removes_the_entry_then_prunes(self):
        self.arrange_open_lane()

        result = self.run_script("--close", NAME)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.recorded_events(), ["herdr workspace close wX", self.prune_event([])])
        self.assertEqual(self.lane_names(), [])

    def test_close_under_tuios_closes_through_herdr_api(self):
        self.arrange_open_lane()

        result = self.run_script("--close", NAME, tuios=True)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.recorded_events(), ["herdr-api workspace close wX", self.prune_event([])])

    def test_label_only_workspace_is_closed_under_tuios_only(self):
        self.add_lane()
        self.set_workspaces([{"workspace_id": "wX", "label": NAME}])

        tuios_result = self.run_script("--close", NAME, tuios=True)
        self.assertEqual(tuios_result.returncode, 0, tuios_result.stderr)
        self.assertEqual(self.recorded_events(), ["herdr-api workspace close wX", self.prune_event([])])

        self.events.unlink()
        self.add_lane()
        plain_result = self.run_script("--close", NAME)
        self.assertEqual(plain_result.returncode, 0, plain_result.stderr)
        self.assertEqual(self.recorded_events(), [self.prune_event([])])

    def test_failed_agent_list_stops_close_and_changes_nothing(self):
        self.arrange_open_lane()
        (self.state_dir / "agent-list-fails").write_text("")

        result = self.run_script("--close", NAME)

        self.assertEqual(result.returncode, 1)
        self.assertIn("herdr-api agent list failed", result.stderr)
        self.assertEqual(self.recorded_events(), [])
        self.assertEqual(self.lane_names(), [NAME])

    def test_workspace_with_a_null_label_is_still_closed(self):
        self.add_lane()
        self.set_workspaces([{"workspace_id": "wX", "label": None,
                              "worktree": {"checkout_path": str(self.worktree)}}])

        result = self.run_script("--close", NAME)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.recorded_events(), ["herdr workspace close wX", self.prune_event([])])

    def test_unexpected_list_shapes_stop_the_close_before_anything_changes(self):
        shapes = [{"result": {}}, {"result": {"agents": None, "workspaces": None}}]
        for shape in shapes:
            for listing in ("agents", "workspaces"):
                with self.subTest(shape=shape, listing=listing):
                    shutil.rmtree(self.state_home, ignore_errors=True)
                    self.arrange_open_lane()
                    (self.state_dir / f"{listing}.json").write_text(json.dumps(shape))

                    result = self.run_script("--close", NAME)

                    self.assertEqual(result.returncode, 1)
                    expected = "printed no agents list" if listing == "agents" else "unexpected shape"
                    self.assertIn(expected, result.stderr)
                    self.assertEqual(self.recorded_events(), [])
                    self.assertEqual(self.lane_names(), [NAME])

    def test_failed_poll_after_the_close_keeps_the_entry(self):
        self.arrange_open_lane()
        (self.state_dir / "agent-list-fails-after-close").write_text("")

        result = self.run_script("--close", NAME)

        self.assertEqual(result.returncode, 1)
        self.assertIn("the workspaces are already closed and the lane entry is kept", result.stderr)
        self.assertEqual(self.recorded_events(), ["herdr workspace close wX"])
        self.assertEqual(self.lane_names(), [NAME])

    def test_working_agent_listed_before_an_idle_one_still_refuses(self):
        # Racy by nature: an awk that exits at its first match SIGPIPEs agents_in only when it exits
        # before the last printf. Many idle rows after the working one make that likely, not certain.
        self.add_lane()
        idle_agents = [agent(f"p{n}", self.worktree, "idle") for n in range(2, 12)]
        self.set_agents([agent("p1", self.worktree, "working"), *idle_agents])

        result = self.run_script("--close", NAME)

        self.assertEqual(result.returncode, 1)
        self.assertIn("has a working agent in pane p1", result.stderr)

    def test_non_claude_working_agent_does_not_refuse_close(self):
        self.arrange_open_lane()
        self.set_agents([agent("p1", self.worktree, "working", kind="codex")])

        result = self.run_script("--close", NAME)

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_poll_waits_for_a_non_claude_agent_and_warns_when_it_stays(self):
        self.arrange_open_lane()
        self.set_agents([agent("p1", self.worktree, "idle", kind="codex")])
        (self.state_dir / "agents-stay").write_text("")

        result = self.run_script("--close", NAME)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"an agent still runs in {self.worktree}; the prune will keep it", result.stderr)

    def test_a_bad_wait_value_stops_the_close_before_anything_changes(self):
        self.arrange_open_lane()

        result = self.run_script("--close", NAME, extra_env={"HERDR_LANE_CLOSE_WAIT": "abc"})

        self.assertEqual(result.returncode, 1)
        self.assertIn("must be a whole number of seconds", result.stderr)
        self.assertEqual(self.recorded_events(), [])
        self.assertEqual(self.lane_names(), [NAME])

    def test_working_agent_in_a_sibling_folder_with_a_shared_prefix_does_not_refuse(self):
        self.arrange_open_lane()
        sibling = self.root / f"{NAME}-2"
        sibling.mkdir()
        self.set_agents([agent("p1", sibling, "working")])

        result = self.run_script("--close", NAME)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.recorded_events(), ["herdr workspace close wX", self.prune_event([])])

    def test_workspace_checkout_through_a_symlink_is_closed(self):
        self.add_lane()
        link = self.root / "link-to-worktree"
        link.symlink_to(self.worktree)
        self.set_workspaces([workspace("wX", link)])

        result = self.run_script("--close", NAME)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.recorded_events(), ["herdr workspace close wX", self.prune_event([])])

    def test_a_leading_zero_wait_is_read_as_decimal(self):
        # Bash reads "09" as bad octal and ends the poll loop at once with a warning; the agents
        # leave at once, so no sleep and no stderr.
        self.arrange_open_lane()

        result = self.run_script("--close", NAME, extra_env={"HERDR_LANE_CLOSE_WAIT": "09"})

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(self.recorded_events(), ["herdr workspace close wX", self.prune_event([])])

    def test_prune_exit_code_is_the_script_exit_code(self):
        self.arrange_open_lane()
        (self.state_dir / "prune-fails").write_text("")

        result = self.run_script("--close", NAME)

        self.assertEqual(result.returncode, 3)
        self.assertEqual(self.lane_names(), [])

    def test_gone_main_checkout_removes_the_entry_and_runs_no_prune(self):
        self.add_lane()
        self.main_checkout.rmdir()

        result = self.run_script("--close", NAME)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"main checkout {self.main_checkout} is gone", result.stdout)
        self.assertEqual(self.recorded_events(), [])
        self.assertEqual(self.lane_names(), [])

    def test_working_agent_refuses_and_changes_nothing(self):
        self.arrange_open_lane(status="working")

        result = self.run_script("--close", NAME)

        self.assertEqual(result.returncode, 1)
        self.assertIn(f"lane {NAME} has a working agent in pane p1; wait for it to finish, then rerun",
                      result.stderr)
        self.assertEqual(self.recorded_events(), [])
        self.assertEqual(self.lane_names(), [NAME])

    def test_failed_workspace_close_keeps_the_entry_and_prunes_nothing(self):
        self.arrange_open_lane()
        (self.state_dir / "close-fails").write_text("")

        result = self.run_script("--close", NAME)

        self.assertEqual(result.returncode, 1)
        self.assertIn("wX", result.stderr)
        self.assertEqual(self.recorded_events(), ["herdr workspace close wX"])
        self.assertEqual(self.lane_names(), [NAME])

    def test_agent_that_never_leaves_warns_then_removes_and_prunes(self):
        self.arrange_open_lane()
        (self.state_dir / "agents-stay").write_text("")

        result = self.run_script("--close", NAME)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"an agent still runs in {self.worktree}; the prune will keep it", result.stderr)
        self.assertEqual(self.recorded_events(), ["herdr workspace close wX", self.prune_event([])])
        self.assertEqual(self.lane_names(), [])

    def test_no_entry_exits_1_and_prunes_nothing(self):
        result = self.run_script("--close", NAME)

        self.assertEqual(result.returncode, 1)
        self.assertIn(f"no lane named {NAME}", result.stderr)
        self.assertEqual(self.recorded_events(), [])

    def test_gone_worktree_still_removes_the_entry_and_prunes(self):
        self.add_lane()
        self.worktree.rmdir()

        result = self.run_script("--close", NAME)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("already gone", result.stderr)
        self.assertEqual(self.recorded_events(), [self.prune_event([])])
        self.assertEqual(self.lane_names(), [])

    def test_gone_worktree_is_closed_through_a_dot_dot_path(self):
        self.add_lane()
        self.worktree.rmdir()

        result = self.run_script("--close", f"../{NAME}", cwd=self.main_checkout)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("no lane file entry", result.stderr)
        self.assertEqual(self.lane_names(), [])

    def test_the_script_finds_its_library_when_run_through_a_stow_symlink(self):
        finished = run_through_stow_symlink(HERDR_LANE_RESUME, self.root / "symlink-run")

        self.assertEqual(finished.returncode, 1)
        self.assertTrue(finished.stderr.startswith("Reopen a dead lane from its lane file"), finished.stderr)
        self.assertNotIn("toolkit-tools.bash", finished.stderr)


GIT_ENV = {
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
}


class EntrylessCloseTest(HerdrLaneResumeTest):
    """A real bare origin, a main checkout on master and a linked worktree on `fork`, one commit ahead."""

    def setUp(self):
        super().setUp()
        shutil.rmtree(self.main_checkout)
        shutil.rmtree(self.worktree)
        self.fake_workspaces = []

        origin = self.root / "origin.git"
        self.git(self.root, "init", "--bare", "-b", "master", str(origin))
        self.git(self.root, "init", "-b", "master", str(self.main_checkout))
        (self.main_checkout / "README").write_text("start\n")
        self.git(self.main_checkout, "add", "README")
        self.git(self.main_checkout, "commit", "-m", "start")
        self.git(self.main_checkout, "remote", "add", "origin", str(origin))
        self.git(self.main_checkout, "push", "-u", "origin", "master")
        self.git(self.main_checkout, "remote", "set-head", "origin", "master")

        self.git(self.main_checkout, "worktree", "add", str(self.worktree), "-b", "fork")
        (self.worktree / "feature").write_text("work\n")
        self.git(self.worktree, "add", "feature")
        self.git(self.worktree, "commit", "-m", "feature")

    def env(self, tuios=False):
        env = super().env(tuios)
        env.update(GIT_ENV)
        return env

    def git(self, folder, *args):
        return subprocess.run(["git", "-C", str(folder), *args], env=self.env(),
                              capture_output=True, text=True, check=True)

    def merge_fork(self):
        self.git(self.main_checkout, "merge", "--ff-only", "fork")
        self.git(self.main_checkout, "push", "origin", "master")

    def workspace_on(self, path, workspace_id="wX", linked=True):
        self.fake_workspaces.append({
            "workspace_id": workspace_id,
            "label": pathlib.Path(path).name,
            "worktree": {"checkout_path": str(path), "is_linked_worktree": linked},
        })
        self.set_workspaces(self.fake_workspaces)

    def assert_refused_changing_nothing(self, result, message):
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(message, result.stderr)
        message_lines = [line for line in result.stderr.splitlines() if message in line]
        self.assertTrue(message_lines[0].startswith("herdr-lane-resume: "), message_lines[0])
        self.assertEqual(self.recorded_events(), [])
        self.assertTrue(self.worktree.is_dir())
        self.git(self.main_checkout, "rev-parse", "--verify", "fork")
        registered = self.git(self.main_checkout, "worktree", "list", "--porcelain").stdout
        self.assertIn(f"worktree {self.worktree}", registered)

    def test_entryless_close_by_name_closes_the_merged_workspace_and_prunes(self):
        self.merge_fork()
        self.workspace_on(self.worktree)

        result = self.run_script("--close", NAME)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.recorded_events(), ["herdr workspace close wX", self.prune_event([])])

    def test_entryless_close_by_path_closes_the_merged_workspace_and_prunes(self):
        self.merge_fork()
        self.workspace_on(self.worktree)

        result = self.run_script("--close", str(self.worktree))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.recorded_events(), ["herdr workspace close wX", self.prune_event([])])

    def test_entryless_close_of_an_unmerged_branch_refuses_before_closing(self):
        self.workspace_on(self.worktree)

        result = self.run_script("--close", NAME)

        self.assert_refused_changing_nothing(result, "branch fork is not merged into origin/master")

    def test_entryless_close_refuses_a_working_agent(self):
        self.merge_fork()
        self.workspace_on(self.worktree)
        self.set_agents([agent("p1", self.worktree, "working")])

        result = self.run_script("--close", NAME)

        self.assert_refused_changing_nothing(result, "has a working agent in pane p1")

    def test_entryless_close_refuses_the_main_checkout(self):
        self.merge_fork()
        self.workspace_on(self.main_checkout, linked=False)
        cases = [
            ("by name", self.main_checkout.name, "is the main checkout"),
            ("by path", str(self.main_checkout), "is not a linked worktree"),
        ]
        for label, target, message in cases:
            with self.subTest(label):
                result = self.run_script("--close", target)

                self.assert_refused_changing_nothing(result, message)

    def test_entryless_close_refuses_a_worktree_of_a_separate_git_dir_repo(self):
        separate = self.root / "separate"
        self.git(self.root, "init", "-b", "master", "--separate-git-dir", str(self.root / "separate.git"),
                 str(separate))
        (separate / "README").write_text("start\n")
        self.git(separate, "add", "README")
        self.git(separate, "commit", "-m", "start")
        separate_worktree = self.root / "separate-linked"
        self.git(separate, "worktree", "add", str(separate_worktree), "-b", "other")
        self.workspace_on(separate_worktree)

        result = self.run_script("--close", str(separate_worktree))

        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("is bare, missing or not a work tree", result.stderr)
        self.assertEqual(self.recorded_events(), [])
        self.assertTrue(separate_worktree.is_dir())

    def test_entryless_close_with_two_matching_workspaces_lists_both(self):
        self.merge_fork()
        other = self.root / "elsewhere" / NAME
        self.workspace_on(self.worktree, "wA")
        self.workspace_on(other, "wB")

        result = self.run_script("--close", NAME)

        self.assert_refused_changing_nothing(result, str(self.worktree))
        self.assertIn(str(other), result.stderr)

    def test_entryless_close_by_name_under_tuios_refuses(self):
        self.merge_fork()
        self.workspace_on(self.worktree)

        result = self.run_script("--close", NAME, tuios=True)

        self.assert_refused_changing_nothing(result, "under tuios a name cannot be matched")
        self.assertIn("known lanes: none", result.stderr)

    def test_entryless_close_by_name_under_tuios_lists_the_known_lanes(self):
        self.merge_fork()
        self.workspace_on(self.worktree)
        self.lanes("add", "--name", "other-lane", "--worktree", str(self.root / "other-lane"),
                   "--main-checkout", str(self.main_checkout), "--branch", "other", stdin=BRIEF)

        result = self.run_script("--close", NAME, tuios=True)

        self.assert_refused_changing_nothing(result, "under tuios a name cannot be matched")
        self.assertIn("known lanes:", result.stderr)
        self.assertIn("other-lane", result.stderr)

    def test_entryless_close_of_a_worktree_of_a_bare_repo_refuses(self):
        bare = self.root / "repo.git"
        self.git(self.root, "clone", "--bare", str(self.root / "origin.git"), str(bare))
        bare_worktree = self.root / "bare-fork"
        self.git(bare, "worktree", "add", str(bare_worktree), "-b", "fork2")
        self.workspace_on(bare_worktree)

        result = self.run_script("--close", str(bare_worktree))

        self.assert_refused_changing_nothing(result, "is bare, missing or not a work tree")

    def test_entryless_failed_workspace_close_prunes_nothing(self):
        self.merge_fork()
        self.workspace_on(self.worktree)
        (self.state_dir / "close-fails").write_text("")

        result = self.run_script("--close", NAME)

        self.assertEqual(result.returncode, 1)
        self.assertIn("could not close workspace wX; nothing was pruned", result.stderr)
        self.assertEqual(self.recorded_events(), ["herdr workspace close wX"])

    def test_entryless_close_of_a_merged_lane_with_an_uncommitted_file_refuses_before_closing(self):
        self.merge_fork()
        self.workspace_on(self.worktree)
        (self.worktree / "scratch").write_text("not committed\n")

        result = self.run_script("--close", NAME)

        self.assert_refused_changing_nothing(result, f"{self.worktree} has uncommitted changes; nothing changed")

    def test_entryless_prune_exit_code_is_the_script_exit_code(self):
        self.merge_fork()
        self.workspace_on(self.worktree)
        (self.state_dir / "prune-fails").write_text("")

        result = self.run_script("--close", NAME)

        self.assertEqual(result.returncode, 3)
        self.assertEqual(self.recorded_events(), ["herdr workspace close wX", self.prune_event([])])

    def test_entryless_close_ignores_an_idle_claude_and_a_working_other_agent(self):
        self.merge_fork()
        cases = [
            ("idle claude", agent("p1", self.worktree, "idle")),
            ("working other agent", agent("p1", self.worktree, "working", kind="other")),
        ]
        for label, listed_agent in cases:
            with self.subTest(label):
                self.workspace_on(self.worktree)
                self.set_agents([listed_agent])

                result = self.run_script("--close", NAME)

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.recorded_events(), ["herdr workspace close wX", self.prune_event([])])
                self.events.unlink()
                self.fake_workspaces.clear()

    def test_entryless_close_by_path_with_no_workspace_refuses(self):
        self.merge_fork()

        result = self.run_script("--close", str(self.worktree))

        self.assert_refused_changing_nothing(result, f"no herdr workspace is open on {self.worktree}")

    def test_entryless_close_of_a_detached_head_refuses(self):
        self.merge_fork()
        self.git(self.worktree, "checkout", "--detach")
        self.workspace_on(self.worktree)

        result = self.run_script("--close", str(self.worktree))

        self.assert_refused_changing_nothing(result, "detached HEAD")

    def test_two_workspaces_on_one_linked_worktree_count_as_one_match_by_name(self):
        self.merge_fork()
        self.workspace_on(self.worktree, "wA")
        self.workspace_on(self.worktree, "wB")

        result = self.run_script("--close", NAME)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.recorded_events(),
                         ["herdr workspace close wA", "herdr workspace close wB", self.prune_event([])])

    def test_one_linked_match_and_one_plain_match_close_only_the_linked_workspace(self):
        self.merge_fork()
        self.workspace_on(self.worktree, "wA")
        self.workspace_on(self.root / "elsewhere" / NAME, "wB", linked=False)

        result = self.run_script("--close", NAME)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.recorded_events(), ["herdr workspace close wA", self.prune_event([])])

    def test_a_stale_origin_ref_is_fetched_before_the_merge_check(self):
        # Pushing to the URL, not the remote name, leaves the main checkout's origin/master stale.
        self.git(self.worktree, "push", str(self.root / "origin.git"), "fork:master")
        self.workspace_on(self.worktree)

        result = self.run_script("--close", NAME)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.recorded_events(), ["herdr workspace close wX", self.prune_event([])])

    def test_branch_is_merged_refusals_change_nothing(self):
        self.merge_fork()
        self.workspace_on(self.worktree)
        # Main checkout leaves master so the worktree can switch onto the default branch.
        self.git(self.main_checkout, "checkout", "-b", "other")
        self.git(self.worktree, "checkout", "master")
        on_default = self.run_script("--close", str(self.worktree))
        self.assert_refused_changing_nothing(on_default, "is on the default branch master")

        self.git(self.worktree, "checkout", "fork")
        self.git(self.main_checkout, "remote", "set-url", "origin", str(self.root / "gone.git"))
        fetch_fails = self.run_script("--close", str(self.worktree))
        self.assert_refused_changing_nothing(fetch_fails, "could not fetch origin/master")

        self.git(self.main_checkout, "remote", "set-head", "origin", "--delete")
        no_head = self.run_script("--close", str(self.worktree))
        self.assert_refused_changing_nothing(no_head, "has no refs/remotes/origin/HEAD")

    def test_a_merge_check_that_cannot_run_refuses_and_changes_nothing(self):
        self.workspace_on(self.worktree)
        # A merge-base that exits 128 is neither "merged" (0) nor "not merged" (1).
        real_git = shutil.which("git")
        write_stub(self.bin_dir / "git", f'[ "$3" = merge-base ] && exit 128\nexec {real_git} "$@"')

        result = self.run_script("--close", str(self.worktree))

        self.assert_refused_changing_nothing(result, "could not check whether branch fork is merged")

    def test_a_path_that_is_not_a_folder_refuses(self):
        result = self.run_script("--close", str(self.root / "missing" / "x"))

        self.assert_refused_changing_nothing(result, "no lane file entry and no folder at")

    def test_a_relative_path_that_is_gone_is_named_by_its_absolute_path(self):
        result = self.run_script("--close", "missing/x", cwd=self.root)

        self.assert_refused_changing_nothing(result, f"no lane file entry and no folder at {self.root}/missing/x")

    def test_an_entry_whose_worktree_differs_from_the_path_falls_to_the_entryless_close(self):
        self.add_lane()
        subdir = self.worktree / "subdir"
        subdir.mkdir()
        self.workspace_on(self.worktree)

        result = self.run_script("--close", str(subdir))

        self.assert_refused_changing_nothing(result, f"no herdr workspace is open on {subdir}")
        self.assertEqual(self.lane_names(), [NAME])

    def test_close_by_path_with_an_entry_uses_the_entry(self):
        # `fork` stays unmerged: the entry-less path would refuse, so a close proves the entry path.
        self.add_lane()
        self.workspace_on(self.worktree)

        result = self.run_script("--close", str(self.worktree))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.recorded_events(), ["herdr workspace close wX", self.prune_event([])])
        self.assertEqual(self.lane_names(), [])


if __name__ == "__main__":
    unittest.main()
