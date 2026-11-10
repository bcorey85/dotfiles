"""Exit 1 when the shell command on stdin pipes into a shell interpreter. A `||` is no pipe unless a backslash
comes right before it. A `|` inside closed quotes counts only when the text holds a shell or code-runner word."""
import os
import re
import sys

sys.path[:0] = [os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib")]
import shell_command
import shell_statements

# A `|` right after another `|` is the second half of `||`, unless a backslash comes right before the first one.
# Inside a quoted code-runner string the layer of quoting is unknown, so any backslash may escape that pipe.
UNPARSED_PIPE_SHELL = re.compile(
    r"(?:(?<!\|)|\\\|)\|&?\s*((/usr(/local)?/s?bin/)|/s?bin/)?(ba|z|da|k)?sh(?![\w.-])",
    re.IGNORECASE)


def pipes_into_shell(command):
    command = shell_statements.strip_comments(shell_statements.strip_heredocs(command))
    try:
        piped_commands = shell_command.parse_piped_commands(command)
    except ValueError:
        # A command this reading cannot parse is checked as text. When the text names a program that runs code, the
        # whole text is searched; otherwise only the unquoted parts.
        if shell_command.names_code_runner(command):
            return bool(UNPARSED_PIPE_SHELL.search(command))
        return bool(shell_command.unquoted_matches(UNPARSED_PIPE_SHELL, command))

    for words, _redirections, piped in piped_commands:
        if piped and shell_command.runs_shell(words):
            return True
        code = shell_command.shell_code_argument(words)
        if code and pipes_into_shell(code):
            return True
    # A program that runs code may hold a pipe into a shell inside a quoted argument (`python3 -c "...| sh"`).
    return shell_command.names_code_runner(command) and bool(UNPARSED_PIPE_SHELL.search(command))


def main():
    return 1 if pipes_into_shell(sys.stdin.read()) else 0


if __name__ == "__main__":
    sys.exit(main())
