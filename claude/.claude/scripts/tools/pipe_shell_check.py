"""Exit 1 when the shell command on stdin pipes into a shell interpreter. A `||` is no pipe unless a
backslash escapes its first bar. Inside a quoted string of a command that names a code runner, any backslash before
the bars counts as escaping it. A `|` inside closed quotes counts only when the text holds a shell or code-runner
word."""
import os
import re
import sys

sys.path[:0] = [os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib")]
import shell_command
import shell_statements


def pipe_shell_pattern(escaped_pipe):
    """A pipe into a shell: a `|` not right after another `|` (the second half of `||`), or a `|` right after a
    match of the escaped_pipe pattern, which matches a backslash run plus the first bar of the pair."""
    return re.compile(
        rf"(?:(?<!\|)|{escaped_pipe})\|&?\s*((/usr(/local)?/s?bin/)|/s?bin/)?(ba|z|da|k)?sh(?![\w.-])",
        re.IGNORECASE)


# In shell text an odd run of backslashes before a `|` escapes it, so a pipe follows; an even run is escaped
# backslashes, so the bars after it are a real `||`.
UNPARSED_PIPE_SHELL = pipe_shell_pattern(r"(?<!\\)(?:\\\\)*\\\|")
# Inside a quoted string the layer of quoting is unknown (`bash -c "echo \\|| sh"` hands the shell `echo \|| sh`),
# so any backslash run may escape that pipe.
QUOTED_PIPE_SHELL = pipe_shell_pattern(r"(?<!\\)\\+\|")


def text_pipes_into_shell(command):
    """Search the whole text of a command that names a code runner: a pipe into a shell anywhere, or a quoted
    backslash run before the bars."""
    if UNPARSED_PIPE_SHELL.search(command):
        return True
    quoted = shell_command.quoted_positions(command, unclosed_is_quoted=False)
    # The last character of the shell name is tested: a backslash run is not reliably marked by its own position.
    return any(match.end() - 1 in quoted for match in QUOTED_PIPE_SHELL.finditer(command))


def pipes_into_shell(command):
    command = shell_statements.strip_comments(shell_statements.strip_heredocs(command))
    try:
        piped_commands = shell_command.parse_piped_commands(command)
    except ValueError:
        # A command this reading cannot parse is checked as text. When the text names a program that runs code, the
        # whole text is searched; otherwise only the unquoted parts.
        if shell_command.names_code_runner(command):
            return text_pipes_into_shell(command)
        return bool(shell_command.unquoted_matches(UNPARSED_PIPE_SHELL, command))

    for words, _redirections, piped in piped_commands:
        if piped and shell_command.runs_shell(words):
            return True
        code = shell_command.shell_code_argument(words)
        if code and pipes_into_shell(code):
            return True
    # A program that runs code may hold a pipe into a shell inside a quoted argument (`python3 -c "...| sh"`).
    return shell_command.names_code_runner(command) and text_pipes_into_shell(command)


def main():
    return 1 if pipes_into_shell(sys.stdin.read()) else 0


if __name__ == "__main__":
    sys.exit(main())
