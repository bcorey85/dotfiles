import json
import os
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths

SCRIPT = os.environ.get("OPEN_CHILD_GATE_SCRIPT") or str(toolkit_paths.REVIEW_DIR / "open_child_gate.py")

ASYNC_RESULT = "Async agent launched successfully.\nagentId: a7bf12f9c51bc4875 (internal ID)"


def launch(tool_use_id, subagent_type="spec-research"):
    block = {"type": "tool_use", "id": tool_use_id, "name": "Agent",
             "input": {"subagent_type": subagent_type, "prompt": "go", "run_in_background": True}}
    return {"type": "assistant", "message": {"role": "assistant", "content": [block]}}


def launch_result(tool_use_id):
    block = {"type": "tool_result", "tool_use_id": tool_use_id, "content": [{"type": "text", "text": ASYNC_RESULT}]}
    return {"type": "user", "message": {"role": "user", "content": [block]}}


def notification(tool_use_id):
    text = f"<task-notification>\n<task-id>t1</task-id>\n<tool-use-id>{tool_use_id}</tool-use-id>\n</task-notification>"
    return {"type": "user", "message": {"role": "user", "content": text}}


class OpenChildGateTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.transcript = os.path.join(tmp.name, "agent.jsonl")
        self.env = {**os.environ, "HANDBACK_STORE_DIR": os.path.join(tmp.name, "store")}

    def hand_back(self, records, agent_type="goal-blind-researcher", **extra):
        with open(self.transcript, "w", encoding="utf-8") as fh:
            for record in records:
                fh.write(json.dumps(record) + "\n")
        hook = {"hook_event_name": "PreToolUse", "tool_name": "SubagentHandback", "agent_type": agent_type,
                "agent_transcript_path": self.transcript, "session_id": "s1", "agent_id": "researcher-1",
                "tool_input": {"message": "done"}}
        hook.update(extra)
        proc = subprocess.run([sys.executable, "-B", SCRIPT], input=json.dumps(hook), capture_output=True,
                              text=True, check=True, env=self.env)
        return proc

    def assert_denied(self, proc):
        decision = json.loads(proc.stdout)["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("completion notice", decision["permissionDecisionReason"])
        self.assertIn("Glob", decision["permissionDecisionReason"])
        self.assertIn("failure", decision["permissionDecisionReason"])

    def test_second_hand_back_from_the_same_agent_passes(self):
        records = [launch("toolu_r"), launch_result("toolu_r")]
        self.assert_denied(self.hand_back(records))
        second = self.hand_back(records)
        self.assertEqual(second.stdout, "")
        self.assertEqual(second.stderr, "")

    def test_another_agent_is_denied_on_its_own_first_hand_back(self):
        records = [launch("toolu_r"), launch_result("toolu_r")]
        self.assert_denied(self.hand_back(records))
        self.assert_denied(self.hand_back(records, agent_id="researcher-2"))

    def test_hand_back_after_the_childs_notification_passes(self):
        proc = self.hand_back([launch("toolu_r"), launch_result("toolu_r"), notification("toolu_r")])
        self.assertEqual(proc.stdout, "")
        self.assertEqual(proc.stderr, "")

    def test_hand_back_passes_when_the_child_ended_on_an_api_error(self):
        child_log = os.path.join(os.path.dirname(self.transcript), "agent-a7bf12f9c51bc4875.jsonl")
        with open(child_log, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"type": "assistant", "isApiErrorMessage": True}) + "\n")

        proc = self.hand_back([launch("toolu_r"), launch_result("toolu_r")])

        self.assertEqual(proc.stdout, "")
        self.assertEqual(proc.stderr, "")

    def test_hand_back_with_no_child_passes(self):
        proc = self.hand_back([])
        self.assertEqual(proc.stdout, "")
        self.assertEqual(proc.stderr, "")

    def test_other_agent_type_with_open_child_passes(self):
        proc = self.hand_back([launch("toolu_r"), launch_result("toolu_r")], agent_type="coder")
        self.assertEqual(proc.stdout, "")
        self.assertEqual(proc.stderr, "")

    def test_transcript_is_found_from_session_path_and_agent_id(self):
        session = os.path.join(os.path.dirname(self.transcript), "session")
        os.makedirs(os.path.join(session, "subagents"))
        child_log = os.path.join(session, "subagents", "agent-abc.jsonl")
        with open(child_log, "w", encoding="utf-8") as fh:
            for record in (launch("toolu_r"), launch_result("toolu_r")):
                fh.write(json.dumps(record) + "\n")
        hook = {"agent_type": "goal-blind-researcher", "agent_id": "abc", "session_id": "s1",
                "transcript_path": session + ".jsonl"}
        proc = subprocess.run([sys.executable, "-B", SCRIPT], input=json.dumps(hook), capture_output=True,
                              text=True, check=True, env=self.env)
        self.assert_denied(proc)

    def test_unreadable_transcript_passes_and_says_why(self):
        proc = self.hand_back([], agent_transcript_path=self.transcript + ".missing")
        self.assertEqual(proc.stdout, "")
        self.assertIn("open-child-gate: skipped", proc.stderr)


if __name__ == "__main__":
    unittest.main()
