"""Tests for the /code fork review check that staged_claim_gate.py runs on SubagentStop: a fork that dispatched a coder
for a phase and ran no review of it is sent back once.

The hook payloads here are SYNTHETIC: no SubagentStop event has been captured, so the field names come from the
SubagentHandback event and the plan, not from a real stop."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

import fork_transcript as ft
import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import fork_review

GATE = toolkit_paths.GATES_DIR / "staged_claim_gate.py"
AGENT_ID = "af3a946da2498ee41"


class ForkReviewGateTests(unittest.TestCase):
    def setUp(self):
        temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temp_directory.cleanup)
        self.root = pathlib.Path(temp_directory.name)
        self.transcript = self.root / f"agent-{AGENT_ID}.jsonl"

    def write_records(self, *records, torn_tail=""):
        self.transcript.write_text(ft.jsonl_text(records, torn_tail))

    def run_gate(self, **overrides):
        hook = {"hook_event_name": "SubagentStop", "agent_type": "code-fork", "agent_id": AGENT_ID,
                "agent_transcript_path": str(self.transcript), "session_id": "s1", "cwd": str(self.root),
                "stop_hook_active": False, "last_assistant_message": "Done."}
        hook.update(overrides)
        hook = {name: value for name, value in hook.items() if value is not None}
        env = {name: value for name, value in os.environ.items() if name != "CLAUDE_SKIP_HOOKS"}
        return subprocess.run([sys.executable, "-B", str(GATE)], input=json.dumps(hook), env=env,
                              capture_output=True, text=True, check=False)

    def assert_sent_back(self, done):
        self.assertEqual(0, done.returncode, done.stderr)
        decision = json.loads(done.stdout)
        self.assertEqual("block", decision["decision"])
        self.assertIn(fork_review.REASON, decision["reason"])

    def assert_passes(self, done):
        self.assertEqual(0, done.returncode, done.stderr)
        self.assertEqual("", done.stdout)

    def test_incident_fork_with_a_coder_and_no_review_is_sent_back(self):
        self.transcript.write_text(ft.FIXTURE.read_text())

        self.assert_sent_back(self.run_gate())

    def test_fork_that_ran_review_start_then_wait_review_passes(self):
        self.write_records(ft.skill_record(), ft.coder_record(), ft.bash_record(ft.REVIEW_START_COMMAND),
                           ft.bash_record(ft.WAIT_REVIEW_COMMAND), ft.text_record())

        self.assert_passes(self.run_gate())

    def test_review_start_and_wait_in_one_call_passes(self):
        both = f"{ft.REVIEW_START_COMMAND} && {ft.WAIT_REVIEW_COMMAND}"
        self.write_records(ft.skill_record(), ft.coder_record(), ft.bash_record(both), ft.text_record())

        self.assert_passes(self.run_gate())

    def test_review_start_without_wait_is_sent_back(self):
        self.write_records(ft.skill_record(), ft.coder_record(), ft.bash_record(ft.REVIEW_START_COMMAND),
                           ft.bash_record(ft.WAIT_AGENT_COMMAND), ft.text_record())

        self.assert_sent_back(self.run_gate())

    def test_review_before_the_coder_dispatch_is_sent_back(self):
        self.write_records(ft.skill_record(), ft.bash_record(ft.REVIEW_START_COMMAND),
                           ft.bash_record(ft.WAIT_REVIEW_COMMAND), ft.coder_record(), ft.text_record())

        self.assert_sent_back(self.run_gate())

    def test_stop_md_written_after_the_coder_passes(self):
        self.write_records(ft.skill_record(), ft.coder_record(), ft.stop_write_record(), ft.text_record())

        self.assert_passes(self.run_gate())

    def test_stale_stop_md_before_the_coder_is_sent_back(self):
        self.write_records(ft.skill_record(), ft.stop_write_record(), ft.coder_record(), ft.text_record())

        self.assert_sent_back(self.run_gate())

    def test_stale_run_folder_with_review_out_and_stop_md_is_sent_back(self):
        run_folder = self.root / ".git" / "code-phase"
        run_folder.mkdir(parents=True)
        (run_folder / "review.out").write_text("converged")
        (run_folder / "stop.md").write_text("an earlier run stopped")
        self.write_records(ft.skill_record(), ft.coder_record(), ft.text_record())

        self.assert_sent_back(self.run_gate())

    def test_multi_phase_second_phase_coded_without_review_is_sent_back(self):
        self.write_records(ft.skill_record(), ft.bash_record(ft.PHASE_START_NEW_RUN_COMMAND), ft.coder_record(),
                           ft.bash_record(ft.REVIEW_START_COMMAND), ft.bash_record(ft.WAIT_REVIEW_COMMAND),
                           ft.bash_record(ft.PHASE_START_COMMAND), ft.coder_record(), ft.text_record())

        self.assert_sent_back(self.run_gate())

    def test_multi_phase_every_phase_reviewed_passes(self):
        self.write_records(ft.skill_record(), ft.bash_record(ft.PHASE_START_NEW_RUN_COMMAND), ft.coder_record(),
                           ft.bash_record(ft.REVIEW_START_COMMAND), ft.bash_record(ft.WAIT_REVIEW_COMMAND),
                           ft.bash_record(ft.PHASE_START_COMMAND), ft.coder_record(),
                           ft.bash_record(ft.REVIEW_START_COMMAND), ft.bash_record(ft.WAIT_REVIEW_COMMAND),
                           ft.text_record())

        self.assert_passes(self.run_gate())

    def test_stop_md_written_by_a_bash_redirect_after_the_coder_passes(self):
        redirect = f"cat > {ft.STOP_FILE_PATH} <<'EOF'\nit's stopped\nEOF"
        self.write_records(ft.skill_record(), ft.coder_record(), ft.bash_record(redirect), ft.text_record())

        self.assert_passes(self.run_gate())

    def test_a_redirect_to_another_file_is_no_stop(self):
        self.write_records(ft.skill_record(), ft.coder_record(), ft.bash_record("echo x > /tmp/notes.md"),
                           ft.text_record())

        self.assert_sent_back(self.run_gate())

    def test_a_write_to_a_look_alike_stop_file_is_no_stop(self):
        for name in ("review-stop.md", "stop.md.bak"):
            file_path = f"/tmp/repo/.git/code-phase/{name}"
            for kind, record in (("write", ft.stop_write_record(file_path)),
                                 ("redirect", ft.bash_record(f"echo x > {file_path}"))):
                with self.subTest(name=name, kind=kind):
                    self.write_records(ft.skill_record(), ft.coder_record(), record, ft.text_record())

                    self.assert_sent_back(self.run_gate())

    def test_mid_phase_phase_start_call_leaves_the_coded_phase_unreviewed(self):
        self.write_records(ft.skill_record(), ft.coder_record(), ft.bash_record(ft.PHASE_START_COMMAND),
                           ft.text_record())

        self.assert_sent_back(self.run_gate())

    def test_mid_phase_phase_start_call_before_the_review_passes(self):
        self.write_records(ft.skill_record(), ft.coder_record(), ft.bash_record(ft.PHASE_START_COMMAND),
                           ft.bash_record(ft.REVIEW_START_COMMAND), ft.bash_record(ft.WAIT_REVIEW_COMMAND),
                           ft.text_record())

        self.assert_passes(self.run_gate())

    def test_resumed_fork_with_a_tick_coder_before_its_first_phase_start_passes(self):
        self.write_records(ft.skill_record(), ft.coder_record(), ft.bash_record(ft.PHASE_START_COMMAND),
                           ft.coder_record(), ft.bash_record(ft.REVIEW_START_COMMAND),
                           ft.bash_record(ft.WAIT_REVIEW_COMMAND), ft.text_record())

        self.assert_passes(self.run_gate())

    def test_tick_coder_after_the_review_passes(self):
        self.write_records(ft.skill_record(), ft.coder_record(), ft.bash_record(ft.REVIEW_START_COMMAND),
                           ft.bash_record(ft.WAIT_REVIEW_COMMAND), ft.coder_record(), ft.text_record())

        self.assert_passes(self.run_gate())

    def test_fork_with_no_coder_dispatch_passes(self):
        self.write_records(ft.skill_record(), ft.bash_record("git status"), ft.text_record())

        self.assert_passes(self.run_gate())

    def test_review_and_fix_forks_pass(self):
        for skill in ("review", "fix"):
            with self.subTest(skill=skill):
                self.write_records(ft.skill_record(skill), ft.coder_record(), ft.text_record())

                self.assert_passes(self.run_gate())

    def test_other_agent_type_passes(self):
        self.transcript.write_text(ft.FIXTURE.read_text())

        self.assert_passes(self.run_gate(agent_type="coder"))

    def test_agent_type_read_from_meta_when_the_event_lacks_it(self):
        self.transcript.write_text(ft.FIXTURE.read_text())
        (self.root / f"agent-{AGENT_ID}.meta.json").write_text(json.dumps({"agentType": "code-fork"}))

        self.assert_sent_back(self.run_gate(agent_type=None))

    def test_transcript_path_derived_from_the_session_transcript_and_agent_id(self):
        session_transcript = self.root / "session.jsonl"
        derived = self.root / "session" / "subagents" / f"agent-{AGENT_ID}.jsonl"
        derived.parent.mkdir(parents=True)
        derived.write_text(ft.FIXTURE.read_text())

        done = self.run_gate(agent_transcript_path=None, transcript_path=str(session_transcript))

        self.assert_sent_back(done)

    def test_event_naming_no_transcript_passes(self):
        self.transcript.write_text(ft.FIXTURE.read_text())

        self.assert_passes(self.run_gate(agent_transcript_path=None))

    def test_a_stale_wait_before_the_review_start_is_sent_back(self):
        self.write_records(ft.skill_record(), ft.coder_record(), ft.bash_record(ft.WAIT_REVIEW_COMMAND),
                           ft.bash_record(ft.REVIEW_START_COMMAND), ft.text_record())

        self.assert_sent_back(self.run_gate())

    def test_second_stop_passes(self):
        self.transcript.write_text(ft.FIXTURE.read_text())

        self.assert_passes(self.run_gate(stop_hook_active=True))

    def test_main_session_stop_never_runs_the_fork_check(self):
        self.transcript.write_text(ft.FIXTURE.read_text())

        self.assert_passes(self.run_gate(hook_event_name="Stop"))

    def test_missing_transcript_passes(self):
        self.assert_passes(self.run_gate())

    def test_torn_last_line_is_skipped(self):
        self.transcript.write_text(ft.FIXTURE.read_text() + '{"type": "assistant", "message": {"rol')

        self.assert_sent_back(self.run_gate())


if __name__ == "__main__":
    unittest.main()
