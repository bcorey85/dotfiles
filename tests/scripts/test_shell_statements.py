"""Checks for shell_statements.py: heredoc bodies are cut out of a command, and only a real heredoc starts one."""
import os
import pathlib
import sys
import tempfile
import time
import unittest
from unittest import mock

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))

from shell_statements import (
    arithmetic_spans,
    blank_script_run_quotes,
    clean,
    decode_ansi_c,
    is_arithmetic_span,
    opens_shell_heredoc,
    resolved_word,
    runs_script_file,
    split_on_pipe_both,
    statement_word_pairs,
    statements_with_operators,
    strip_comments,
    strip_heredocs,
    strip_stored_heredocs,
)


class SplitOnPipeBothTest(unittest.TestCase):
    def test_each_unquoted_pipe_both_ends_a_part(self):
        self.assertEqual(["a ", " b ", " c"], split_on_pipe_both("a |& b |& c"))
        self.assertEqual(["a | b"], split_on_pipe_both("a | b"))

    def test_a_quoted_or_escaped_pipe_both_stays_in_its_part(self):
        for command in ("echo '|&' x", 'echo "|&" x', "echo \\|& x"):
            self.assertEqual([command], split_on_pipe_both(command), command)


class IsArithmeticSpanTest(unittest.TestCase):
    def test_a_span_is_arithmetic_only_when_its_inner_paren_closes_at_the_last_character(self):
        cases = {"(1+2)": True, "((1+2)*3)": True, "(a)+(b)": False, "(echo x) ": False, "(echo x > {a,b}) ": False,
                 "(1+2": False, "(')')": True}
        for span, expected in cases.items():
            self.assertEqual(is_arithmetic_span(span), expected, span)


class ArithmeticSpansTest(unittest.TestCase):
    def test_a_span_is_kept_only_when_its_inner_paren_closes_at_the_last_character(self):
        cases = {"x=$((1+2))": [(2, 10)], "((1+2))": [(0, 7)], "$((1+(2)))": [(0, 10)],
                 "((echo hi) > f); echo $((1))": [(22, 28)], "$((echo hi) )": [], "echo '((1))'": []}
        for text, expected in cases.items():
            self.assertEqual(expected, arithmetic_spans(text), text)


class DecodeAnsiCTest(unittest.TestCase):
    def test_a_code_point_above_the_unicode_range_does_not_crash(self):
        for word in ("\\U00110000", "\\UFFFFFFFF"):
            with self.subTest(word=word):
                self.assertEqual(decode_ansi_c(word), word)

    def test_a_code_point_in_range_decodes(self):
        self.assertEqual(decode_ansi_c("\\U0010FFFF\\x41"), "\U0010FFFFA")


class StatementsWithOperatorsTest(unittest.TestCase):
    def test_a_redirection_stays_a_word_of_its_statement_and_is_no_separator(self):
        cases = {
            "git push 2>&1 && ls": [("", ["git", "push", "2>&1"], "&&"), ("&&", ["ls"], "")],
            "git push &>f; ls": [("", ["git", "push", "&>f"], ";"), (";", ["ls"], "")],
        }
        for command, expected in cases.items():
            with self.subTest(command=command):
                found = [(s.operator_before, s.words, s.operator_after) for s in statements_with_operators(command)]
                self.assertEqual(found, expected)


class StatementWordPairsTest(unittest.TestCase):
    def test_a_redirection_word_is_the_same_in_both_lists(self):
        for command, word in (("git push 2>&1", "2>&1"), ("git push &>f", "&>f")):
            with self.subTest(command=command):
                pair, = statement_word_pairs(command)
                self.assertEqual(pair.blanked, ["git", "push", word])
                self.assertEqual(pair.resolved, ["git", "push", word])

    def test_an_ansi_c_word_is_blanked_in_one_list_and_decoded_in_the_other(self):
        pair, = statement_word_pairs("git reset $'--hard'")

        self.assertEqual(pair.blanked, ["git", "reset", '$""'])
        self.assertEqual(pair.resolved, ["git", "reset", "--hard"])


class ResolvedWordTest(unittest.TestCase):
    def resolve(self, command, index):
        quotes = []
        words = clean(command, quotes).split()
        return resolved_word(words[index], quotes)

    def test_an_ansi_c_string_is_decoded_and_its_dollar_dropped(self):
        self.assertEqual(self.resolve("git reset $'--hard'", 2), "--hard")
        self.assertEqual(self.resolve("git reset $'\\x2d\\x2dhard'", 2), "--hard")

    def test_a_redirection_word_is_returned_unchanged(self):
        self.assertEqual(self.resolve("git push 2>&1", 2), "2>&1")
        self.assertEqual(self.resolve("git push &>f", 2), "&>f")


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


