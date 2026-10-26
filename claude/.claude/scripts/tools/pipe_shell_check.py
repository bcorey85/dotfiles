"""Exit 1 when the shell command on stdin pipes into a shell interpreter. Only a real pipe counts: a `|` inside a
quoted argument, such as the regex `(py|sh)`, is not one."""
import os
import re
import sys

sys.path[:0] = [os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib")]
import shell_command

SHELL_INTERPRETERS = {"sh", "bash", "zsh", "dash", "ksh"}
# Words that run the command after them, with plain flags or `NAME=value` words beside it.
COMMAND_WRAPPERS = {"sudo", "env", "exec", "command", "nohup", "nice", "time", "doas", "builtin"}
GROUP_WORDS = {"{", "!"}
UNPARSED_PIPE_SHELL = re.compile(r"\|\s*((/usr(/local)?/s?bin/)|/s?bin/)?(ba|z|da|k)?sh\b", re.IGNORECASE)


def runs_shell(words):
    """True when the simple command, once its wrapper words are dropped, runs a shell interpreter."""
    words = shell_command.without_assignments(words)
    while words and (words[0] in GROUP_WORDS or os.path.basename(words[0]) in COMMAND_WRAPPERS):
        words = shell_command.without_assignments(words[1:])
        while words and words[0].startswith("-"):
            words = words[1:]
    return bool(words) and os.path.basename(words[0]).lower() in SHELL_INTERPRETERS


def pipes_into_shell(command):
    try:
        piped_commands = shell_command.parse_piped_commands(command)
    except ValueError:
        # A command this reading cannot trust is checked as plain text, as before.
        return bool(UNPARSED_PIPE_SHELL.search(command))

    return any(piped and runs_shell(words) for words, _redirections, piped in piped_commands)


def main():
    return 1 if pipes_into_shell(sys.stdin.read()) else 0


if __name__ == "__main__":
    sys.exit(main())
