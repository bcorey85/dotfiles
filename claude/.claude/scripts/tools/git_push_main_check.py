"""Exit 1 when the shell command on stdin holds a `git push` that names main or master as a target. Only the
arguments of each `git push` simple command are read, so a chained command that mentions main elsewhere passes."""
import os
import re
import sys

sys.path[:0] = [os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib")]
import shell_command

PROTECTED_BRANCHES = {"main", "master"}
UNPARSED_PUSH = re.compile(r"git\s+push\b", re.IGNORECASE)
UNPARSED_BRANCH = re.compile(r"\b(main|master)\b", re.IGNORECASE)


def push_arguments(words):
    """The words after `push` when the simple command is a `git push`, else None."""
    words = shell_command.without_assignments(words)
    if not words or os.path.basename(words[0]) != "git":
        return None

    _options, index = shell_command.git_options(words)
    if index >= len(words) or words[index] != "push":
        return None
    return words[index + 1:]


def names_protected_branch(argument):
    """True when a refspec argument (`main`, `+master`, `HEAD:main`, `src:refs/heads/master`) targets main or master."""
    if argument.startswith("-"):
        return False
    for part in argument.split(":"):
        branch = part.lstrip("+").removeprefix("refs/heads/")
        if branch.lower() in PROTECTED_BRANCHES:
            return True
    return False


def pushes_to_protected_branch(command):
    try:
        simple_commands = shell_command.split_simple_commands(command)
    except ValueError:
        # A command this reading cannot trust is checked as plain text, as before.
        return bool(UNPARSED_PUSH.search(command) and UNPARSED_BRANCH.search(command))

    for words in simple_commands:
        arguments = push_arguments(words)
        if arguments is not None and any(names_protected_branch(argument) for argument in arguments):
            return True
    return False


def main():
    return 1 if pushes_to_protected_branch(sys.stdin.read()) else 0


if __name__ == "__main__":
    sys.exit(main())
