import json
import os
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

    def test_a_torn_last_line_is_not_interrupted(self):
        self.write([interrupt_record()])
        with open(self.transcript, "a", encoding="utf-8") as fh:
            fh.write('{"type": "user", "mess')
        self.assertFalse(loop_transcript.agent_interrupted(self.transcript))

    def test_a_last_record_that_is_not_an_object_is_not_interrupted(self):
        self.write([interrupt_record(), ["not", "an", "object"]])
        self.assertFalse(loop_transcript.agent_interrupted(self.transcript))

    def test_an_empty_file_is_not_interrupted(self):
        self.write([])
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


if __name__ == "__main__":
    unittest.main()
