"""Checks for lib/session_edits.py: the Edit and Write calls of a session transcript, and their replay."""
import json
import pathlib
import sys
import tempfile
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import session_edits


def tool_use(use_id, name, tool_input):
    return {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": use_id, "name": name,
                                                           "input": tool_input}]}}


def tool_result(use_id, is_error):
    return {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": use_id, "content": "x",
                                                      "is_error": is_error}]}}


class SessionEditsTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = pathlib.Path(folder.name).resolve() / "repo"
        self.root.mkdir()
        self.transcript = pathlib.Path(folder.name) / "session.jsonl"

    def write_transcript(self, rows):
        self.transcript.write_text("".join(json.dumps(row) + "\n" for row in rows) + "not json\n")

    def test_the_writes_that_did_not_fail_are_listed_per_file_in_call_order(self):
        notes = str(self.root / "notes.py")
        self.write_transcript([
            tool_use("1", "Write", {"file_path": notes, "content": "a = 1\n"}),
            tool_result("1", False),
            tool_use("2", "Edit", {"file_path": notes, "old_string": "1", "new_string": "2"}),
            tool_result("2", True),
            tool_use("3", "Edit", {"file_path": notes, "old_string": "a", "new_string": "b", "replace_all": False}),
            tool_use("4", "Edit", {"file_path": "/elsewhere/x.py", "old_string": "a", "new_string": "b"}),
            tool_use("5", "Bash", {"command": "echo > notes.py"}),
        ])

        writes = session_edits.file_writes(self.transcript, self.root)

        self.assertEqual(list(writes), ["notes.py"])
        self.assertEqual([write["tool"] for write in writes["notes.py"]], ["Write", "Edit"])
        self.assertEqual(session_edits.replayed_text("old\n", writes["notes.py"]), "b = 1\n")

    def test_an_edit_whose_old_string_is_gone_or_whose_shape_is_unknown_does_not_replay(self):
        cases = [
            ("old string gone", {"tool": "Edit", "file_path": "f", "old_string": "zzz", "new_string": "y"}),
            ("unknown field", {"tool": "Edit", "file_path": "f", "old_string": "a", "new_str": "y"}),
        ]
        for label, write in cases:
            with self.subTest(label), self.assertRaises(session_edits.ReplayError):
                session_edits.replayed_text("a\n", [write])

    def test_replace_all_replaces_every_occurrence(self):
        write = {"tool": "Edit", "file_path": "f", "old_string": "a", "new_string": "b", "replace_all": True}

        self.assertEqual(session_edits.replayed_text("a a\n", [write]), "b b\n")


if __name__ == "__main__":
    unittest.main()
