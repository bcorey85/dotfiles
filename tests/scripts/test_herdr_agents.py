"""lib/herdr_agents.py: the herdr agent list as plain dicts, and which agents run inside a folder."""
import os
import pathlib
import sys
import tempfile
import unittest
import unittest.mock

import toolkit_paths
from stubs import write_stub

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import herdr_agents


class HerdrAgentsTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = pathlib.Path(temp.name).resolve()
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        path_env = unittest.mock.patch.dict(os.environ, {"PATH": f"{self.bin_dir}:{os.environ['PATH']}"})
        path_env.start()
        self.addCleanup(path_env.stop)

    def stub_herdr_api(self, body):
        write_stub(self.bin_dir / "herdr-api", body)

    def test_claude_agents_keeps_only_claude_agents(self):
        self.stub_herdr_api("""echo '{"result":{"agents":[{"agent":"claude","pane_id":"p1"},
            {"agent":"codex","pane_id":"p2"}]}}'""")

        self.assertEqual([{"agent": "claude", "pane_id": "p1"}], herdr_agents.claude_agents())

    def test_each_failed_call_raises_naming_the_call(self):
        cases = {
            "a non-zero exit": ("exit 1", "herdr-api agent list failed with exit 1"),
            "text that is not JSON": ("echo nope", "herdr-api agent list printed no JSON"),
            "JSON that is not an object": ("echo '[]'", "herdr-api agent list printed no JSON object"),
            "a reply with no agents list": ("echo '{\"result\":{}}'", "herdr-api agent list printed no agents list"),
        }
        for label, (body, message) in cases.items():
            with self.subTest(label):
                self.stub_herdr_api(body)
                with self.assertRaises(herdr_agents.PaneCallError) as raised:
                    herdr_agents.claude_agents()
                self.assertIn(message, str(raised.exception))

    def test_a_missing_herdr_api_raises_naming_the_call(self):
        empty_path = {"PATH": str(self.root / "empty")}
        with unittest.mock.patch.dict(os.environ, empty_path), self.assertRaises(herdr_agents.PaneCallError) as raised:
            herdr_agents.herdr_reply(["pane", "current"])
        self.assertIn("herdr-api pane current failed", str(raised.exception))

    def test_agents_in_matches_the_folder_itself_a_nested_folder_and_a_symlink_to_it(self):
        folder = self.root / "lane"
        (folder / "deeper").mkdir(parents=True)
        link = self.root / "link"
        link.symlink_to(folder)
        agents = [{"pane_id": "same", "cwd": str(folder)},
                  {"pane_id": "nested", "cwd": str(folder / "deeper")},
                  {"pane_id": "linked", "cwd": str(link)}]

        inside = herdr_agents.agents_in(folder, agents)

        self.assertEqual(["same", "nested", "linked"], [agent["pane_id"] for agent in inside])

    def test_agents_in_skips_a_sibling_with_a_shared_prefix_and_an_agent_without_a_usable_cwd(self):
        folder = self.root / "lane"
        folder.mkdir()
        sibling = self.root / "lane-2"
        sibling.mkdir()
        agents = [{"pane_id": "sibling", "cwd": str(sibling)},
                  {"pane_id": "none"},
                  {"pane_id": "null", "cwd": None},
                  {"pane_id": "empty", "cwd": ""}]

        with unittest.mock.patch("os.getcwd", return_value=str(folder)):
            inside = herdr_agents.agents_in(folder, agents)

        self.assertEqual([], inside)


if __name__ == "__main__":
    unittest.main()
