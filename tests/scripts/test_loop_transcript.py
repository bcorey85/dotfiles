import json
import os
import pathlib
import sys
import tempfile
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import loop_transcript

INTERRUPT_SHAPES = ("[Request interrupted by user]", "[Request interrupted by user for tool use]")


def interrupt_record(text=INTERRUPT_SHAPES[0]):
    block = {"type": "text", "text": text}
    return {"type": "user", "message": {"role": "user", "content": [block]}}


def assistant_record(text="working"):
    block = {"type": "text", "text": text}
    return {"type": "assistant", "message": {"role": "assistant", "content": [block]}}


class AgentInterruptedTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.transcript = os.path.join(tmp.name, "agent-a1.jsonl")

    def write(self, records):
        with open(self.transcript, "w", encoding="utf-8") as fh:
            for record in records:
                fh.write(json.dumps(record) + "\n")

    def test_each_interrupt_shape_as_the_last_record_is_interrupted(self):
        for text in INTERRUPT_SHAPES:
            with self.subTest(text=text):
                self.write([assistant_record(), interrupt_record(text)])
                self.assertTrue(loop_transcript.agent_interrupted(self.transcript))

    def test_a_normal_last_assistant_record_is_not_interrupted(self):
        self.write([interrupt_record(), assistant_record()])
        self.assertFalse(loop_transcript.agent_interrupted(self.transcript))

    def test_an_interrupt_record_that_is_not_the_last_record_is_not_interrupted(self):
        self.write([assistant_record(), interrupt_record(), assistant_record("resumed")])
        self.assertFalse(loop_transcript.agent_interrupted(self.transcript))

    def test_a_missing_file_is_not_interrupted(self):
        self.assertFalse(loop_transcript.agent_interrupted(self.transcript + ".missing"))

    def test_content_shapes_are_read_for_the_interrupt_text(self):
        text = INTERRUPT_SHAPES[0]
        later_block = [{"type": "tool_result", "content": "x"}, {"type": "text", "text": text}]
        cases = {
            "a plain string": (text, True),
            "the interrupt as a later block": (later_block, True),
            "a non-text block only": ([{"type": "tool_result", "text": text}], False),
            "a non-dict block": (["not a block", {"type": "text", "text": "hi"}], False),
            "a text block with no text": ([{"type": "text"}], False),
            "null content": (None, False),
            "ordinary user text": ("please go on", False),
        }
        for label, (content, expected) in cases.items():
            with self.subTest(case=label):
                self.write([{"type": "user", "message": {"role": "user", "content": content}}])
                self.assertEqual(loop_transcript.agent_interrupted(self.transcript), expected)

    def test_a_user_record_with_no_message_is_not_interrupted(self):
        self.write([{"type": "user"}])
        self.assertFalse(loop_transcript.agent_interrupted(self.transcript))

    def test_real_transcript_endings_read_as_interrupted_only_when_the_interrupt_is_last(self):
        fixtures = pathlib.Path(__file__).resolve().parent / "fixtures"
        cases = {
            "interrupt_ends_transcript.jsonl": True,
            "interrupt_then_resumed_transcript.jsonl": False,
            "interrupt_quoted_in_tool_result_transcript.jsonl": False,
        }
        for name, expected in cases.items():
            with self.subTest(fixture=name):
                self.assertEqual(loop_transcript.agent_interrupted(fixtures / name), expected)


class MetaReaderTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.transcript = os.path.join(tmp.name, "agent-a1.jsonl")
        self.meta_path = os.path.join(tmp.name, "agent-a1.meta.json")

    def write_meta(self, text):
        with open(self.meta_path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def test_finished_by_meta_is_true_only_when_the_meta_says_finished(self):
        self.assertFalse(loop_transcript.finished_by_meta(self.transcript))
        self.write_meta("{}")
        self.assertFalse(loop_transcript.finished_by_meta(self.transcript))
        self.write_meta('{"finished": true}')
        self.assertTrue(loop_transcript.finished_by_meta(self.transcript))

    def test_subagent_entries_yield_each_meta_file_with_its_transcript_path_and_meta_by_agent_id(self):
        folder = pathlib.Path(os.path.dirname(self.transcript))
        for agent_id, meta_text in (("a2", '{"agentType": "coder"}'), ("a1", '{"torn": ')):
            (folder / f"agent-{agent_id}.meta.json").write_text(meta_text)

        entries = list(loop_transcript.subagent_entries(folder))

        self.assertEqual(entries, [("a1", folder / "agent-a1.jsonl", {}),
                                   ("a2", folder / "agent-a2.jsonl", {"agentType": "coder"})])


class WrittenPathsTest(unittest.TestCase):
    def test_write_edit_multiedit_and_notebook_edit_paths_are_collected_and_bash_is_ignored(self):
        calls = [
            ("Write", {"file_path": "/r/a.py"}),
            ("Edit", {"file_path": "/r/b.py"}),
            ("MultiEdit", {"file_path": "/r/g.py"}),
            ("NotebookEdit", {"notebook_path": "/r/c.ipynb"}),
            ("NotebookEdit", {"file_path": "/r/d.ipynb"}),
            ("Bash", {"command": "echo hi > /r/e.py", "file_path": "/r/f.py"}),
        ]
        with tempfile.TemporaryDirectory() as folder:
            transcript = os.path.join(folder, "agent-a1.jsonl")
            with open(transcript, "w", encoding="utf-8") as fh:
                for name, tool_input in calls:
                    block = {"type": "tool_use", "name": name, "input": tool_input}
                    fh.write(json.dumps({"message": {"content": [block]}}) + "\n")

            written = loop_transcript.written_paths(transcript)

        self.assertEqual(written, {"/r/a.py", "/r/b.py", "/r/g.py", "/r/c.ipynb", "/r/d.ipynb"})

    def test_since_keeps_only_writes_whose_record_timestamp_is_later_and_drops_unparsable_ones(self):
        rows = [
            ("/r/before.py", "2026-01-01T00:00:00.000Z"),
            ("/r/after.py", "2026-01-01T00:00:20.500Z"),
            ("/r/offset.py", "2026-01-01T02:00:30+02:00"),
            ("/r/missing.py", None),
            ("/r/garbled.py", "yesterday"),
            ("/r/number.py", 1767225620),
        ]
        since = 1767225610  # 2026-01-01T00:00:10Z
        with tempfile.TemporaryDirectory() as folder:
            transcript = os.path.join(folder, "session.jsonl")
            with open(transcript, "w", encoding="utf-8") as fh:
                for edited, timestamp in rows:
                    block = {"type": "tool_use", "name": "Edit", "input": {"file_path": edited}}
                    record = {"message": {"content": [block]}}
                    if timestamp is not None:
                        record["timestamp"] = timestamp
                    fh.write(json.dumps(record) + "\n")

            written = loop_transcript.written_paths(transcript, since=since)

        self.assertEqual(written, {"/r/after.py", "/r/offset.py"})

    def test_succeeded_only_drops_a_write_whose_result_is_an_error_and_keeps_one_with_no_result(self):
        def use(tool_use_id, name, path):
            block = {"type": "tool_use", "id": tool_use_id, "name": name, "input": {"file_path": path}}
            return {"type": "assistant", "message": {"content": [block]}}

        def result(tool_use_id, is_error):
            block = {"type": "tool_result", "tool_use_id": tool_use_id, "content": "x", "is_error": is_error}
            return {"type": "user", "message": {"content": [block]}}

        records = [use("t1", "Write", "/r/refused.py"), result("t1", True),
                   use("t2", "Edit", "/r/done.py"), result("t2", False),
                   use("t3", "Write", "/r/cut_off.py")]
        with tempfile.TemporaryDirectory() as folder:
            transcript = os.path.join(folder, "session.jsonl")
            with open(transcript, "w", encoding="utf-8") as fh:
                for record in records:
                    fh.write(json.dumps(record) + "\n")

            everything = loop_transcript.written_paths(transcript)
            succeeded = loop_transcript.written_paths(transcript, succeeded_only=True)

        self.assertEqual(everything, {"/r/refused.py", "/r/done.py", "/r/cut_off.py"})
        self.assertEqual(succeeded, {"/r/done.py", "/r/cut_off.py"})


if __name__ == "__main__":
    unittest.main()