class ScriptRunTest(unittest.TestCase):
    def test_an_interpreter_with_a_script_file_is_a_script_run_anywhere(self):
        for words in (["python3", "x.py", "a"], ["python3", "-W", "ignore", "x.py"],
                      ["env", "FOO=1", "python3", "x.py"]):
            with self.subTest(words=words):
                self.assertTrue(runs_script_file(words))

    def test_a_path_in_the_toolkit_scripts_or_a_skill_scripts_folder_is_a_script_run(self):
        for words in (["~/.claude/scripts/review/verify-log", "review"],
                      [os.path.expanduser("~/.claude/skills/review/scripts/tool"), "a"]):
            with self.subTest(words=words):
                self.assertTrue(runs_script_file(words))

    def test_a_toolkit_interpreter_launcher_is_read_as_the_interpreter_it_runs(self):
        launcher = "~/.claude/scripts/tools/hook-python"
        self.assertTrue(runs_script_file([launcher, "x.py", "a"]))
        self.assertTrue(runs_script_file([launcher, "-W", "ignore", "x.py"]))
        self.assertFalse(runs_script_file([launcher, "-c", "import os"]))
        self.assertFalse(runs_script_file([launcher, "-"]))
        self.assertEqual('~/.claude/scripts/tools/hook-python x.py ""',
                         blank_script_run_quotes(f'{launcher} x.py "a git commit"'))
        self.assertEqual(f'{launcher} -c "import os"', blank_script_run_quotes(f'{launcher} -c "import os"'))
        self.assertEqual(f"{launcher} - <<'EOF'\nos.system('git commit')\nEOF",
                         strip_stored_heredocs(f"{launcher} - <<'EOF'\nos.system('git commit')\nEOF"))

    def test_a_skill_script_stays_trusted_when_each_skill_is_linked_on_its_own(self):
        own_skills = toolkit_paths.CLAUDE_DIR / "skills"
        skill_name = next(folder.parent.name for folder in sorted(own_skills.glob("*/scripts")))
        with tempfile.TemporaryDirectory() as home:
            skills_link_dir = pathlib.Path(home) / ".claude" / "skills"
            skills_link_dir.mkdir(parents=True)
            (skills_link_dir / skill_name).symlink_to(own_skills / skill_name)
            words = [str(skills_link_dir / skill_name / "scripts" / "tool"), "a"]
            with mock.patch.dict(os.environ, {"HOME": home}):
                self.assertTrue(runs_script_file(words))
                self.assertFalse(runs_script_file([str(skills_link_dir / skill_name / "tool"), "a"]))

    def test_a_path_anywhere_else_is_no_script_run(self):
        for words in (["~/bin/tool", "--rows", "-"], ["../other/tool"], ["./$X/tool"], ["./run.sh"], ["tools/run.sh"],
                      ["~/.claude/plugins/x/run", "git commit -m x"], ["./node_modules/.bin/concurrently", "x"],
                      ["~/.claude/skills/review/tool"], ["~/.claude/hooks/tool"],
                      ["/Applications/Tool.app/tool", "x"], ["/Library/tool", "x"], ["/System/tool", "x"],
                      ["~/.claude/../bin/tool"]):
            with self.subTest(words=words):
                self.assertFalse(runs_script_file(words))

    def test_a_program_whose_later_word_names_a_shell_or_launcher_is_no_script_run(self):
        for words in (["~/.claude/scripts/bin/mise", "exec", "--", "bash", "-c", "git commit -am x"],
                      ["~/.claude/scripts/cross-env", "A=1", "sh", "-c", "git commit -am x"],
                      ["node", "some/tool.js", "sh", "-c", "git commit"],
                      ["~/.claude/scripts/tools/notify", "python3", "-c", "git commit"],
                      ["~/.claude/scripts/tools/notify", "node", "-e", "git commit"],
                      ["~/.claude/scripts/x", "docker", "exec", "c", "git commit -am x"]):
            with self.subTest(words=words):
                self.assertFalse(runs_script_file(words))

    def test_a_later_test_flag_makes_no_script_run(self):
        for words in (["node", "--test", "x.js", "a"],
                      ["~/.claude/scripts/tools/notify", "--test", "a"],
                      ["~/.claude/scripts/tools/notify", "--test=git commit -am x"],
                      ["~/.claude/scripts/review/review_loop_script.py", ".", "--gate-command", "git commit"],
                      ["~/.claude/scripts/review/review_loop_script.py", ".", "--gate-command=git commit"]):
            with self.subTest(words=words):
                self.assertFalse(runs_script_file(words))

    def test_a_review_launch_keeps_the_quoted_text_of_its_test_command(self):
        for command in ("python3 ~/.claude/scripts/review/review_fix.py launch --test 'git commit -am x'",
                        "python3 ~/.claude/scripts/review/review_fix.py launch '--test=git commit -am x'"):
            with self.subTest(command=command):
                self.assertEqual(command, blank_script_run_quotes(command))

    def test_a_launcher_wrapped_commit_keeps_its_quoted_text(self):
        for command in ('~/.claude/scripts/bin/mise exec -- bash -c "git commit -am x"',
                        '~/.claude/scripts/cross-env A=1 sh -c "git commit -am x"',
                        'node some/tool.js sh -c "git commit"'):
            with self.subTest(command=command):
                self.assertEqual(command, blank_script_run_quotes(command))

    def test_a_shell_eval_git_a_bare_program_and_inline_code_are_no_script_run(self):
        for words in (["bash", "x.sh"], ["/bin/bash", "x.sh"], ["/usr/bin/git", "commit"], ["eval", "x"],
                      ["gh", "pr", "create"], ["python3", "-c", "x"], ["python3", "-i", "x.py"], [],
                      ["php", "-r", 'system("git commit -am x");', "x"], ["php", "-rsystem(1);", "x"],
                      ["/usr/bin/xargs", "-I{}", "sh"], ["/usr/bin/find", ".", "-exec", "sh"],
                      ["/usr/bin/flock", "/tmp/l", "-c", "x"], ["/usr/bin/watch", "x"], ["/usr/bin/script", "-c", "x"],
                      ["/usr/bin/su", "-c", "x"], ["/usr/bin/ssh", "host", "x"], ["/usr/bin/fish", "-c", "x"],
                      ["/usr/bin/busybox", "sh"], ["/usr/bin/parallel", "x"], ["/usr/bin/awk", "x"],
                      ["/usr/bin/tmux", "new", "x"], ["/usr/bin/sg", "grp", "-c", "x"],
                      ["/usr/bin/expect", "-c", "x"], ["/usr/bin/tcsh", "-c", "x"],
                      ["~/.local/bin/tcsh", "-c", "x"], ["~/.cargo/bin/nu", "-c", "x"],
                      ["/snap/bin/pwsh", "-c", "x"], ["/home/linuxbrew/.linuxbrew/bin/bash", "-c", "x"],
                      ["/opt/local/bin/gawk", "x"]):
            with self.subTest(words=words):
                self.assertFalse(runs_script_file(words))

    def test_only_the_steps_that_are_script_runs_lose_their_quoted_text(self):
        command = 'python3 x.py "a b" && gh pr create --body "c" ; ~/.claude/scripts/t \'d\''

        self.assertEqual('python3 x.py "" && gh pr create --body "c" ; ~/.claude/scripts/t ""',
                         blank_script_run_quotes(command))

    def test_a_script_step_is_blanked_and_the_commit_step_after_it_stays_as_written(self):
        command = 'python3 x.py "a" && git commit -m "x"'

        self.assertEqual('python3 x.py "" && git commit -m "x"', blank_script_run_quotes(command))

    def test_a_script_step_that_a_pipe_follows_stays_as_written(self):
        for command in ('python3 x.py "git commit -am x" | fish', 'python3 x.py "git commit -am x" | nu',
                        'python3 x.py "git commit -am x" |& fish', 'a | python3 x.py "git commit -am x" | nu'):
            with self.subTest(command=command):
                self.assertEqual(command, blank_script_run_quotes(command))

    def test_a_script_step_with_a_process_substitution_stays_as_written(self):
        for command in ('python3 x.py "git commit -am x" > >(fish)', 'cat <(python3 x.py "git commit -am x")'):
            with self.subTest(command=command):
                self.assertEqual(command, blank_script_run_quotes(command))

    def test_a_compound_group_piped_onward_stays_as_written(self):
        for command in ('{ ~/.claude/scripts/tools/x.py "git commit -m y"; } | python3',
                        '(python3 x.py "git commit -am x"; true) | python3',
                        'if true; then python3 x.py "git commit -am x"; fi | python3',
                        'for i in 1; do ~/.claude/scripts/tools/x.py "git commit -m y"; done | python3'):
            with self.subTest(command=command):
                self.assertEqual(command, blank_script_run_quotes(command))

    def test_a_heredoc_in_a_brace_group_piped_onward_is_not_cut(self):
        command = "{ ~/.claude/scripts/x <<'EOF'\ngit commit -m y\nEOF\n} | python3"

        self.assertEqual(command, strip_stored_heredocs(command))

    def test_the_last_step_of_a_pipe_is_still_blanked(self):
        self.assertEqual('echo a | python3 x.py ""', blank_script_run_quotes('echo a | python3 x.py "b"'))

    def test_a_step_with_a_substitution_holds_more_than_one_command_so_it_stays_as_written(self):
        command = 'python3 x.py "a" $(git commit -m "x")'

        self.assertEqual(command, blank_script_run_quotes(command))

    def test_a_step_that_cannot_be_parsed_stays_as_written(self):
        self.assertEqual("python3 x.py 'unclosed", blank_script_run_quotes("python3 x.py 'unclosed"))


if __name__ == "__main__":
    unittest.main()
