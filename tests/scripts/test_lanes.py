"""tools/lanes.py: the lane file command line, run as a subprocess."""
import contextlib
import importlib.util
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import textwrap
import unittest
import unittest.mock

import toolkit_paths

LANES_SCRIPT = pathlib.Path(os.environ.get("LANES_PATH") or toolkit_paths.TOOLS_DIR / "lanes.py")


class LanesCliTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = pathlib.Path(temp.name).resolve()
        self.lanes_dir = self.root / "state" / "herdr-lanes"
        self.env = dict(os.environ, XDG_STATE_HOME=str(self.root / "state"))

    def run_lanes(self, *args, stdin=""):
        return subprocess.run([sys.executable, str(LANES_SCRIPT), *args], input=stdin, capture_output=True,
                              text=True, env=self.env, timeout=60)

    def add(self, name, stdin="the brief"):
        worktree = self.root / name
        worktree.mkdir(exist_ok=True)
        return self.run_lanes("add", "--name", name, "--worktree", str(worktree), "--main-checkout",
                              str(self.root / "main"), "--branch", f"b-{name}", "--reports-to", "boss", stdin=stdin)

    def test_add_without_reports_to_stores_an_empty_string(self):
        worktree = self.root / "solo"
        worktree.mkdir()
        added = self.run_lanes("add", "--name", "solo", "--worktree", str(worktree), "--main-checkout",
                               str(self.root / "main"), "--branch", "b-solo", stdin="echo brief\n")
        self.assertEqual(0, added.returncode, added.stderr)
        entry = json.loads(added.stdout)
        self.assertEqual("", entry["reports_to"])
        self.assertEqual("echo brief", entry["brief"])

    def test_an_unwritable_state_folder_exits_2_not_1(self):
        self.lanes_dir.mkdir(parents=True)
        self.lanes_dir.chmod(0o500)
        self.addCleanup(self.lanes_dir.chmod, 0o755)
        if os.access(self.lanes_dir, os.W_OK):
            self.skipTest("folder permissions do not bind this user")
        result = self.run_lanes("set-session", "a", "sid")
        self.assertEqual(2, result.returncode, result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_an_add_that_hits_a_live_entry_exits_1_naming_the_lane_file(self):
        self.assertEqual(0, self.add("one").returncode)
        result = self.add("one")
        self.assertEqual(1, result.returncode, result.stderr)
        self.assertIn(f"lanes: lane one already exists with a live worktree ({self.lanes_dir / 'one.json'})",
                      result.stderr)

    def test_an_add_that_cannot_write_exits_2_naming_the_lane_file(self):
        (self.root / "state").write_text("a file where the state folder should be")
        result = self.add("one")
        self.assertEqual(2, result.returncode, result.stderr)
        self.assertIn(f"lanes: {self.lanes_dir / 'one.json'}: ", result.stderr)

    def test_every_verb_prints_its_json_and_a_lane_round_trips(self):
        added = self.add("one")
        self.assertEqual(0, added.returncode, added.stderr)
        entry = json.loads(added.stdout)
        self.assertEqual(("the brief", "", "boss"), (entry["brief"], entry["session_id"], entry["reports_to"]))

        got = json.loads(self.run_lanes("get", "one").stdout)
        self.assertEqual(entry, got["entry"])
        self.assertEqual({"entry": None}, json.loads(self.run_lanes("get", "none").stdout))

        containing = self.run_lanes("get", "--containing", str(self.root / "one" / "deeper"))
        self.assertEqual("one", json.loads(containing.stdout)["entry"]["name"])

        self.add("alpha")
        listed = json.loads(self.run_lanes("list").stdout)
        self.assertEqual(["alpha", "one"], [lane["name"] for lane in listed["lanes"]])

        changed = self.run_lanes("set-session", "one", "sid-1", "--brief-stdin", stdin="phase two")
        self.assertEqual({"changed": True}, json.loads(changed.stdout))
        again = self.run_lanes("set-session", "one", "sid-1", "--brief-stdin", stdin="phase two\n")
        self.assertEqual({"changed": False}, json.loads(again.stdout))
        stored = json.loads(self.run_lanes("get", "one").stdout)["entry"]
        self.assertEqual(("phase two", "sid-1"), (stored["brief"], stored["session_id"]))

        checked = self.run_lanes("check")
        self.assertEqual((0, {"checked": 2}), (checked.returncode, json.loads(checked.stdout)))

        removed = self.run_lanes("remove", "one")
        self.assertEqual(stored, json.loads(removed.stdout))
        self.assertEqual({"entry": None}, json.loads(self.run_lanes("get", "one").stdout))

    def test_add_exits_1_for_a_live_entry_and_set_session_and_remove_exit_1_for_no_entry(self):
        self.add("one")
        self.assertEqual(1, self.add("one").returncode)
        self.assertEqual(1, self.run_lanes("set-session", "none", "sid").returncode)
        self.assertEqual(1, self.run_lanes("remove", "none").returncode)

    def test_a_bad_lane_file_exits_2_naming_the_file_and_the_field(self):
        self.add("one")
        bad_file = self.lanes_dir / "bad.json"
        bad_file.write_text(json.dumps({"name": "bad"}))
        for args in (("list",), ("get", "bad"), ("check",), ("check", str(bad_file))):
            with self.subTest(args):
                result = self.run_lanes(*args)
                self.assertEqual(2, result.returncode)
                self.assertIn(str(bad_file), result.stderr)
                self.assertIn("field worktree: expected", result.stderr)

    def test_a_malformed_file_is_named_for_each_bad_shape(self):
        self.add("one")
        good = json.loads(self.run_lanes("get", "one").stdout)["entry"]
        shapes = {
            "extra": (dict(good, extra=1), "extra"),
            "type": (dict(good, branch=3), "branch"),
            "stem": (dict(good, name="other"), "name"),
            "json": ("{oops", "(file)"),
        }
        for label, (content, field) in shapes.items():
            with self.subTest(label):
                text = content if isinstance(content, str) else json.dumps(content)
                (self.lanes_dir / "one.json").write_text(text)
                result = self.run_lanes("get", "one")
                self.assertEqual(2, result.returncode)
                self.assertIn(f"lanes: {self.lanes_dir / 'one.json'}: field {field}: expected", result.stderr)

    def test_check_over_a_folder_with_one_bad_file_stops_on_it(self):
        self.add("one")
        self.add("two")
        (self.lanes_dir / "two.json").write_text("[]")
        result = self.run_lanes("check")
        self.assertEqual(2, result.returncode)
        self.assertIn(str(self.lanes_dir / "two.json"), result.stderr)
        self.assertEqual(0, self.run_lanes("check", str(self.lanes_dir / "one.json")).returncode)

    def test_a_hostile_name_exits_2_and_leaves_a_file_outside_the_folder(self):
        victim = self.root / "state" / "victim.json"
        victim.parent.mkdir(parents=True)
        victim.write_text("keep")
        for args in (("remove", "../victim"), ("get", "../victim")):
            with self.subTest(args):
                result = self.run_lanes(*args)
                self.assertEqual(2, result.returncode)
                self.assertIn("field name", result.stderr)
        self.assertTrue(victim.exists())

    def test_a_name_with_a_trailing_newline_is_refused_on_add(self):
        result = self.add("foo\n")
        self.assertEqual(2, result.returncode)
        self.assertIn("field name", result.stderr)

    def test_check_names_a_missing_file_and_a_non_utf8_file_with_exit_2(self):
        missing = self.root / "absent.json"
        result = self.run_lanes("check", str(missing))
        self.assertEqual(2, result.returncode)
        self.assertIn(f"lanes: {missing}: field (file): expected", result.stderr)
        binary = self.root / "binary.json"
        binary.write_bytes(b"\xff\xfe")
        result = self.run_lanes("check", str(binary))
        self.assertEqual(2, result.returncode)
        self.assertIn(f"lanes: {binary}: field (file): expected UTF-8 text", result.stderr)

    def test_check_over_a_directory_exits_2_naming_the_file(self):
        folder = self.root / "dir.json"
        folder.mkdir()
        result = self.run_lanes("check", str(folder))
        self.assertEqual(2, result.returncode)
        self.assertIn(f"lanes: {folder}: field (file): expected a readable file", result.stderr)

    def test_check_with_no_files_skips_a_file_removed_mid_walk_and_counts_only_files_read(self):
        self.assertEqual(0, self.add("one").returncode)
        self.assertEqual(0, self.add("two").returncode)
        gone = self.lanes_dir / "one.json"
        spec = importlib.util.spec_from_file_location("lanes_under_test", LANES_SCRIPT)
        lanes = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lanes)
        real_read = lanes.lane_entries.read_entry

        def read_after_removal(file):
            gone.unlink(missing_ok=True)
            return real_read(file)

        out = io.StringIO()
        with unittest.mock.patch.dict(os.environ, self.env), \
                unittest.mock.patch.object(lanes.lane_entries, "read_entry", read_after_removal), \
                contextlib.redirect_stdout(out):
            code = lanes.main(["lanes.py", "check"])
        self.assertEqual(0, code)
        self.assertEqual({"checked": 1}, json.loads(out.getvalue()))

    def test_an_empty_brief_on_stdin_exits_2_for_add_and_set_session(self):
        self.assertEqual(2, self.add("one", stdin="").returncode)
        self.add("two")
        result = self.run_lanes("set-session", "two", "sid", "--brief-stdin", stdin="")
        self.assertEqual(2, result.returncode)
        self.assertIn("field brief", result.stderr)

    def test_get_takes_a_name_or_containing_but_not_both_or_neither(self):
        self.assertEqual(2, self.run_lanes("get").returncode)
        self.assertEqual(2, self.run_lanes("get", "one", "--containing", "/x").returncode)

    def test_a_held_lock_exits_2_naming_the_lock(self):
        self.lanes_dir.mkdir(parents=True)
        lock_path = self.lanes_dir / "lanes.lock"
        holder_code = textwrap.dedent(f"""
            import sys, time
            sys.path.insert(0, {str(toolkit_paths.LIB_DIR)!r})
            import file_lock
            with file_lock.hold_exclusive({str(lock_path)!r}, 1):
                print("held", flush=True)
                time.sleep(30)
        """)
        holder = subprocess.Popen([sys.executable, "-c", holder_code], stdout=subprocess.PIPE, text=True)
        self.addCleanup(holder.wait)
        self.addCleanup(holder.kill)
        self.assertEqual("held", holder.stdout.readline().strip())

        result = self.add("one")
        self.assertEqual(2, result.returncode)
        lane_file = self.lanes_dir / "one.json"
        self.assertIn(f"lanes: {lane_file}: lock {lock_path} held for 10s", result.stderr)


if __name__ == "__main__":
    unittest.main()
