"""scripts/.local/lib/lane_list.py: the error branches of the lane list reader."""
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

from stubs import SCRIPT_LIB_DIR

sys.path.insert(0, str(SCRIPT_LIB_DIR))
import lane_list


class LaneListTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = pathlib.Path(scratch.name)

    def use_tools_file(self, text):
        tools_file = self.root / "toolkit-tools.bash"
        tools_file.write_text(text)
        patcher = mock.patch.object(lane_list, "TOOLS_FILE", tools_file)
        patcher.start()
        self.addCleanup(patcher.stop)

    def use_cli(self, source):
        cli = self.root / "cli.py"
        cli.write_text(source)
        self.use_tools_file(f'lanes_cli="{cli}"\n')

    def test_a_tools_file_that_fails_raises(self):
        self.use_tools_file("exit 3\n")

        with self.assertRaisesRegex(lane_list.LaneListError, "cannot read lanes_cli"):
            lane_list.lanes_cli_path(10)

    def test_a_tools_file_with_an_empty_lanes_cli_raises(self):
        self.use_tools_file('lanes_cli=""\n')

        with self.assertRaisesRegex(lane_list.LaneListError, "cannot read lanes_cli.*empty"):
            lane_list.lanes_cli_path(10)

    def test_a_cli_that_exits_non_zero_raises_with_its_stderr(self):
        self.use_cli("import sys\nprint('boom', file=sys.stderr)\nsys.exit(2)\n")

        with self.assertRaisesRegex(lane_list.LaneListError, "lanes list failed: boom"):
            lane_list.read_lane_entries(10)

    def test_an_answer_that_is_not_json_raises(self):
        self.use_cli("print('not json')\n")

        with self.assertRaisesRegex(lane_list.LaneListError, "unexpected answer"):
            lane_list.read_lane_entries(10)

    def test_an_answer_without_a_lanes_key_raises(self):
        self.use_cli("print('{\"other\": []}')\n")

        with self.assertRaisesRegex(lane_list.LaneListError, "unexpected answer"):
            lane_list.read_lane_entries(10)

    def test_a_good_answer_returns_the_entries(self):
        self.use_cli("print('{\"lanes\": [{\"name\": \"a\"}]}')\n")

        self.assertEqual(lane_list.read_lane_entries(10), [{"name": "a"}])


if __name__ == "__main__":
    unittest.main()
