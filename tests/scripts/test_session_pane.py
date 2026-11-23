"""Runs session_pane.py sender against a registry folder of live session rows and a stub herdr-api.

Checks the name it prints and the exit code for each way the sender is, or is not, found.
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths
from stubs import write_stub

SESSION_PANE = pathlib.Path(os.environ.get("SESSION_PANE_SCRIPT", toolkit_paths.TOOLS_DIR / "session_pane.py"))
PANE_WITH_SESSION = '{"result":{"pane":{"agent":"claude","agent_session":{"value":"s-pane"}}}}'
PANE_WITHOUT_AGENT = '{"result":{"pane":{"agent":null}}}'


class SessionPaneTestCase(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = pathlib.Path(os.path.realpath(scratch.name))
        self.config_dir = self.root / "claude"
        (self.config_dir / "sessions").mkdir(parents=True)
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()

    def register_session(self, session_id, name):
        """A live registry row: the pid is this test process's, which is alive."""
        row = {"pid": os.getpid(), "sessionId": session_id, "name": name}
        (self.config_dir / "sessions" / f"{os.getpid()}.json").write_text(json.dumps(row))


class SessionPaneSenderTest(SessionPaneTestCase):
    def stub_pane_current(self, command):
        write_stub(self.bin_dir / "herdr-api", f'case "$1 $2" in\n    "pane current") {command} ;;\nesac')

    def run_sender(self, env_session_id=None, restrict_path=False):
        env = {key: value for key, value in os.environ.items() if key != "CLAUDE_CODE_SESSION_ID"}
        env["CLAUDE_CONFIG_DIR"] = str(self.config_dir)
        if restrict_path:
            # Only the empty bin dir and python3's own folder, so herdr-api cannot be found.
            env["PATH"] = f"{self.bin_dir}:{pathlib.Path(sys.executable).parent}"
        else:
            env["PATH"] = f"{self.bin_dir}:{env['PATH']}"
        if env_session_id is not None:
            env["CLAUDE_CODE_SESSION_ID"] = env_session_id
        return subprocess.run(["python3", str(SESSION_PANE), "sender"], env=env, capture_output=True, text=True)

    def test_the_name_comes_from_the_session_id_in_the_environment(self):
        self.register_session("s-env", "orchestrator")
        self.stub_pane_current("exit 1")

        finished = self.run_sender(env_session_id="s-env")

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(json.loads(finished.stdout), {"name": "orchestrator"})

    def test_with_no_environment_id_the_name_comes_from_the_current_panes_session(self):
        self.register_session("s-pane", "pane-orchestrator")
        self.stub_pane_current(f"echo '{PANE_WITH_SESSION}'")

        finished = self.run_sender()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(json.loads(finished.stdout), {"name": "pane-orchestrator"})

    def test_no_source_giving_a_name_exits_1_with_a_reason_on_stdout(self):
        cases = (
            ("pane has no agent", PANE_WITHOUT_AGENT),
            ("pane session has no live named row", PANE_WITH_SESSION),
        )
        for label, pane in cases:
            with self.subTest(case=label):
                self.stub_pane_current(f"echo '{pane}'")

                finished = self.run_sender()

                self.assertEqual(finished.returncode, 1, finished.stderr)
                result = json.loads(finished.stdout)
                self.assertIsNone(result["name"])
                self.assertTrue(result["reason"], label)

    def test_an_environment_id_with_no_live_named_row_falls_through_to_the_pane_lookup(self):
        self.register_session("s-pane", "pane-orchestrator")
        self.stub_pane_current(f"echo '{PANE_WITH_SESSION}'")

        finished = self.run_sender(env_session_id="unknown")

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(json.loads(finished.stdout), {"name": "pane-orchestrator"})

    def test_a_failed_herdr_api_call_exits_2_and_the_reason_names_the_call(self):
        cases = (
            ("non-zero exit", "exit 1", True),
            ("not JSON", "echo not-json", True),
            ("JSON but not an object", "echo '[1]'", True),
            ("herdr-api missing", None, False),
        )
        for label, command, stub_present in cases:
            with self.subTest(case=label):
                (self.bin_dir / "herdr-api").unlink(missing_ok=True)
                if stub_present:
                    self.stub_pane_current(command)

                finished = self.run_sender(restrict_path=not stub_present)

                self.assertEqual(finished.returncode, 2, finished.stderr)
                result = json.loads(finished.stdout)
                self.assertIsNone(result["name"])
                self.assertIn("herdr-api pane current", result["reason"])


