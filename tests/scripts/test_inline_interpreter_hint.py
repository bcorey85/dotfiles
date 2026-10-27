"""Checks for inline_interpreter_hint.py: it denies interpreter code given inline or on stdin, and names the script
file to write instead."""
import json
import subprocess
import sys
import unittest

import toolkit_paths

HOOK = toolkit_paths.GATES_DIR / "inline_interpreter_hint.py"

DENIED_COMMANDS = {
    "python_dash_flag_c": "python3 -c 'print(1)'",
    "node_eval": "node -e 'process.exit(1)'",
    "python_dash": "python3 -",
    "python_dash_with_heredoc": "python3 - <<'EOF'\nimport pathlib\npathlib.Path('f').write_text('x')\nEOF",
    "python_heredoc_without_dash": "python3 <<'EOF'\nprint(1)\nEOF",
    "python_unquoted_heredoc_marker": "python3 <<EOF\nprint(1)\nEOF",
    "python_here_string": "python3 <<< 'print(1)'",
    "node_dash": "node -",
    "node_heredoc": "node <<'EOF'\nconsole.log(1)\nEOF",
    "ruby_dash": "ruby -",
    "ruby_heredoc": "ruby <<'EOF'\nputs 1\nEOF",
    "perl_dash": "perl -",
    "perl_heredoc": "perl <<'EOF'\nprint 1;\nEOF",
    "python_unbuffered_dash": "python3 -u -",
    "python_versioned_dash": "python3.12 -",
    "pipe_into_python": "cat x | python3",
    "pipe_into_node": "cat x | node",
    "pipe_into_python_after_a_chain": "cd d && cat x | python3 && echo done",
    "heredoc_piped_into_python": "cat <<'EOF' | python3\nprint(1)\nEOF",
    "env_wrapped_python_dash": "env FOO=1 python3 -",
    "python_dash_after_a_heredoc_with_an_apostrophe": "cat <<'EOF' > f\ndon't\nEOF\npython3 -",
    "timeout_wrapped": "timeout 60 python3 - <<'EOF'\nprint(1)\nEOF",
    "uv_run_wrapped": "uv run python - <<'EOF'\nprint(1)\nEOF",
    "poetry_run_wrapped": "poetry run python - <<'EOF'\nprint(1)\nEOF",
    "nice_wrapped": "nice python3 - <<'EOF'\nprint(1)\nEOF",
    "nice_with_a_level_wrapped": "nice -n 5 python3 - <<'EOF'\nprint(1)\nEOF",
    "env_flag_wrapped": "env -i python3 - <<'EOF'\nprint(1)\nEOF",
    "docker_compose_exec_wrapped": "docker compose exec -T web python - <<'EOF'\nprint(1)\nEOF",
    "python_option_with_a_value": "python3 -W ignore - <<'EOF'\nprint(1)\nEOF",
    "python_x_option_with_a_value": "python3 -X utf8 -",
    "heredoc_piped_and_redirected_with_a_quote_in_the_body":
        "python3 - <<'EOF' | head -n 20 > /tmp/out\nprint(\"it's\")\nEOF",
    "unparsed_escaped_pipe_then_pipe_into_python": "grep 'a\\|b' f | python3",
    "unparsed_quoted_pipe_then_python_dash": "echo '|' ; python3 - <<'EOF'\nprint(1)\nEOF",
    "python_after_a_rg_heredoc_lookalike": "rg -n '<<EOF' .\npython3 -",
    "python_after_a_shift_expression": "echo $((1<<X))\npython3 -",
    "python_after_two_heredocs": "cat <<A <<B\na\nA\nb\nB\npython3 -",
    "pipe_into_python_with_verbose_flag": "cat x | python3 -v",
    "unparsed_escaped_pipe_then_python_heredoc": "grep 'a\\|b' f; python3 <<'EOF'\nprint(1)\nEOF",
    "unparsed_escaped_pipe_then_python_dash": "grep 'a\\|b' f | python3 -",
    "interpreter_in_a_heredoc_fed_to_bash": "bash <<'EOF'\npython3 -\nEOF",
    "python_reading_dev_stdin": "cat x | python3 /dev/stdin",
    "python_reading_dev_fd_zero": "python3 /dev/fd/0 <<'EOF'\nprint(1)\nEOF",
    "python_reading_proc_self_fd_zero": "cat x | python3 /proc/self/fd/0",
    "unparsed_pipe_into_python_inside_a_group": "( cat x | python3 ) ; echo '|'",
    "unparsed_pipe_both_streams_into_python": "cat x |& python3 ; echo '|'",
    "unparsed_pipe_both_streams_after_a_closed_group": "(cat x) |& python3; echo '|'",
    "unparsed_stream_merge_after_python": "cat x | python3 2>&1; echo '|'",
    "unparsed_output_redirect_after_python": "cat x | python3 >out.txt; echo '|'",
    "unparsed_stream_merge_after_a_wrapped_python": "cat x | nice python3 2>&1; echo '|'",
    "heredoc_python_after_a_comment_with_an_apostrophe": "# don't touch prod\npython3 - <<'EOF'\nimport os\nEOF",
    "pipe_into_python_after_a_comment_with_an_apostrophe": "ls # it's here\ncat data | python3",
    "here_string_python_after_a_comment_with_an_apostrophe": "ls # it's here\npython3 <<<'print(1)'",
    "manage_shell_heredoc": "python manage.py shell <<'EOF'\nprint(1)\nEOF",
    "manage_shell_here_string": "python3 manage.py shell <<< 'print(1)'",
    "manage_shell_pipe": "echo 'print(1)' | python manage.py shell",
    "manage_shell_run_directly_with_a_heredoc": "./manage.py shell <<'EOF'\nprint(1)\nEOF",
    "nodejs_dash": "nodejs -",
    "unparsed_part_python_dash_with_an_escaped_pipe_argument": "cat x | python3 - 'a\\|b'",
    "unparsed_part_python_with_a_spaced_redirect": "cat x | python3 > 'o\\|t'",
    "node_require_option_with_a_value": "cat x | node -r dotenv/config",
    "node_long_require_option_with_a_value": "cat x | node --require dotenv/config",
    "node_import_option_with_a_value": "cat x | node --import tsx",
    "perl_include_option_with_a_value": "perl -I lib -",
    "ruby_include_option_with_a_value": "cat x | ruby -I lib",
    "php_define_option_with_a_value": "cat x | php -d display_errors=1",
    "manage_shell_with_an_option_and_a_heredoc": "python manage.py shell --settings=x <<EOF\nprint(1)\nEOF",
    "manage_shell_with_a_value_option_and_a_heredoc": "python3 manage.py shell -i ipython <<EOF\nprint(1)\nEOF",
    "manage_shell_in_docker_compose": "docker compose exec web python manage.py shell -i x <<EOF\nx\nEOF",
}
ALLOWED_COMMANDS = {
    "script_file": "python3 script.py",
    "script_file_with_heredoc_data": "python3 script.py <<'EOF'\nsome data\nEOF",
    "script_file_after_a_pipe": "cat x | python3 script.py",
    "module": "python3 -m unittest -q test_a",
    "version": "python3 --version",
    "version_after_a_pipe": "echo | python3 --version",
    "node_script_file": "node build.js",
    "node_version": "node --version",
    "heredoc_into_cat": "cat > f.py <<'EOF'\nprint(1)\nEOF\npython3 f.py",
    "heredoc_body_naming_an_interpreter": "cat > notes.txt <<'EOF'\ncat x | python3\nEOF",
    "interpreter_word_in_an_argument": "echo python3 | tee f",
    "bare_interpreter_with_no_stdin": "python3",
    "python_script_read_from_a_file": "python3 < code.py",
    "python_module_glued_to_the_flag_after_a_pipe": "echo '{}' | python3 -mjson.tool",
    "two_heredoc_bodies_naming_an_interpreter": "cat <<A <<B\npython3 -\nA\ncat x | python3\nB\necho done",
    "python_version_flag": "echo | python3 -V",
    "python_verbose_version_flag_after_a_pipe": "cat f | python3 -VV",
    "php_long_version_flag_after_a_pipe": "cat f | php --version",
    "perl_long_version_flag_after_a_pipe": "cat f | perl --version",
    "perl_version_flag_after_a_pipe": "echo | perl -v",
    "node_version_flag_after_a_pipe": "echo | node -v",
    "php_version_flag_after_a_pipe": "echo | php -v",
    "ruby_version_flag_after_a_pipe": "echo | ruby -v",
    "ruby_long_version_flag_after_a_pipe": "echo | ruby --version",
    "unparsed_escaped_pipe_then_python_script": "grep 'a\\|b' f | python3 script.py",
    "unparsed_grep_over_node_modules": "grep -rn 'foo\\|bar' node_modules/x",
    "unparsed_word_containing_perl": "rg 'x\\|y' src/superlative.ts",
    "unparsed_quoted_interpreter_name": "grep 'python\\|node' f",
    "unparsed_python_script_then_grep": "python3 script.py 2>&1 | grep 'a\\|b'",
    "unparsed_python_script_with_quoted_redirect": 'python3 "a.py" > "out.txt"',
    "unparsed_quoted_semicolon_after_export": "export PYTHONPATH=src; echo ';'",
    "unparsed_node_modules_after_a_pipe": "ls node_modules | grep 'a\\|b'",
    "manage_shell_script_file_read": "python manage.py shell < file",
    "commit_message_heredoc_with_an_odd_quote":
        "git commit -m \"$(cat <<'EOF'\nSupports 5\" screens\ngrep x f | python3\nEOF\n)\"",
    "manage_other_command_with_a_heredoc": "python manage.py migrate <<'EOF'\nx\nEOF",
    "nodejs_version_flag_after_a_pipe": "echo | nodejs --version",
}


class InlineInterpreterHintTest(unittest.TestCase):
    def reason_for(self, command):
        payload = json.dumps({"tool_input": {"command": command}})
        finished = subprocess.run([sys.executable, str(HOOK)], input=payload, capture_output=True, text=True,
                                  check=True)
        if not finished.stdout.strip():
            return ""
        return json.loads(finished.stdout)["hookSpecificOutput"]["permissionDecisionReason"]

    def test_inline_and_stdin_code_is_denied(self):
        for name, command in DENIED_COMMANDS.items():
            with self.subTest(name=name):
                self.assertNotEqual(self.reason_for(command), "", command)

    def test_a_script_file_module_or_version_flag_is_allowed(self):
        for name, command in ALLOWED_COMMANDS.items():
            with self.subTest(name=name):
                self.assertEqual(self.reason_for(command), "", command)

    def test_the_deny_names_the_scratchpad_script_and_the_stdin_forms(self):
        reason = self.reason_for("python3 - <<'EOF'\nprint(1)\nEOF")
        self.assertIn("scratchpad", reason)
        self.assertIn("script file", reason)
        self.assertIn("python3 -", reason)


if __name__ == "__main__":
    unittest.main()
