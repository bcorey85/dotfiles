"""Checks for wait_loop_gate.py, the PreToolUse hook that denies unbounded waits in subagent Bash calls.

Set WAIT_LOOP_GATE_SCRIPT to run against another copy, such as a staged one."""
import json
import os
import pathlib
import subprocess
import sys
import unittest

import toolkit_paths

SCRIPT = pathlib.Path(os.environ.get("WAIT_LOOP_GATE_SCRIPT")
                      or toolkit_paths.GATES_DIR / "wait_loop_gate.py")


def run_hook(stdin):
    return subprocess.run([sys.executable, str(SCRIPT)], input=stdin, capture_output=True, text=True)


def run_command(command, subagent=True):
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    if subagent:
        payload["agent_type"] = "coder"
        payload["agent_id"] = "abc123"
    return run_hook(json.dumps(payload))


class WaitLoopGateTest(unittest.TestCase):
    def assert_denied(self, command):
        finished = run_command(command)
        self.assertEqual(finished.returncode, 0)
        decision = json.loads(finished.stdout)["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertTrue(decision["permissionDecisionReason"])
        return decision["permissionDecisionReason"]

    def assert_passes(self, command, subagent=True):
        finished = run_command(command, subagent)
        self.assertEqual(finished.returncode, 0)
        self.assertEqual(finished.stdout, "")

    def test_until_loop_denied(self):
        reason = self.assert_denied("until curl -sf localhost:3000; do sleep 2; done")
        self.assertIn("seq 30", reason)

    def test_while_loop_denied(self):
        self.assert_denied("while ! docker ps | grep -q db; do\n  sleep 5\ndone")

    def test_loop_commands_pass_as_main_session(self):
        for command in ("until curl -sf localhost:3000; do sleep 2; done", "tail -f app.log", "sleep 300",
                        "for i in $(seq 100); do sleep 5; done"):
            self.assert_passes(command, subagent=False)

    def test_agent_id_alone_marks_subagent(self):
        payload = {"agent_id": "x", "tool_input": {"command": "sleep 300"}}
        self.assertIn("deny", run_hook(json.dumps(payload)).stdout)

    def test_bounded_for_loop_passes(self):
        self.assert_passes("for i in $(seq 30); do curl -sf localhost:3000 && break; sleep 3; done")

    def test_brace_range_and_word_list_pass(self):
        self.assert_passes("for i in {1..20}; do check && break; sleep 5; done")
        self.assert_passes("for i in a b c; do check && break; sleep 10; done")

    def test_long_for_loop_denied(self):
        self.assert_denied("for i in $(seq 100); do curl -sf localhost:3000 && break; sleep 5; done")

    def test_for_loop_with_unknown_count_denied(self):
        self.assert_denied("for i in $(ls); do sleep 1; done")
        self.assert_denied("for i in $COUNT; do sleep 1; done")

    def test_for_loop_without_sleep_passes(self):
        self.assert_passes("for f in a.txt b.txt; do cat $f; done")

    def test_follow_modes_denied(self):
        for command in ("tail -f app.log", "tail -F app.log", "tail --follow app.log", "docker logs -f web",
                        "docker logs --follow web", "docker compose logs -f web",
                        "docker compose -f dc.yml -p demo logs --follow web", "kubectl logs -f pod/x",
                        "journalctl -f -u svc", "watch ls", "docker logs -f web | grep ready"):
            with self.subTest(command=command):
                self.assert_denied(command)

    def test_follow_bounded_by_timeout_passes(self):
        self.assert_passes("timeout 90 docker logs -f x")
        self.assert_passes("timeout -s KILL 120 tail -f x")

    def test_follow_with_long_timeout_denied(self):
        self.assert_denied("timeout 900 tail -f x")

    def test_standalone_sleep(self):
        self.assert_passes("sleep 5")
        self.assert_passes("sleep 30")
        self.assert_denied("sleep 120")
        self.assert_denied("sleep 1m")

    def test_ordinary_commands_pass(self):
        for command in ("docker logs --tail 200 x", "docker logs --since 2m x", "make test", "tail -n 50 app.log",
                        "docker compose -f dc.yml logs --tail 50", "git log --until=2026-01-01"):
            with self.subTest(command=command):
                self.assert_passes(command)

    def test_heredoc_text_with_loop_words_passes(self):
        self.assert_passes("cat > notes.md <<'EOF'\nuntil the build is green, sleep 600 and tail -f the log\n"
                           "while true; do sleep 1; done\nEOF\nls")

    def test_quoted_text_passes(self):
        self.assert_passes('echo "until ready; do sleep 60; done"')

    def test_garbage_stdin_passes(self):
        for stdin in ("", "not json", "[1, 2]", '{"agent_id": "x", "tool_input": null}',
                      '{"agent_id": "x", "tool_input": {"command": 5}}'):
            with self.subTest(stdin=stdin):
                finished = run_hook(stdin)
                self.assertEqual(finished.returncode, 0)
                self.assertEqual(finished.stdout, "")


if __name__ == "__main__":
    unittest.main()