AGENT_LIST = ('{"result":{"agents":['
              '{"agent":"claude","pane_id":"w1:p1","cwd":"%(wt)s","agent_session":{"value":"s-one"}},'
              '{"agent":"claude","pane_id":"w1:p2","cwd":"%(wt)s/deeper","agent_session":{"value":"s-two"}},'
              '{"agent":"claude","pane_id":"w1:p3","cwd":"%(solo)s","agent_session":{"value":"s-three"}},'
              '{"agent":"shell","pane_id":"w1:p4","cwd":"%(solo)s","agent_session":{"value":"s-four"}}]}}')


class SessionPaneResolveTest(SessionPaneTestCase):
    def setUp(self):
        super().setUp()
        self.shared = self.root / "shared"
        (self.shared / "deeper").mkdir(parents=True)
        self.solo = self.root / "solo"
        self.solo.mkdir()
        listing = AGENT_LIST % {"wt": self.shared, "solo": self.solo}
        write_stub(self.bin_dir / "herdr-api", f'case "$1 $2" in\n    "agent list") echo \'{listing}\' ;;\nesac')

    def run_resolve(self, arg):
        env = dict(os.environ, CLAUDE_CONFIG_DIR=str(self.config_dir), PATH=f"{self.bin_dir}:{os.environ['PATH']}")
        return subprocess.run(["python3", str(SESSION_PANE), "resolve", arg], env=env, capture_output=True,
                              text=True)

    def test_a_session_name_resolves_to_the_pane_holding_its_session(self):
        self.register_session("s-three", "lane-three")

        finished = self.run_resolve("lane-three")

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(json.loads(finished.stdout), {"pane_id": "w1:p3", "via": "session"})

    def test_a_directory_resolves_to_the_one_claude_agent_inside_it(self):
        finished = self.run_resolve(str(self.solo))

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(json.loads(finished.stdout), {"pane_id": "w1:p3", "via": "path"})

    def test_a_directory_with_two_agents_exits_1_listing_both(self):
        finished = self.run_resolve(str(self.shared))

        self.assertEqual(finished.returncode, 1)
        self.assertIn(f"w1:p1 {self.shared}\n", finished.stderr)
        self.assertIn(f"w1:p2 {self.shared}/deeper\n", finished.stderr)

    def test_a_directory_with_no_claude_agent_exits_1(self):
        empty = self.root / "empty"
        empty.mkdir()

        finished = self.run_resolve(str(empty))

        self.assertEqual(finished.returncode, 1)
        self.assertIn("no claude agent runs in", finished.stderr)

    def test_a_directory_wins_over_a_session_of_the_same_name(self):
        self.register_session("s-one", str(self.solo))

        finished = self.run_resolve(str(self.solo))

        self.assertEqual(json.loads(finished.stdout)["via"], "path")

    def test_a_session_with_no_pane_exits_1_naming_it(self):
        self.register_session("s-gone", "lane-gone")

        finished = self.run_resolve("lane-gone")

        self.assertEqual(finished.returncode, 1)
        self.assertIn("session lane-gone has no herdr pane", finished.stderr)

    def test_an_unknown_argument_is_returned_as_given_without_listing_agents(self):
        write_stub(self.bin_dir / "herdr-api", "exit 1")

        finished = self.run_resolve("w1:p9")

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(json.loads(finished.stdout), {"pane_id": "w1:p9", "via": "as-given"})

    def test_a_failed_agent_list_exits_2_naming_the_call(self):
        write_stub(self.bin_dir / "herdr-api", "exit 1")

        finished = self.run_resolve(str(self.solo))

        self.assertEqual(finished.returncode, 2)
        self.assertIn("herdr-api agent list", finished.stderr)


if __name__ == "__main__":
    unittest.main()
