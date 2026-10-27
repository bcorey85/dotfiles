"""Checks for shell_statements.py: heredoc bodies are cut out of a command, and only a real heredoc starts one."""
import sys
import time
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))

from shell_statements import opens_shell_heredoc, strip_comments, strip_heredocs


class StripCommentsTest(unittest.TestCase):
    def test_an_apostrophe_in_a_comment_does_not_hide_the_next_comments(self):
        command = "ls # it's\nls # don't\nsed -i x f"

        self.assertEqual("ls \nls \nsed -i x f", strip_comments(command))

    def test_a_hash_inside_quotes_is_kept(self):
        self.assertEqual("echo '# a'", strip_comments("echo '# a'"))
        self.assertEqual('echo "x # y" ', strip_comments('echo "x # y" # z'))


class OpensShellHeredocTest(unittest.TestCase):
    def test_a_comment_with_an_apostrophe_after_the_opener_is_ignored(self):
        self.assertTrue(opens_shell_heredoc("bash <<'EOF' # it's"))

    def test_a_line_that_cannot_be_parsed_and_names_a_shell_counts_as_a_shell(self):
        self.assertTrue(opens_shell_heredoc("bash 'unclosed <<EOF"))

    def test_a_heredoc_into_cat_is_not_a_shell(self):
        self.assertFalse(opens_shell_heredoc("cat <<EOF"))

    def test_a_line_that_cannot_be_parsed_and_names_no_shell_is_not_a_shell(self):
        for line in ("cut -d'|' -f2 <<EOF", "awk -F'|' '{print $1}' <<EOF", "tr ';' ',' <<EOF"):
            self.assertFalse(opens_shell_heredoc(line), line)
        self.assertTrue(opens_shell_heredoc("echo '|'; bash <<EOF"))
        self.assertTrue(opens_shell_heredoc("cat x | /bin/sh -s ';' <<EOF"))

    def test_an_unparsed_line_with_a_shell_glued_to_the_heredoc_or_quoted_counts_as_a_shell(self):
        for line in ("/bin/bash<<EOF 'unclosed", "\"bash\" <<'EOF' 'unclosed", "'sh'<<EOF \"unclosed"):
            self.assertTrue(opens_shell_heredoc(line), line)

    def test_a_heredoc_inside_a_substitution_in_double_quotes_is_seen(self):
        command = "git commit -m \"$(cat <<'EOF'\nSupports 5\" screens\nEOF\n)\""

        self.assertEqual("git commit -m \"$(cat <<'EOF'\n)\"", strip_heredocs(command))


class StripHeredocsTest(unittest.TestCase):
    def test_the_body_and_terminator_are_dropped(self):
        cases = {
            "one body": ("cat <<EOF\nbody\nEOF\necho x", "cat <<EOF\necho x"),
            "quoted marker": ("cat <<'EOF'\nbody\nEOF\necho x", "cat <<'EOF'\necho x"),
            "dash marker with an indented terminator": ("cat <<-EOF\nbody\n\tEOF\necho x", "cat <<-EOF\necho x"),
            "two markers on one line": ("cat <<A <<B\na\nA\nb\nB\necho x", "cat <<A <<B\necho x"),
            "a body line that names the other marker": ("cat <<A <<B\nB\nA\nb\nB\necho x", "cat <<A <<B\necho x"),
        }
        for name, (command, expected) in cases.items():
            with self.subTest(name=name):
                self.assertEqual(expected, strip_heredocs(command))

    def test_text_that_is_not_a_heredoc_keeps_the_next_line(self):
        cases = {
            "quoted marker text": "rg -n '<<EOF' .\necho x",
            "double quoted marker text": 'echo "<<EOF"\necho x',
            "shift inside arithmetic": "echo $((1<<X))\necho x",
            "here-string": "cat <<<x\necho y",
            "marker in a comment": "echo hi # <<X\necho x",
        }
        for name, command in cases.items():
            with self.subTest(name=name):
                self.assertEqual(command, strip_heredocs(command))

    def test_the_body_of_a_heredoc_fed_to_a_shell_is_kept_as_code(self):
        cases = {
            "bash": ("bash <<'EOF'\nsed -i s/a/b/ f\nEOF\necho x", "bash <<'EOF'\n(\nsed -i s/a/b/ f\n)\necho x"),
            "wrapped sh": ("sudo sh <<EOF\nrm f\nEOF", "sudo sh <<EOF\n(\nrm f\n)"),
        }
        for name, (command, expected) in cases.items():
            with self.subTest(name=name):
                self.assertEqual(expected, strip_heredocs(command))

    def test_a_shell_name_that_is_not_the_command_does_not_keep_the_body(self):
        command = "cat <<EOF > bash\nbody\nEOF\necho x"

        self.assertEqual("cat <<EOF > bash\necho x", strip_heredocs(command))

    def test_the_delimiter_is_the_whole_shell_word(self):
        command = "cat <<EOF-X > /dev/null\nx\nEOF-X\necho hi"

        self.assertEqual("cat <<EOF-X > /dev/null\necho hi", strip_heredocs(command))

    def test_a_heredoc_with_no_terminator_line_is_not_cut(self):
        command = "cat <<EOF\nbody\necho hi"

        self.assertEqual(command, strip_heredocs(command))

    def test_a_marker_inside_a_quoted_string_that_spans_lines_opens_nothing(self):
        command = "echo 'a\ncat <<EOF\nb' \necho hi"

        self.assertEqual(command, strip_heredocs(command))

    def test_an_arithmetic_shift_with_spaces_opens_nothing(self):
        command = "(( v = 1 << x ))\necho hi"

        self.assertEqual(command, strip_heredocs(command))

    def test_an_unquoted_heredoc_keeps_its_substitution_spans_as_code(self):
        command = "cat <<EOF > /dev/null\n$(echo hi > f)\nplain\n`rm g`\nEOF\nls"
        expected = "cat <<EOF > /dev/null\n(\necho hi > f\n)\n(\nrm g\n)\nls"

        self.assertEqual(expected, strip_heredocs(command))

    def test_a_quoted_heredoc_keeps_no_substitution_span(self):
        command = "cat <<'EOF' > /dev/null\n$(echo hi > f)\nEOF\nls"

        self.assertEqual("cat <<'EOF' > /dev/null\nls", strip_heredocs(command))

    def test_a_real_heredoc_after_quoted_marker_text_is_still_stripped(self):
        command = "echo '<<A' <<B\nbody\nB\necho x"

        self.assertEqual("echo '<<A' <<B\necho x", strip_heredocs(command))

    def test_a_long_command_with_no_heredoc_is_stripped_in_under_a_second(self):
        command = "\n".join(f"echo line {number} > /tmp/out{number}.txt" for number in range(3000))
        started = time.monotonic()

        self.assertEqual(command, strip_heredocs(command))
        self.assertLess(time.monotonic() - started, 1)


if __name__ == "__main__":
    unittest.main()
