"""Checks for shell_steps.placed_commands: the folder each simple command runs in."""
import sys
import unittest
import unittest.mock

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import shell_steps


def placed(command, **options):
    return [(call.words, call.directory) for call in shell_steps.placed_commands(command, "/start", **options)]


class PlacedCommandsTest(unittest.TestCase):
    def test_moves_are_not_yielded_and_set_the_folder_of_later_commands(self):
        self.assertEqual(placed("cd x && ls; pushd y; ls; popd; ls"),
                         [(["ls"], "/start/x"), (["ls"], "/start/x/y"), (["ls"], "/start/x")])

    def test_a_group_cd_is_undone_where_the_group_closes(self):
        self.assertEqual(placed("(cd x; ls); ls"), [(["ls"], "/start/x"), (["ls"], "/start")])

    def test_a_container_call_is_peeled_only_when_asked(self):
        self.assertEqual(placed("docker exec c rm a"), [(["rm", "a"], "/start")])
        self.assertEqual(placed("docker exec c rm a", peel_containers=False),
                         [(["docker", "exec", "c", "rm", "a"], "/start")])

    def test_a_placed_command_keeps_the_step_the_words_before_wrappers_and_the_words_after(self):
        calls = list(shell_steps.placed_commands("timeout 5 rm a", "/start"))
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].step, "timeout 5 rm a")
        self.assertEqual(calls[0].simple_command, ["timeout", "5", "rm", "a"])
        self.assertEqual(calls[0].words, ["rm", "a"])

    def test_an_unclosed_quote_raises(self):
        with self.assertRaises(ValueError):
            placed("rm 'a")

    def test_skip_unread_leaves_out_the_bad_step_and_reads_on(self):
        with unittest.mock.patch("sys.stderr"):
            self.assertEqual(placed("echo 1 > x; ls", skip_unread=True), [(["ls"], "/start")])

    def test_skip_unread_with_a_cd_in_the_bad_step_makes_the_folder_unknown(self):
        with unittest.mock.patch("sys.stderr"):
            self.assertEqual(placed("cd x\\|y; ls", skip_unread=True), [(["ls"], None)])

    def test_a_skipped_step_still_opens_and_closes_its_group(self):
        with unittest.mock.patch("sys.stderr"):
            self.assertEqual(placed("(cd x; echo 1 > y); ls", skip_unread=True), [(["ls"], "/start")])
            self.assertEqual(placed("(echo 1 > y; cd x); ls", skip_unread=True), [(["ls"], "/start")])

    def test_cd_as_a_path_part_is_no_move(self):
        with unittest.mock.patch("sys.stderr"):
            self.assertEqual(placed("echo 1 > ./cd/y; ls", skip_unread=True), [(["ls"], "/start")])


if __name__ == "__main__":
    unittest.main()
