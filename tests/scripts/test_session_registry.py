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

    def test_a_session_display_name_comes_from_the_live_row_only(self):
        self.register("lane-one", "sid-live", os.getpid(), "1.json")
        self.register("lane-dead", "sid-dead", 10**30, "2.json")
        self.assertEqual("lane-one", session_registry.session_display_name("sid-live"))
        self.assertIsNone(session_registry.session_display_name("sid-dead"))
        self.assertIsNone(session_registry.session_display_name("sid-none"))

    def test_a_live_row_with_an_empty_name_gives_no_display_name(self):
        self.register("", "sid-unnamed", os.getpid(), "3.json")
        self.assertIsNone(session_registry.session_display_name("sid-unnamed"))
