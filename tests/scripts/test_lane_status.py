"""Runs lane_status.py against stub herdr-api, df and du commands, a temp lane folder and a temp scratch root."""
import importlib.util
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import toolkit_paths
from stubs import write_stub

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import lane_entries

LANE_STATUS = pathlib.Path(os.environ.get("LANE_STATUS_SCRIPT", toolkit_paths.TOOLS_DIR / "lane_status.py"))
ROOMY_DF = "Filesystem 1024-blocks Used Available Capacity Mounted on\n/dev/x 999999999 1 99999999 1% /"
TIGHT_DF = "Filesystem 1024-blocks Used Available Capacity Mounted on\n/dev/x 999999999 1 100 99% /"
# A Bash call sent to the background, the result that hands back its task id, the notification when it ends, and the
# closing text of a turn that stops to wait on it.
BACKGROUND_SHELL_CALL = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "make bench", "run_in_background": True}}]}}
BACKGROUND_SHELL = {"type": "user", "toolUseResult": {"backgroundTaskId": "b1"}, "message": {"content": [
    {"type": "tool_result", "tool_use_id": "t1", "content": "Command running in background with ID: b1"}]}}
SHELL_NOTIFICATION = {"type": "user", "message": {"content": (
    "<task-notification><task-id>b1</task-id><tool-use-id>t1</tool-use-id><status>completed</status>"
    "<result>done</result></task-notification>")}}
BACKGROUND_RUN = [BACKGROUND_SHELL_CALL, BACKGROUND_SHELL]
CLOSING_TEXT = {"type": "assistant", "message": {"content": [
    {"type": "text", "text": "The bench runs in the background; I will report when it ends."}]}}


class LaneStatusTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = pathlib.Path(os.path.realpath(scratch.name))
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        self.state_home = self.root / "state"
        self.temp_base = self.root / "tmp"
        self.temp_base.mkdir()
        self.worktree = self.root / "wt-one"
        self.worktree.mkdir()
        patched = mock.patch.dict(os.environ, {"XDG_STATE_HOME": str(self.state_home)})
        patched.start()
        self.addCleanup(patched.stop)
        self.stub_agents([])
        self.stub_df(ROOMY_DF)
        self.stub_du("100")

    def stub_agents(self, agents):
        reply = json.dumps({"result": {"agents": agents}})
        write_stub(self.bin_dir / "herdr-api", f"echo '{reply}'")

    def stub_df(self, text):
        write_stub(self.bin_dir / "df", f"cat <<'EOF'\n{text}\nEOF")

    def stub_du(self, kilobytes):
        write_stub(self.bin_dir / "du", f"printf '{kilobytes}\\t%s\\n' \"$2\"")

    def add_lane(self, name="one", worktree=None):
        worktree = worktree or self.worktree
        lane_entries.add_entry(name, str(worktree), str(self.root), f"branch-{name}", "brief", "")

    def status_env(self, **overrides):
        env = {key: value for key, value in os.environ.items() if not key.startswith("LANE_STATUS_")}
        env["PATH"] = f"{self.bin_dir}:{env['PATH']}"
        env["CLAUDE_CODE_TMPDIR"] = str(self.temp_base)
        env["CLAUDE_CONFIG_DIR"] = str(self.root / "config")
        env.update(overrides)
        return env

    def run_status(self, *arguments, **env_overrides):
        env = self.status_env(**{"LANE_STATUS_MIN_MEMORY_GB": "0", **env_overrides})
        return subprocess.run(["python3", str(LANE_STATUS), *arguments], env=env, capture_output=True, text=True)

    def agent(self, status, cwd=None):
        return {"agent": "claude", "agent_status": status, "cwd": str(cwd or self.worktree), "pane_id": "p1"}

    def agent_with_transcript(self, status, records):
        """An agent whose session transcript holds `records`, one JSON object per line."""
        session_id = "s-one"
        transcript = self.root / "config" / "projects" / "-wt-one" / f"{session_id}.jsonl"
        transcript.parent.mkdir(parents=True, exist_ok=True)
        transcript.write_text("".join(json.dumps(record) + "\n" for record in records))
        agent = self.agent(status)
        agent["agent_session"] = {"value": session_id}
        return agent

    def test_an_idle_agent_with_an_unreported_background_shell_is_waiting(self):
        self.add_lane()
        self.stub_agents([self.agent_with_transcript("idle", [*BACKGROUND_RUN, CLOSING_TEXT])])

        finished = self.run_status()

        self.assertEqual(finished.stdout, "one: waiting on 1 background job(s)\n", finished.stderr)

    def test_an_idle_agent_whose_background_shell_reported_is_idle(self):
        self.add_lane()
        self.stub_agents([self.agent_with_transcript("idle", [*BACKGROUND_RUN, SHELL_NOTIFICATION, CLOSING_TEXT])])

        finished = self.run_status()

        self.assertEqual(finished.stdout, "one: idle\n", finished.stderr)

    def test_an_agent_whose_transcript_ends_on_an_api_error_is_dead(self):
        self.add_lane()
        cases = [("Please run /login. API Error: 401", "login expired"), ("API Error: 500 overloaded", "api error")]
        for error_text, reason in cases:
            with self.subTest(reason=reason):
                error_record = {"type": "assistant", "isApiErrorMessage": True,
                                "message": {"content": [{"type": "text", "text": error_text}]}}
                self.stub_agents([self.agent_with_transcript("idle", [*BACKGROUND_RUN, error_record])])

                finished = self.run_status()

                self.assertEqual(finished.stdout, f"one: dead ({reason})\n", finished.stderr)

    def test_changes_prints_a_state_once_and_working_when_the_lane_recovers(self):
        self.add_lane()
        self.stub_agents([self.agent("idle")])
        first = self.run_status("--changes")
        again = self.run_status("--changes")
        self.stub_agents([self.agent("working")])
        recovered = self.run_status("--changes")
        quiet = self.run_status("--changes")

        outputs = [(run.returncode, run.stdout) for run in (first, again, recovered, quiet)]
        self.assertEqual(outputs, [(1, "one: idle\n"), (0, ""), (1, "one: working\n"), (0, "")])

    def test_working_agent_and_healthy_machine_print_nothing(self):
        self.add_lane()
        self.stub_agents([self.agent("working")])

        finished = self.run_status()

        self.assertEqual((finished.returncode, finished.stdout), (0, ""), finished.stderr)

    def test_idle_agent_is_named_with_its_status(self):
        self.add_lane()
        self.stub_agents([self.agent("idle", self.worktree / "sub")])

        finished = self.run_status()

        self.assertEqual(finished.returncode, 1, finished.stderr)
        self.assertEqual(finished.stdout, "one: idle\n")

    def test_a_lane_with_no_agent_is_reported(self):
        self.add_lane()
        self.stub_agents([self.agent("working", self.root / "elsewhere")])

        finished = self.run_status()

        self.assertEqual(finished.returncode, 1, finished.stderr)
        self.assertEqual(finished.stdout, "one: dead (no agent)\n")

    def test_a_lane_with_one_working_agent_among_several_is_silent(self):
        self.add_lane()
        self.stub_agents([self.agent("idle"), self.agent("working")])

        finished = self.run_status()

        self.assertEqual((finished.returncode, finished.stdout), (0, ""), finished.stderr)

    def test_a_lane_with_no_working_agent_reports_the_first_status(self):
        self.add_lane()
        self.stub_agents([self.agent("idle"), self.agent("blocked")])

        finished = self.run_status()

        self.assertEqual((finished.returncode, finished.stdout), (1, "one: idle\n"), finished.stderr)

    def test_an_agent_without_a_status_is_reported_as_unknown(self):
        self.add_lane()
        agent = self.agent("idle")
        del agent["agent_status"]
        self.stub_agents([agent])

        finished = self.run_status()

        self.assertEqual(finished.stdout, "one: unknown\n")

    def test_an_agent_in_a_sibling_folder_with_the_same_prefix_does_not_count(self):
        self.add_lane()
        self.stub_agents([self.agent("working", self.root / "wt-one-extra")])

        finished = self.run_status()

        self.assertEqual(finished.stdout, "one: dead (no agent)\n")

    def test_an_agent_whose_cwd_is_a_symlink_to_the_worktree_counts(self):
        self.add_lane()
        link = self.root / "link-to-wt"
        link.symlink_to(self.worktree)
        self.stub_agents([self.agent("working", link)])

        finished = self.run_status()

        self.assertEqual((finished.returncode, finished.stdout), (0, ""), finished.stderr)

    def test_a_non_claude_agent_in_the_worktree_does_not_count(self):
        self.add_lane()
        other = self.agent("working")
        other["agent"] = "codex"
        self.stub_agents([other])

        finished = self.run_status()

        self.assertEqual(finished.stdout, "one: dead (no agent)\n")

    def test_no_lanes_skips_the_herdr_call(self):
        write_stub(self.bin_dir / "herdr-api", "exit 1")

        finished = self.run_status()

        self.assertEqual((finished.returncode, finished.stdout), (0, ""), finished.stderr)

    def test_a_lane_whose_worktree_is_gone_is_reported(self):
        self.add_lane(worktree=self.root / "vanished")

        finished = self.run_status()

        self.assertEqual(finished.returncode, 1, finished.stderr)
        self.assertEqual(finished.stdout, "one: dead (worktree gone)\n")

    def test_a_closed_lane_is_absent(self):
        self.add_lane()
        lane_entries.remove_entry("one")

        finished = self.run_status()

        self.assertEqual((finished.returncode, finished.stdout), (0, ""), finished.stderr)

    def test_low_scratch_space_prints_the_free_line(self):
        self.stub_df(TIGHT_DF)

        finished = self.run_status()

        scratch_root = self.temp_base / f"claude-{os.getuid()}"
        self.assertEqual(finished.returncode, 1, finished.stderr)
        self.assertRegex(finished.stdout, rf"^scratch: 0\.0 GB free on {re.escape(str(self.temp_base))}, under 1 GB\n$")
        self.assertNotIn(str(scratch_root), finished.stdout)

    def test_scratch_root_over_the_cap_prints_the_holds_line(self):
        scratch_root = self.temp_base / f"claude-{os.getuid()}"
        scratch_root.mkdir()
        self.stub_du("10485760")

        finished = self.run_status()

        self.assertEqual(finished.returncode, 1, finished.stderr)
        self.assertEqual(finished.stdout, f"scratch: {scratch_root} holds 10.0 GB, over 4 GB\n")

    def test_a_missing_scratch_root_skips_the_du_call(self):
        write_stub(self.bin_dir / "du", "exit 9")

        finished = self.run_status()

        self.assertEqual((finished.returncode, finished.stdout), (0, ""), finished.stderr)

    def test_a_failed_du_exits_2(self):
        (self.temp_base / f"claude-{os.getuid()}").mkdir()
        write_stub(self.bin_dir / "du", "exit 9")

        finished = self.run_status()

        self.assertEqual(finished.returncode, 2)
        self.assertIn("du", finished.stderr)

    def test_failed_herdr_api_exits_2(self):
        self.add_lane()
        write_stub(self.bin_dir / "herdr-api", "exit 1")

        finished = self.run_status()

        self.assertEqual(finished.returncode, 2)
        self.assertIn("herdr-api agent list", finished.stderr)

    def test_failed_df_exits_2(self):
        write_stub(self.bin_dir / "df", "exit 1")

        finished = self.run_status()

        self.assertEqual(finished.returncode, 2)
        self.assertIn("df", finished.stderr)

    def test_bad_lane_file_exits_2_naming_the_file(self):
        lanes = self.state_home / "herdr-lanes"
        lanes.mkdir(parents=True)
        (lanes / "broken.json").write_text("{not json")

        finished = self.run_status()

        self.assertEqual(finished.returncode, 2)
        self.assertIn(f"{lanes / 'broken.json'}: field (file): expected valid JSON", finished.stderr)

    @unittest.skipUnless(sys.platform.startswith("linux"), "reads /proc/meminfo")
    def test_memory_under_the_threshold_prints_the_memory_line(self):
        finished = self.run_status(LANE_STATUS_MIN_MEMORY_GB="100000")

        self.assertEqual(finished.returncode, 1, finished.stderr)
        self.assertRegex(finished.stdout, r"^memory: \d+\.\d GB available, under 100000 GB\n$")

    def run_status_on_unknown_platform(self, memory_threshold):
        runner = self.root / "run_with_unknown_platform.py"
        runner.write_text(
            "import importlib.util, sys\n"
            f"spec = importlib.util.spec_from_file_location('lane_status', {str(LANE_STATUS)!r})\n"
            "module = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(module)\n"
            "sys.platform = 'win32'\n"
            "sys.exit(module.main(['lane_status.py']))\n")
        env = self.status_env(LANE_STATUS_MIN_MEMORY_GB=memory_threshold)
        return subprocess.run(["python3", str(runner)], env=env, capture_output=True, text=True)

    def test_unreadable_memory_prints_the_cannot_read_line(self):
        finished = self.run_status_on_unknown_platform("1")

        self.assertEqual((finished.returncode, finished.stdout), (1, "memory: cannot read\n"), finished.stderr)

    def test_a_bad_memory_threshold_exits_2_even_when_memory_is_unreadable(self):
        finished = self.run_status_on_unknown_platform("bad")

        self.assertEqual(finished.returncode, 2)
        self.assertIn("LANE_STATUS_MIN_MEMORY_GB", finished.stderr)

    def test_thresholds_are_checked_even_when_their_path_is_not_taken(self):
        for variable in ("LANE_STATUS_SCRATCH_CAP_GB", "LANE_STATUS_MIN_MEMORY_GB"):
            with self.subTest(variable=variable):
                finished = self.run_status(**{variable: "bad"})

                self.assertEqual(finished.returncode, 2)
                self.assertIn(variable, finished.stderr)

    def test_a_threshold_that_is_nan_inf_or_not_a_number_exits_2_naming_the_variable(self):
        for value in ("nan", "inf", "lots"):
            with self.subTest(value=value):
                finished = self.run_status(LANE_STATUS_MIN_SCRATCH_GB=value)

                self.assertEqual(finished.returncode, 2)
                self.assertIn("LANE_STATUS_MIN_SCRATCH_GB", finished.stderr)

    def test_the_memory_threshold_is_8_gb_when_the_variable_is_unset(self):
        spec = importlib.util.spec_from_file_location("lane_status_under_test", LANE_STATUS)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with mock.patch.dict(os.environ):
            os.environ.pop("LANE_STATUS_MIN_MEMORY_GB", None)
            threshold = module.threshold_gb("LANE_STATUS_MIN_MEMORY_GB")
        self.assertEqual(8, threshold)

        with mock.patch.object(module.system_resources, "memory_available_gb", return_value=7.9):
            under = module.memory_lines(threshold)
        with mock.patch.object(module.system_resources, "memory_available_gb", return_value=8.0):
            at = module.memory_lines(threshold)
        self.assertEqual(["memory: 7.9 GB available, under 8 GB"], under)
        self.assertEqual([], at)


if __name__ == "__main__":
    unittest.main()
