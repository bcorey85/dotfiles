"""lib/lane_entries.py: the lane file grammar and its writes."""
import json
import os
import pathlib
import sys
import tempfile
import unittest
import unittest.mock

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import lane_entries


class LaneEntriesTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = pathlib.Path(temp.name).resolve()
        state_env = unittest.mock.patch.dict(os.environ, {"XDG_STATE_HOME": str(self.root / "state")})
        state_env.start()
        self.addCleanup(state_env.stop)

    def make_worktree(self, name):
        worktree = self.root / name
        worktree.mkdir(exist_ok=True)
        return str(worktree)

    def add(self, name, worktree=None, brief="do the work"):
        worktree = worktree or self.make_worktree(name)
        return lane_entries.add_entry(name, worktree, str(self.root / "main"), f"branch-{name}", brief, "boss")

    def write_raw(self, name, text):
        lane_entries.lanes_dir().mkdir(parents=True, exist_ok=True)
        file = lane_entries.lanes_dir() / f"{name}.json"
        file.write_text(text)
        return file

    def good_entry(self, name="one"):
        return {"name": name, "worktree": str(self.root), "main_checkout": str(self.root), "branch": "b",
                "brief": "x", "session_id": "", "reports_to": "", "started_at": "2026-11-22T10:00:00+00:00"}

    def test_the_lanes_dir_follows_xdg_state_home_else_the_home_state_folder(self):
        self.assertEqual(self.root / "state" / "herdr-lanes", lane_entries.lanes_dir())
        with unittest.mock.patch.dict(os.environ, {"XDG_STATE_HOME": "", "HOME": str(self.root)}):
            self.assertEqual(self.root / ".local" / "state" / "herdr-lanes", lane_entries.lanes_dir())

    def test_an_added_entry_is_read_back_listed_sorted_and_removed(self):
        self.add("zeta")
        added = self.add("alpha")
        self.assertEqual("", added["session_id"])
        self.assertEqual(added, lane_entries.entry("alpha"))
        self.assertEqual(["alpha", "zeta"], [lane["name"] for lane in lane_entries.all_entries()])
        removed = lane_entries.remove_entry("alpha")
        self.assertEqual(added, removed)
        self.assertIsNone(lane_entries.entry("alpha"))
        self.assertEqual(["zeta"], [lane["name"] for lane in lane_entries.all_entries()])

    def test_with_no_lanes_folder_the_list_is_empty_and_an_entry_is_none(self):
        self.assertEqual([], lane_entries.all_entries())
        self.assertIsNone(lane_entries.entry("none"))

    def test_remove_and_set_session_of_a_missing_entry_raise(self):
        with self.assertRaises(lane_entries.LaneNotFoundError):
            lane_entries.remove_entry("none")
        with self.assertRaises(lane_entries.LaneNotFoundError):
            lane_entries.set_session("none", "sid")

    def test_set_session_reports_whether_anything_changed_and_keeps_the_brief_unless_given_one(self):
        self.add("one")
        self.assertTrue(lane_entries.set_session("one", "sid-1"))
        self.assertFalse(lane_entries.set_session("one", "sid-1"))
        self.assertEqual("do the work", lane_entries.entry("one")["brief"])
        self.assertTrue(lane_entries.set_session("one", "sid-1", brief="phase two"))
        self.assertFalse(lane_entries.set_session("one", "sid-1", brief="phase two"))
        self.assertEqual("phase two", lane_entries.entry("one")["brief"])
        self.assertEqual("sid-1", lane_entries.entry("one")["session_id"])

    def test_an_entry_with_a_live_worktree_is_refused_and_one_with_a_gone_worktree_is_replaced(self):
        first = self.add("one")
        with self.assertRaises(lane_entries.LaneExistsError):
            self.add("one", brief="other")
        self.assertEqual("do the work", lane_entries.entry("one")["brief"])
        pathlib.Path(first["worktree"]).rmdir()
        replaced = self.add("one", worktree=str(self.root / "new-place"), brief="fresh")
        self.assertEqual("fresh", lane_entries.entry("one")["brief"])
        self.assertEqual(replaced["worktree"], lane_entries.entry("one")["worktree"])

    def test_the_entry_containing_a_path_is_found_for_a_nested_path_and_not_for_an_outside_one(self):
        added = self.add("one")
        nested = pathlib.Path(added["worktree"]) / "a" / "b"
        nested.mkdir(parents=True)
        self.add("two")
        self.assertEqual("one", lane_entries.entry_containing(nested)["name"])
        self.assertEqual("one", lane_entries.entry_containing(added["worktree"])["name"])
        self.assertIsNone(lane_entries.entry_containing(self.root / "main"))
        self.assertIsNone(lane_entries.entry_containing(self.root / "one-sibling"))

    def test_the_entry_containing_a_path_resolves_symlinks_on_both_sides(self):
        added = self.add("one")
        link = self.root / "link"
        link.symlink_to(added["worktree"])
        self.assertEqual("one", lane_entries.entry_containing(link / "a")["name"])

        real = self.root / "real"
        real.mkdir()
        stored_link = self.root / "stored-link"
        stored_link.symlink_to(real)
        self.add("two", worktree=str(stored_link))
        self.assertEqual("two", lane_entries.entry_containing(real / "a")["name"])

    def test_an_unreadable_lanes_folder_raises_and_a_missing_one_is_empty(self):
        self.assertEqual([], lane_entries.entry_files())
        self.add("one")
        folder = lane_entries.lanes_dir()
        folder.chmod(0)
        self.addCleanup(folder.chmod, 0o755)
        if os.access(folder, os.R_OK):
            self.skipTest("folder permissions do not bind this user")
        with self.assertRaises(lane_entries.LaneFileError) as raised:
            lane_entries.all_entries()
        self.assertEqual("(folder)", raised.exception.field)

    def test_each_bad_shape_raises_naming_the_file_and_the_field(self):
        wrong_type = dict(self.good_entry(), branch=7)
        extra_key = dict(self.good_entry(), surprise="x")
        missing_key = self.good_entry()
        del missing_key["brief"]
        cases = [
            ("missing key", "one", json.dumps(missing_key), "brief"),
            ("extra key", "one", json.dumps(extra_key), "surprise"),
            ("wrong type", "one", json.dumps(wrong_type), "branch"),
            ("stem mismatch", "other", json.dumps(self.good_entry("one")), "name"),
            ("relative worktree", "one", json.dumps(dict(self.good_entry(), worktree="rel/dir")), "worktree"),
            ("started_at without offset", "one", json.dumps(dict(self.good_entry(), started_at="2026-11-22T10:00:00")),
             "started_at"),
            ("started_at impossible date", "one",
             json.dumps(dict(self.good_entry(), started_at="2026-13-40T10:00:00+00:00")), "started_at"),
            ("started_at trailing newline", "one",
             json.dumps(dict(self.good_entry(), started_at="2026-11-22T10:00:00+00:00\n")), "started_at"),
            ("name trailing newline", "one", json.dumps(self.good_entry("one\n")), "name"),
            ("invalid JSON", "one", "{not json", "(file)"),
            ("not an object", "one", "[]", "(file)"),
        ]
        for label, stem, text, field in cases:
            with self.subTest(label):
                file = self.write_raw(stem, text)
                with self.assertRaises(lane_entries.LaneFileError) as raised:
                    lane_entries.read_entry(file)
                self.assertEqual(field, raised.exception.field)
                self.assertEqual(file, raised.exception.file)
                self.assertIn(str(file), str(raised.exception))
                self.assertIn(f"field {field}", str(raised.exception))

    def test_a_malformed_file_stops_the_list_and_is_never_an_empty_list(self):
        self.add("one")
        self.write_raw("bad", "{")
        with self.assertRaises(lane_entries.LaneFileError):
            lane_entries.all_entries()

    def test_an_invalid_lane_name_is_refused_before_any_file_is_made(self):
        for name in ("../escape", "", ".hidden", "a/b", "foo\n"):
            with self.subTest(name):
                with self.assertRaises(lane_entries.LaneFileError) as raised:
                    self.add(name, worktree=str(self.root))
                self.assertEqual("name", raised.exception.field)
        self.assertEqual([], lane_entries.entry_files())

    def test_a_hostile_name_never_reaches_a_file_outside_the_lanes_folder(self):
        victim = self.root / "state" / "victim.json"
        victim.parent.mkdir(parents=True)
        victim.write_text("keep")
        calls = (
            lambda: lane_entries.remove_entry("../victim"),
            lambda: lane_entries.entry("../victim"),
            lambda: lane_entries.set_session("../victim", "s"),
        )
        for call in calls:
            with self.assertRaises(lane_entries.LaneFileError) as raised:
                call()
            self.assertEqual("name", raised.exception.field)
        self.assertTrue(victim.exists())

    def test_a_missing_file_raises_file_not_found_and_a_non_utf8_file_is_a_bad_file(self):
        with self.assertRaises(FileNotFoundError):
            lane_entries.read_entry(self.root / "absent.json")
        lane_entries.lanes_dir().mkdir(parents=True)
        binary = lane_entries.lanes_dir() / "one.json"
        binary.write_bytes(b"\xff\xfe")
        with self.assertRaises(lane_entries.LaneFileError) as raised:
            lane_entries.read_entry(binary)
        self.assertEqual("(file)", raised.exception.field)

    def test_a_directory_named_like_a_lane_file_is_a_bad_file(self):
        folder = lane_entries.lanes_dir() / "dir.json"
        folder.mkdir(parents=True)
        with self.assertRaises(lane_entries.LaneFileError) as raised:
            lane_entries.read_entry(folder)
        self.assertEqual("(file)", raised.exception.field)
        self.assertIn("a readable file", raised.exception.expected)
        with self.assertRaises(lane_entries.LaneFileError):
            lane_entries.all_entries()

    def test_a_named_missing_file_is_a_bad_file_with_the_system_message(self):
        with self.assertRaises(lane_entries.LaneFileError) as raised:
            lane_entries.read_named_entry(self.root / "absent.json")
        self.assertEqual("(file)", raised.exception.field)
        self.assertEqual("a readable file (No such file or directory)", raised.exception.expected)

    def test_a_file_removed_after_the_folder_is_listed_is_skipped(self):
        self.add("one")
        self.add("two")
        gone = lane_entries.lanes_dir() / "one.json"
        real_read = lane_entries.read_entry

        def read_after_removal(file):
            gone.unlink(missing_ok=True)
            return real_read(file)

        with unittest.mock.patch.object(lane_entries, "read_entry", read_after_removal):
            names = [lane["name"] for lane in lane_entries.all_entries()]
        self.assertEqual(["two"], names)

    def test_an_empty_brief_is_refused(self):
        with self.assertRaises(lane_entries.LaneFileError) as raised:
            self.add("one", brief="")
        self.assertEqual("brief", raised.exception.field)
        self.assertIsNone(lane_entries.entry("one"))

    def test_set_session_with_an_empty_brief_is_refused_and_keeps_the_stored_brief(self):
        self.add("one")
        with self.assertRaises(lane_entries.LaneFileError) as raised:
            lane_entries.set_session("one", "sid", brief="")
        self.assertEqual("brief", raised.exception.field)
        self.assertEqual("do the work", lane_entries.entry("one")["brief"])


if __name__ == "__main__":
    unittest.main()
