import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import toolkit_paths
from test_loop_transcript import INTERRUPT_SHAPES, assistant_record, interrupt_record
from test_open_child_gate import launch, launch_result, notification

SCRIPT = os.environ.get("FORK_CHILDREN_SCRIPT") or str(toolkit_paths.CODE_DIR / "fork_children.py")

FORK_ID = "a" + "1" * 16
CODER_ID = "a7bf12f9c51bc4875"  # the agent id launch_result names
OTHER_ID = "a" + "2" * 16
REVIEW_START = "python3 ~/.claude/scripts/code/code_review_start.py code plan.md 1 handoff.txt --detach"


def tool_result_record(tool_use_id, text):
    block = {"type": "tool_result", "tool_use_id": tool_use_id, "content": [{"type": "text", "text": text}]}
    return {"type": "user", "message": {"role": "user", "content": [block]}}


def launch_result_for(tool_use_id, agent_id):
    return tool_result_record(tool_use_id,
                              f"Async agent launched successfully.\nagentId: {agent_id} (internal ID)")


def unresolved_launch_result(tool_use_id):
    return tool_result_record(tool_use_id, "Async agent launched successfully.")


def bash_record(command, cwd=None):
    block = {"type": "tool_use", "id": "toolu_bash", "name": "Bash", "input": {"command": command}}
    record = {"type": "assistant", "message": {"role": "assistant", "content": [block]}}
    if cwd is not None:
        record["cwd"] = cwd
    return record


class ForkChildrenTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        config_dir = os.path.join(tmp.name, "config")
        self.subagents = os.path.join(config_dir, "projects", "proj", "session", "subagents")
        os.makedirs(self.subagents)
        self.repo = os.path.join(tmp.name, "repo")
        os.makedirs(self.repo)
        subprocess.run(["git", "init", "-q", self.repo], check=True)
        self.env = {**os.environ, "HANDBACK_STORE_DIR": os.path.join(tmp.name, "store"),
                    "CLAUDE_CONFIG_DIR": config_dir}
        self.env.pop("CLAUDE_SKIP_HOOKS", None)

    def write_agent(self, agent_id, records, meta):
        transcript = os.path.join(self.subagents, f"agent-{agent_id}.jsonl")
        meta_path = os.path.join(self.subagents, f"agent-{agent_id}.meta.json")
        with open(transcript, "w", encoding="utf-8") as fh:
            for record in records:
                fh.write(json.dumps(record) + "\n")
        if meta is None:
            return
        with open(meta_path, "w", encoding="utf-8") as fh:
            json.dump(meta, fh)

    def write_fork(self, records, agent_type="code-fork"):
        self.write_agent(FORK_ID, records, {"agentType": agent_type})

    def write_live_coder_fork(self, coder_records=None, coder_meta=None):
        self.write_fork([launch("toolu_c", subagent_type="coder"), launch_result("toolu_c")])
        records = [assistant_record()] if coder_records is None else coder_records
        self.write_agent(CODER_ID, records, {"agentType": "coder"} if coder_meta is None else coder_meta)

    def run_script(self, args, stdin=None):
        return subprocess.run([sys.executable, "-B", SCRIPT, *args], input=stdin, capture_output=True, text=True,
                              env=self.env, check=False)

    def hook(self, task_id=FORK_ID, tool_name="TaskStop", session_id="s1"):
        # A transcript TaskStop event: tool_input holds the task id. A captured event replaces this fixture once
        # the hook is wired in settings.json.
        event = {"hook_event_name": "PreToolUse", "tool_name": tool_name, "tool_input": {"task_id": task_id},
                 "session_id": session_id, "transcript_path": os.path.join(self.subagents, "..", "main.jsonl")}
        return self.run_script(["hook"], stdin=json.dumps(event))

    def report(self):
        proc = self.run_script([FORK_ID, "--repo", self.repo])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def assert_passes(self, proc):
        self.assertEqual(proc.stdout, "")
        self.assertEqual(proc.stderr, "")
        self.assertEqual(proc.returncode, 0)

    def assert_denied_naming(self, proc, *names):
        decision = json.loads(proc.stdout)["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny")
        reason = decision["permissionDecisionReason"]
        self.assertIn(f"fork_children.py {FORK_ID}", reason)
        self.assertIn(f"code fork {FORK_ID} has live children: ", reason)
        self.assertTrue(reason.endswith("TaskStop each id it names, then TaskStop the fork."), reason)
        for name in names:
            self.assertIn(name, reason)

    def test_taskstop_of_a_fork_with_a_live_coder_is_denied_once(self):
        self.write_live_coder_fork()

        self.assert_denied_naming(self.hook(), CODER_ID)
        self.assert_passes(self.hook())

        store_file = os.path.join(self.env["HANDBACK_STORE_DIR"], "s1.jsonl")
        with open(store_file, encoding="utf-8") as fh:
            rows = [json.loads(line) for line in fh if line.strip()]
        self.assertEqual([(row["kind"], row["agent_id"], row["children"]) for row in rows],
                         [("taskstop_children_denied", FORK_ID, [CODER_ID])])

    def test_a_launch_with_no_agent_id_yet_is_named_in_the_deny(self):
        self.write_fork([launch("toolu_x", subagent_type="coder"), unresolved_launch_result("toolu_x")])

        self.assert_denied_naming(self.hook(), "launch toolu_x (no agent id yet)")

    def hook_with_non_fork_agent_type(self, session_id):
        self.write_fork([launch("toolu_c", subagent_type="coder"), launch_result("toolu_c")], agent_type="coder")
        return self.hook(session_id=session_id)

    def hook_with_child_finished_by_meta(self, session_id):
        self.write_live_coder_fork(coder_meta={"agentType": "coder", "finished": True})
        return self.hook(session_id=session_id)

    def hook_with_no_child(self, session_id):
        self.write_fork([])
        return self.hook(session_id=session_id)

    def test_taskstop_passes_when_it_is_not_a_stop_of_a_fork_with_a_live_child(self):
        self.write_live_coder_fork()
        cases = {
            "a background task id": lambda session_id: self.hook(task_id="b1a2b3c4d", session_id=session_id),
            "another tool": lambda session_id: self.hook(tool_name="Bash", session_id=session_id),
            "an agent id with no transcript": lambda session_id: self.hook(task_id=OTHER_ID, session_id=session_id),
            "a non-fork agent type": self.hook_with_non_fork_agent_type,
            "a child finished by meta": self.hook_with_child_finished_by_meta,
            "a fork with no child": self.hook_with_no_child,
        }
        for number, (label, run_case) in enumerate(cases.items()):
            with self.subTest(case=label):
                self.assert_passes(run_case(f"passes-{number}"))

    def test_an_event_with_no_session_id_passes_with_a_live_child(self):
        self.write_live_coder_fork()
        event = {"hook_event_name": "PreToolUse", "tool_name": "TaskStop", "tool_input": {"task_id": FORK_ID}}

        self.assert_passes(self.run_script(["hook"], stdin=json.dumps(event)))

    def test_the_denial_is_once_per_fork_and_session(self):
        self.write_live_coder_fork()

        self.assert_denied_naming(self.hook(session_id="s1"), CODER_ID)
        self.assert_passes(self.hook(session_id="s1"))
        self.assert_denied_naming(self.hook(session_id="s2"), CODER_ID)

    def test_a_meta_named_child_that_ends_on_an_interrupt_record_is_not_listed(self):
        self.write_fork([])
        self.write_agent(CODER_ID, [assistant_record(), interrupt_record()],
                         {"agentType": "coder", "parentAgentId": FORK_ID})

        self.assertEqual(self.report()["children"], [])

    def test_a_child_named_by_launch_and_by_meta_is_listed_once(self):
        self.write_live_coder_fork(coder_meta={"agentType": "coder", "parentAgentId": FORK_ID})

        self.assertEqual(self.report()["children"], [CODER_ID])

    def test_a_launch_named_child_that_ends_on_an_interrupt_record_is_not_listed(self):
        self.write_live_coder_fork(coder_records=[assistant_record(), interrupt_record()])

        self.assertEqual(self.report()["children"], [])

    def test_a_meta_that_names_another_parent_is_not_this_forks_child(self):
        self.write_fork([])
        self.write_agent(CODER_ID, [assistant_record()], {"agentType": "coder", "parentAgentId": OTHER_ID})

        self.assertEqual(self.report()["children"], [])

    def test_a_skipped_hook_passes_with_a_live_child(self):
        self.write_live_coder_fork()
        self.env["CLAUDE_SKIP_HOOKS"] = "1"

        self.assert_passes(self.hook())

    def test_a_torn_meta_file_beside_the_fork_does_not_stop_the_report(self):
        self.write_live_coder_fork(coder_meta={"agentType": "coder", "parentAgentId": FORK_ID})
        with open(os.path.join(self.subagents, f"agent-{OTHER_ID}.meta.json"), "w", encoding="utf-8") as fh:
            fh.write('{"agentType": "coder", "paren')

        self.assertEqual(self.report()["children"], [CODER_ID])

    def test_a_child_that_ends_on_an_interrupt_record_is_not_live_and_an_assistant_record_is(self):
        for number, interrupt_text in enumerate(INTERRUPT_SHAPES):
            with self.subTest(interrupt=interrupt_text):
                self.write_live_coder_fork(coder_records=[assistant_record(), interrupt_record(interrupt_text)])
                self.assert_passes(self.hook(session_id=f"interrupted-{number}"))

                self.write_live_coder_fork(coder_records=[interrupt_record(interrupt_text), assistant_record()])
                self.assert_denied_naming(self.hook(session_id=f"running-{number}"), CODER_ID)

    def test_a_meta_named_child_with_a_delivered_handback_is_not_listed(self):
        handback = {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": "toolu_hb", "name": "SubagentHandback", "input": {"message": "done"}}]}}
        self.write_fork([])
        self.write_agent(CODER_ID, [assistant_record(), handback, tool_result_record("toolu_hb", "ok")],
                         {"agentType": "coder", "parentAgentId": FORK_ID})

        self.assertEqual(self.report()["children"], [])

    def test_a_store_that_cannot_be_written_passes_and_says_why(self):
        self.write_live_coder_fork()
        blocker = os.path.join(os.path.dirname(self.env["HANDBACK_STORE_DIR"]), "store-is-a-file")
        with open(blocker, "w", encoding="utf-8") as fh:
            fh.write("x")
        self.env["HANDBACK_STORE_DIR"] = blocker

        proc = self.hook()

        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "")
        self.assertTrue(proc.stderr.startswith("fork-children-hook: skipped"), proc.stderr)

    def test_malformed_stdin_passes_and_says_why(self):
        proc = self.run_script(["hook"], stdin="not json")

        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "")
        self.assertTrue(proc.stderr.startswith("fork-children-hook: skipped"), proc.stderr)

    def test_the_report_lists_live_launches_and_leaves_out_a_launch_that_reported(self):
        self.write_fork([launch("toolu_c", subagent_type="coder"), launch_result("toolu_c"),
                         launch("toolu_n", subagent_type="coder"), launch_result_for("toolu_n", OTHER_ID),
                         notification("toolu_n"),
                         launch("toolu_x", subagent_type="coder"), unresolved_launch_result("toolu_x")])
        self.write_agent(CODER_ID, [assistant_record()], {"agentType": "coder"})

        self.assertEqual(self.report(), {"fork": FORK_ID, "children": [CODER_ID], "unresolved_launches": ["toolu_x"],
                                         "loop": {"pid": None, "stopped": False, "reason": "none"}})

    def test_a_child_named_only_by_its_meta_parent_is_listed_unless_it_finished(self):
        self.write_fork([])
        self.write_agent(CODER_ID, [assistant_record()], {"agentType": "coder", "parentAgentId": FORK_ID})
        self.write_agent(OTHER_ID, [assistant_record()],
                         {"agentType": "coder", "parentAgentId": FORK_ID, "finished": True})

        self.assertEqual(self.report()["children"], [CODER_ID])

    def start_process(self, marker):
        argv = [sys.executable, "-c", "import time; time.sleep(120)", *marker]
        process = subprocess.Popen(argv, start_new_session=True)
        self.addCleanup(process.wait)
        self.addCleanup(process.kill)
        return process

    def record_loop_pid(self, pid):
        git_path = subprocess.run(["git", "-C", self.repo, "rev-parse", "--path-format=absolute", "--git-path",
                                   "code-phase"], capture_output=True, text=True, check=True)
        phase_dir = git_path.stdout.strip()
        os.makedirs(phase_dir, exist_ok=True)
        with open(os.path.join(phase_dir, "pid"), "w", encoding="utf-8") as fh:
            fh.write(str(pid))

    def test_the_report_stops_the_loop_this_fork_started(self):
        self.write_fork([bash_record(REVIEW_START)])
        process = self.start_process(["code_review_start.py"])
        self.record_loop_pid(process.pid)

        loop = self.report()["loop"]

        self.assertEqual(loop, {"pid": process.pid, "stopped": True, "reason": "stopped"})
        self.assertIsNotNone(process.wait(timeout=10))

    def test_the_report_leaves_a_review_loop_the_fork_did_not_start_running(self):
        self.write_fork([])
        process = self.start_process(["code_review_start.py"])
        self.record_loop_pid(process.pid)

        loop = self.report()["loop"]

        self.assertEqual(loop, {"pid": process.pid, "stopped": False, "reason": "not_this_run"})
        self.assertIsNone(process.poll())

    def test_the_report_leaves_a_process_that_is_not_a_review_loop_running(self):
        self.write_fork([bash_record(REVIEW_START)])
        process = self.start_process([])
        self.record_loop_pid(process.pid)

        loop = self.report()["loop"]

        self.assertEqual(loop, {"pid": process.pid, "stopped": False, "reason": "not_review_loop"})
        self.assertIsNone(process.poll())

    def test_the_report_finds_the_repo_from_the_forks_last_cwd_when_run_from_another_folder(self):
        self.write_fork([bash_record(REVIEW_START, cwd=self.repo)])
        process = self.start_process(["code_review_start.py"])
        self.record_loop_pid(process.pid)

        proc = subprocess.run([sys.executable, "-B", SCRIPT, FORK_ID], capture_output=True, text=True, env=self.env,
                              cwd=tempfile.gettempdir(), check=False)

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["loop"], {"pid": process.pid, "stopped": True, "reason": "stopped"})

    def test_the_report_without_repo_falls_back_to_the_current_folder_when_the_fork_records_no_cwd(self):
        self.write_fork([bash_record(REVIEW_START)])
        process = self.start_process(["code_review_start.py"])
        self.record_loop_pid(process.pid)

        proc = subprocess.run([sys.executable, "-B", SCRIPT, FORK_ID], capture_output=True, text=True, env=self.env,
                              cwd=self.repo, check=False)

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["loop"], {"pid": process.pid, "stopped": True, "reason": "stopped"})

    def test_a_repo_outside_a_git_checkout_reports_no_repo_with_the_children_named(self):
        self.write_live_coder_fork()
        not_a_repo = os.path.join(os.path.dirname(self.repo), "plain")
        os.makedirs(not_a_repo)

        proc = self.run_script([FORK_ID, "--repo", not_a_repo])

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout), {"fork": FORK_ID, "children": [CODER_ID], "unresolved_launches": [],
                                                   "loop": {"pid": None, "stopped": False, "reason": "no_repo"}})

    def test_usage_errors_exit_2(self):
        self.write_agent(CODER_ID, [assistant_record()], {"agentType": "coder"})
        cases = {"not an agent id": ["xyz"], "no transcript": [OTHER_ID], "not a code fork": [CODER_ID]}
        for label, args in cases.items():
            with self.subTest(case=label):
                proc = self.run_script([*args, "--repo", self.repo])
                self.assertEqual(proc.returncode, 2, proc.stderr)
                self.assertEqual(proc.stdout, "")


