"""Tests for review_loop_outside_writes.py: which paths a coder wrote count as outside the reviewed repo."""
import json
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
import review_loop_outside_writes as outside


class OutsideWritesTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = pathlib.Path(tmp.name).resolve()
        self.repo = self.base / "repo"
        self.repo.mkdir()
        self.out = self.base / "out"
        self.out.mkdir()
        outside.OUTSIDE_WRITE_FAULTS.clear()
        outside.PASS_OUTSIDE_WRITES.clear()
        self.addCleanup(outside.OUTSIDE_WRITE_FAULTS.clear)
        self.addCleanup(outside.PASS_OUTSIDE_WRITES.clear)

    def writes(self, written, roots=()):
        return outside.outside_writes(self.repo, written, list(roots))

    def test_a_path_in_another_folder_is_outside(self):
        other = self.base / "other" / "tool.py"

        self.assertEqual(self.writes([str(other)]), [str(other)])

    def test_a_repo_path_and_a_relative_path_are_inside(self):
        written = [str(self.repo / "app.py"), "pkg/app.py"]

        self.assertEqual(self.writes(written), [])

    def scratch_roots_with_temp(self, temp_folder):
        with mock.patch.object(outside.hook_input, "temp_roots", return_value=[str(temp_folder)]), \
                mock.patch.object(outside.hook_input, "session_temp_roots", return_value=[]):
            return outside.scratch_roots(self.repo, self.out)

    def test_a_temp_path_is_scratch_when_the_repo_is_not_under_temp(self):
        (self.base / "temp").mkdir()
        roots = self.scratch_roots_with_temp(self.base / "temp")
        scratch_file = self.base / "temp" / "note.txt"

        self.assertEqual(self.writes([str(scratch_file)], roots), [])

    def test_temp_is_not_scratch_when_the_repo_lives_under_it(self):
        roots = self.scratch_roots_with_temp(self.base)
        sibling = self.base / "sibling" / "tool.py"

        self.assertNotIn(self.base, roots)
        self.assertEqual(self.writes([str(sibling)], roots), [str(sibling)])

    def test_a_session_scratchpad_root_is_scratch(self):
        pad = self.base / "claude-1000"
        pad.mkdir()
        with mock.patch.object(outside.hook_input, "temp_roots", return_value=[]), \
                mock.patch.object(outside.hook_input, "session_temp_roots", return_value=[str(pad)]):
            roots = outside.scratch_roots(self.repo, self.out)

        self.assertEqual(self.writes([str(pad / "proj" / "s" / "x.txt")], roots), [])

    def test_the_out_dir_is_scratch(self):
        roots = outside.scratch_roots(self.repo, self.out)

        self.assertIn(self.out, roots)
        self.assertEqual(self.writes([str(self.out / "notes.txt")], roots), [])

    def test_a_symlink_into_another_checkout_resolves_outside(self):
        (self.base / "sibling" / "bin").mkdir(parents=True)
        (self.base / "link").symlink_to(self.base / "sibling")
        target = self.base / "sibling" / "bin" / "tool.py"

        self.assertEqual(self.writes([str(self.base / "link" / "bin" / "tool.py")]), [str(target)])

    def test_a_relative_name_that_escapes_the_repo_is_outside(self):
        target = self.base / "sibling" / "tool.py"

        self.assertEqual(self.writes(["../sibling/tool.py"]), [str(target)])

    def test_a_symlink_inside_the_repo_that_points_out_resolves_outside(self):
        (self.base / "sibling").mkdir()
        (self.repo / "link").symlink_to(self.base / "sibling")
        target = self.base / "sibling" / "tool.py"

        self.assertEqual(self.writes([str(self.repo / "link" / "tool.py")]), [str(target)])

    def test_no_transcript_notes_a_fault_and_records_nothing(self):
        with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.base / "config")}):
            outside.record_pass_writes("coder1", self.repo, self.out, "s-missing")

        self.assertEqual(outside.PASS_OUTSIDE_WRITES, {})
        [note] = outside.OUTSIDE_WRITE_FAULTS
        self.assertIn("coder1: the outside-write check could not run", note)
        self.assertIn("'s-missing'", note)

    def test_an_empty_session_id_notes_a_fault(self):
        with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.base / "config")}):
            outside.record_pass_writes("coder1", self.repo, self.out, "")

        self.assertEqual(outside.PASS_OUTSIDE_WRITES, {})
        self.assertEqual(len(outside.OUTSIDE_WRITE_FAULTS), 1)

    def test_a_transcript_with_an_outside_write_records_it_and_notes_it(self):
        projects = self.base / "config" / "projects" / "p"
        projects.mkdir(parents=True)
        other = self.base / "other" / "tool.py"
        block = {"type": "tool_use", "name": "Write", "input": {"file_path": str(other)}}
        record = {"type": "assistant", "message": {"content": [block]}}
        (projects / "s-1.jsonl").write_text(json.dumps(record) + "\n")

        with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.base / "config")}):
            outside.record_pass_writes("coder1", self.repo, self.out, "s-1")

        self.assertEqual(outside.PASS_OUTSIDE_WRITES, {"coder1": [str(other)]})
        self.assertEqual(outside.OUTSIDE_WRITE_FAULTS,
                         [f"coder1 wrote outside the reviewed repo (not put back): {other}"])

    def write_transcript(self, session, paths):
        projects = self.base / "config" / "projects" / "p"
        projects.mkdir(parents=True, exist_ok=True)
        records = []
        for name in paths:
            block = {"type": "tool_use", "name": "Write", "input": {"file_path": name}}
            records.append(json.dumps({"type": "assistant", "message": {"content": [block]}}))
        (projects / f"{session}.jsonl").write_text("\n".join(records) + "\n")

    def test_a_transcript_that_cannot_be_read_notes_a_fault_and_records_nothing(self):
        self.write_transcript("s-2", [])

        with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.base / "config")}), \
                mock.patch.object(outside.loop_transcript, "written_paths", side_effect=OSError("denied")):
            outside.record_pass_writes("coder1", self.repo, self.out, "s-2")

        self.assertEqual(outside.PASS_OUTSIDE_WRITES, {})
        [note] = outside.OUTSIDE_WRITE_FAULTS
        self.assertIn("could not run", note)

    def test_a_transcript_with_only_repo_and_scratch_writes_records_none_and_notes_nothing(self):
        self.write_transcript("s-3", [str(self.repo / "app.py"), str(self.out / "x")])

        with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.base / "config")}):
            outside.record_pass_writes("coder1", self.repo, self.out, "s-3")

        self.assertEqual(outside.PASS_OUTSIDE_WRITES, {"coder1": []})
        self.assertEqual(outside.OUTSIDE_WRITE_FAULTS, [])


if __name__ == "__main__":
    unittest.main()
