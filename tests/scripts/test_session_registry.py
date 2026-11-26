"""lib/session_registry.py: the config folders and the live-session rows."""
import json
import os
import pathlib
import sys
import tempfile
import unittest
import unittest.mock

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import session_registry


class SessionRegistryTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = pathlib.Path(temp.name)
        (self.home / "sessions").mkdir()
        config_env = unittest.mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.home)})
        config_env.start()
        self.addCleanup(config_env.stop)

    def test_a_holder_is_labelled_by_name_then_session_id_then_pid(self):
        self.assertEqual(session_registry.holder_label({"name": "n", "sessionId": "s", "pid": 1}), "n")
        self.assertEqual(session_registry.holder_label({"sessionId": "s", "pid": 1}), "s")
        self.assertEqual(session_registry.holder_label({"pid": 1}), "pid 1")

    def register(self, name, session_id, pid, file_name):
        row = {"pid": pid, "name": name, "sessionId": session_id}
        (self.home / "sessions" / file_name).write_text(json.dumps(row))

    def test_the_folders_follow_the_config_dir_override_else_the_home_claude_folder(self):
        with tempfile.TemporaryDirectory() as fake_home:
            with unittest.mock.patch.dict(os.environ, {"HOME": fake_home, "CLAUDE_CONFIG_DIR": "/elsewhere/config"}):
                self.assertEqual(session_registry.sessions_dir(), pathlib.Path("/elsewhere/config/sessions"))
                self.assertEqual(session_registry.projects_dir(), pathlib.Path("/elsewhere/config/projects"))
            with unittest.mock.patch.dict(os.environ, {"HOME": fake_home, "CLAUDE_CONFIG_DIR": ""}):
                self.assertEqual(session_registry.sessions_dir(), pathlib.Path(fake_home) / ".claude" / "sessions")
                self.assertEqual(session_registry.projects_dir(), pathlib.Path(fake_home) / ".claude" / "projects")

    def test_a_row_with_no_name_session_id_or_pid_still_gets_a_label(self):
        self.assertEqual(session_registry.holder_label({}), "unknown session")

    def test_a_session_display_name_comes_from_the_live_row_only(self):
        self.register("lane-one", "sid-live", os.getpid(), "1.json")
        self.register("lane-dead", "sid-dead", 10**30, "2.json")
        self.assertEqual("lane-one", session_registry.session_display_name("sid-live"))
        self.assertIsNone(session_registry.session_display_name("sid-dead"))
        self.assertIsNone(session_registry.session_display_name("sid-none"))

    def register_in(self, session_id, cwd, file_name, pid=None):
        row = {"pid": pid or os.getpid(), "name": "lane", "sessionId": session_id, "cwd": cwd}
        (self.home / "sessions" / file_name).write_text(json.dumps(row))

    def test_another_live_session_inside_the_folder_is_found_and_the_own_session_is_not(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = pathlib.Path(folder).resolve()
            (repo / "sub").mkdir()
            self.register_in("own", str(repo), "1.json")
            self.assertEqual([], session_registry.other_live_sessions_in(repo, "own"))
            self.register_in("other", str(repo / "sub"), "2.json")
            found = session_registry.other_live_sessions_in(repo, "own")
            self.assertEqual(["other"], [row["sessionId"] for row in found])

    def test_every_other_live_session_inside_the_folder_is_found_in_registry_order(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = pathlib.Path(folder).resolve()
            self.register_in("own", str(repo), "1.json")
            self.register_in("first", str(repo), "2.json")
            self.register_in("second", str(repo / "sub"), "3.json")
            self.register_in("elsewhere", str(repo.parent), "4.json")
            found = session_registry.other_live_sessions_in(repo, "own")
            self.assertEqual(["first", "second"], [row["sessionId"] for row in found])

    def test_a_session_transcript_is_found_under_any_project_and_a_missing_one_is_none(self):
        (self.home / "projects" / "proj").mkdir(parents=True)
        transcript = self.home / "projects" / "proj" / "sid.jsonl"
        transcript.write_text("")
        self.assertEqual(transcript, session_registry.session_transcript("sid"))
        self.assertIsNone(session_registry.session_transcript("none"))
        self.assertIsNone(session_registry.session_transcript(None))

    def test_a_session_transcript_in_several_projects_is_the_first_in_sorted_order(self):
        for project in ("b", "a"):
            (self.home / "projects" / project).mkdir(parents=True)
            (self.home / "projects" / project / "sid.jsonl").write_text("")
        self.assertEqual(self.home / "projects" / "a" / "sid.jsonl", session_registry.session_transcript("sid"))

    def test_every_transcript_match_of_a_session_is_returned_sorted(self):
        for project in ("b", "a"):
            (self.home / "projects" / project).mkdir(parents=True)
            (self.home / "projects" / project / "sid.jsonl").write_text("")
        expected = [self.home / "projects" / "a" / "sid.jsonl", self.home / "projects" / "b" / "sid.jsonl"]
        self.assertEqual(expected, session_registry.session_transcript_matches("sid"))

    def test_a_session_outside_the_folder_a_dead_one_and_a_row_with_no_cwd_are_no_match(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = pathlib.Path(folder).resolve()
            self.register_in("elsewhere", str(repo.parent), "1.json")
            self.register_in("dead", str(repo), "2.json", pid=10**30)
            (self.home / "sessions" / "3.json").write_text(
                json.dumps({"pid": os.getpid(), "sessionId": "no-cwd", "name": "x"}))
            self.assertEqual([], session_registry.other_live_sessions_in(repo, "own"))

    def test_a_row_is_found_by_name_only_while_its_pid_is_alive(self):
        self.register("lane-dead", "sid-dead", 10**30, "1.json")
        self.register("lane-live", "sid-live", os.getpid(), "2.json")
        self.assertEqual("sid-live", session_registry.row_for_name("lane-live")["sessionId"])
        self.assertIsNone(session_registry.row_for_name("lane-dead"))
        self.assertIsNone(session_registry.row_for_name("lane-absent"))

    def test_the_first_live_row_of_a_name_wins_and_a_dead_row_ahead_of_it_is_skipped(self):
        self.register("twin", "sid-dead", 10**30, "1.json")
        self.register("twin", "sid-first", os.getpid(), "2.json")
        self.register("twin", "sid-second", os.getpid(), "3.json")
        self.assertEqual("sid-first", session_registry.row_for_name("twin")["sessionId"])

    def test_a_row_is_found_by_session_id_only_while_its_pid_is_alive(self):
        self.register("twin", "sid-dead", 10**30, "1.json")
        self.register("twin", "sid-first", os.getpid(), "2.json")
        self.register("twin", "sid-second", os.getpid(), "3.json")
        self.assertEqual("sid-second", session_registry.row_for_session_id("sid-second")["sessionId"])
        self.assertIsNone(session_registry.row_for_session_id("sid-dead"))
        self.assertIsNone(session_registry.row_for_session_id("sid-absent"))

    def test_a_live_row_with_an_empty_name_gives_no_display_name(self):
        self.register("", "sid-unnamed", os.getpid(), "3.json")
        self.assertIsNone(session_registry.session_display_name("sid-unnamed"))
