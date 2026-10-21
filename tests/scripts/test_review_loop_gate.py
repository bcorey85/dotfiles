import json
import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.environ.get("REVIEW_LOOP_GATE_SCRIPT") or os.path.expanduser("~/.claude/scripts/review-loop-gate.py")

ASYNC_RESULT = "Async agent launched successfully.\nagentId: a7bf12f9c51bc4875 (internal ID)"


def user(text):
    return {"type": "user", "message": {"role": "user", "content": text}}


def dispatch(tool_use_id, subagent_type):
    block = {"type": "tool_use", "id": tool_use_id, "name": "Agent",
             "input": {"subagent_type": subagent_type, "prompt": "go"}}
    return {"type": "assistant", "message": {"role": "assistant", "content": [block]}}


def result(tool_use_id, text):
    block = {"type": "tool_result", "tool_use_id": tool_use_id, "content": [{"type": "text", "text": text}]}
    return {"type": "user", "message": {"role": "user", "content": [block]}}


def bash(command):
    block = {"type": "tool_use", "id": "toolu_bash", "name": "Bash", "input": {"command": command}}
    return {"type": "assistant", "message": {"role": "assistant", "content": [block]}}


def notification(tool_use_id):
    prompt = "<task-notification>\n<task-id>t1</task-id>\n<tool-use-id>%s</tool-use-id>\n</task-notification>" % tool_use_id
    return {"type": "attachment", "attachment": {"type": "queued_command", "prompt": prompt}}


class ReviewLoopGateTest(unittest.TestCase):
    def stop(self, records, **extra):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "loop.jsonl")
        with open(path, "w", encoding="utf-8") as fh:
            for rec in records:
                fh.write(json.dumps(rec) + "\n")
        hook = {"hook_event_name": "SubagentStop", "agent_type": "review-loop", "agent_transcript_path": path}
        hook.update(extra)
        proc = subprocess.run([sys.executable, "-B", SCRIPT], input=json.dumps(hook), capture_output=True,
                              text=True, check=True)
        self.assertEqual(proc.stderr, "")
        return proc.stdout

    def coder_and_background_reviewer(self):
        return [user("review loop"),
                dispatch("toolu_coder", "coder"), result("toolu_coder", "done"),
                dispatch("toolu_rev", "code-reviewer"), result("toolu_rev", ASYNC_RESULT)]

    def test_open_background_dispatch_passes(self):
        self.assertEqual(self.stop(self.coder_and_background_reviewer()), "")

    def test_reported_background_dispatch_blocks_without_full_check(self):
        out = self.stop(self.coder_and_background_reviewer() + [notification("toolu_rev")])
        self.assertIn("No full check ran", json.loads(out)["reason"])

    def test_agent_message_counts_as_reported(self):
        message = user('<agent-message from="a7bf12f9c51bc4875">findings</agent-message>')
        out = self.stop(self.coder_and_background_reviewer() + [message])
        self.assertIn("No full check ran", json.loads(out)["reason"])

    def test_foreground_dispatch_blocks(self):
        records = [user("review loop"),
                   dispatch("toolu_coder", "coder"), result("toolu_coder", "done"),
                   dispatch("toolu_rev", "code-reviewer"), result("toolu_rev", "agentId: a7bf12f9c51bc4875")]
        self.assertIn("No full check ran", json.loads(self.stop(records))["reason"])

    def test_full_check_after_reviewed_coder_passes(self):
        records = [user("review loop"),
                   dispatch("toolu_coder", "coder"), result("toolu_coder", "done"),
                   dispatch("toolu_rev", "code-reviewer"), result("toolu_rev", "ok"),
                   bash("npm test > /tmp/review-gate.log 2>&1")]
        self.assertEqual(self.stop(records), "")

    def test_stop_hook_active_passes(self):
        records = [user("review loop"), dispatch("toolu_coder", "coder"), result("toolu_coder", "done")]
        self.assertEqual(self.stop(records, stop_hook_active=True), "")


if __name__ == "__main__":
    unittest.main()