class StopLoopBranchTest(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("fork_children_under_test", SCRIPT)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def stop_loop_with(self, command_line, terminated=True):
        module = self.module
        with mock.patch.object(module.code_wait, "running_review_pid", return_value=4242), \
                mock.patch.object(module.process_group, "command_line", command_line), \
                mock.patch.object(module.process_group, "terminate_group", return_value=terminated), \
                mock.patch.object(module.script_utils, "bash_commands", return_value=[REVIEW_START]), \
                contextlib.redirect_stderr(io.StringIO()) as stderr:
            return module.stop_fork_loop("repo", "transcript"), stderr.getvalue()

    def test_a_failed_process_query_reads_as_not_a_review_loop(self):
        def failing_query(pid):
            raise self.module.process_group.ProcessQueryError("ps timed out")

        loop, stderr = self.stop_loop_with(failing_query)

        self.assertEqual(loop, {"pid": 4242, "stopped": False, "reason": "not_review_loop"})
        self.assertIn("ps timed out", stderr)

    def test_a_process_that_died_before_its_command_line_was_read_reads_as_gone(self):
        loop, _ = self.stop_loop_with(lambda pid: "")

        self.assertEqual(loop, {"pid": 4242, "stopped": False, "reason": "gone"})

    def test_a_loop_that_ended_before_it_was_stopped_reads_as_gone(self):
        loop, _ = self.stop_loop_with(lambda pid: "python3 code_review_start.py", terminated=False)

        self.assertEqual(loop, {"pid": 4242, "stopped": False, "reason": "gone"})


if __name__ == "__main__":
    unittest.main()
