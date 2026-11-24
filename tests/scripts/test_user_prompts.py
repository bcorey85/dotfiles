"""Checks for user_prompts.starts_turn and script_utils.turn_launched_background: where a turn of the main session
begins, and whether the current turn launched background work."""
import json
import pathlib
import shutil
import sys
import tempfile
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import script_utils
import user_prompts


def user_record(content, **flags):
    return {"type": "user", "message": {"role": "user", "content": content}, **flags}


def launch_record(name, **tool_input):
    return {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "name": name, "input": tool_input}]}}


class StartsTurnTest(unittest.TestCase):
    def test_typed_prompt_shell_echo_and_task_notification_start_a_turn(self):
        for content in ("fix the gate", "<bash-input>ls</bash-input>", "<task-notification>done</task-notification>",
                        [{"type": "text", "text": "fix the gate"}]):
            with self.subTest(content=content):
                self.assertTrue(user_prompts.starts_turn(user_record(content)))

    def test_tool_result_meta_and_subagent_records_start_no_turn(self):
        records = {
            "tool_result": user_record([{"type": "tool_result", "content": "ok"}]),
            "meta": user_record("expansion", isMeta=True),
            "sidechain": user_record("subagent prompt", isSidechain=True),
            "compact summary": user_record("summary", isCompactSummary=True),
            "assistant": launch_record("Bash", command="ls"),
        }
        for label, record in records.items():
            with self.subTest(label=label):
                self.assertFalse(user_prompts.starts_turn(record))


class TurnLaunchedBackgroundTest(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def write_transcript(self, *records, tail=""):
        transcript = self.tmp / "transcript.jsonl"
        transcript.write_text("".join(json.dumps(record) + "\n" for record in records) + tail)
        return transcript

    def test_an_agent_call_launches_unless_set_to_the_foreground(self):
        cases = ((None, True), (True, True), ("true", True), (False, False), ("false", False), (" False ", False))
        for value, expected in cases:
            with self.subTest(value=value):
                options = {} if value is None else {"run_in_background": value}
                transcript = self.write_transcript(user_record("go"), launch_record("Agent", prompt="x", **options))
                self.assertEqual(script_utils.turn_launched_background(transcript), expected)

    def test_a_tool_other_than_bash_or_agent_never_launches(self):
        for name in ("Monitor", "Read"):
            with self.subTest(name=name):
                transcript = self.write_transcript(user_record("go"), launch_record(name, run_in_background=True))
                self.assertFalse(script_utils.turn_launched_background(transcript))

    def test_true_and_the_string_true_count_but_false_and_the_string_false_do_not(self):
        for value, expected in ((True, True), ("true", True), (" True ", True), (False, False), ("false", False)):
            with self.subTest(value=value):
                transcript = self.write_transcript(user_record("go"),
                                                   launch_record("Bash", command="make", run_in_background=value))
                self.assertEqual(script_utils.turn_launched_background(transcript), expected)

    def test_an_agent_launch_counts_and_a_foreground_call_does_not(self):
        launched = self.write_transcript(user_record("go"), launch_record("Agent", run_in_background="true"))
        self.assertTrue(script_utils.turn_launched_background(launched))
        foreground = self.write_transcript(user_record("go"), launch_record("Bash", command="make"))
        self.assertFalse(script_utils.turn_launched_background(foreground))

    def test_a_turn_start_after_the_launch_resets_it(self):
        transcript = self.write_transcript(user_record("go"),
                                           launch_record("Bash", command="make", run_in_background=True),
                                           user_record("<bash-input>ls</bash-input>"))
        self.assertFalse(script_utils.turn_launched_background(transcript))

    def test_a_tool_result_after_the_launch_keeps_it(self):
        transcript = self.write_transcript(user_record("go"),
                                           launch_record("Bash", command="make", run_in_background=True),
                                           user_record([{"type": "tool_result", "content": "started"}]))
        self.assertTrue(script_utils.turn_launched_background(transcript))

    def test_a_torn_last_line_is_skipped(self):
        transcript = self.write_transcript(user_record("go"),
                                           launch_record("Bash", command="make", run_in_background=True),
                                           tail='{"type": "assi')
        self.assertTrue(script_utils.turn_launched_background(transcript))

    def test_a_missing_file_or_an_empty_path_is_false(self):
        self.assertFalse(script_utils.turn_launched_background(self.tmp / "missing.jsonl"))
        self.assertFalse(script_utils.turn_launched_background(""))


if __name__ == "__main__":
    unittest.main()
