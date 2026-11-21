"""Follow the directory a shell is in as a command line runs: `cd`, `pushd`, `popd`, and the folder words they take."""
import os
import re

# The words that change the shell's working directory; every gate follows or flags the same set.
CD_WORD = "cd"
DIRECTORY_MOVE_WORDS = (CD_WORD, "pushd", "popd")


def path_word(word):
    """The path a shell word names: a quote left at either end is dropped and a leading `~` or `~user` is replaced by
    that home directory. A `~user` that names no user stays as it is."""
    for quote in ('"', "'"):
        if word.endswith(quote):
            word = word[:-1]
        if word.startswith(quote):
            word = word[1:]
    return os.path.expanduser(word)


def path_word_is_absolute(raw):
    """True when the path a shell word names (see path_word) starts with `/`, outer blanks ignored."""
    return path_word(raw.strip(" \t\n\r\f\v")).startswith("/")


CD_OPTION = re.compile(r"-[LPe@]+|--")
# A folder word the shell expands or looks up: a parameter, a substitution, a glob or brace, or `~user`.
UNREAD_FOLDER = re.compile(r"[$`*?\[{]|^~[^/]")
# A directory-stack index (`pushd +1`, `cd -1`), not a folder name.
STACK_INDEX = re.compile(r"[+-]\d+")


def cd_folder(words):
    """The folder a `cd` or `pushd` call names (`~` for a bare `cd`), or None for a `popd`, a bare `pushd`, `cd -`,
    zsh's two-word `cd old new`, a directory-stack index, or a folder the shell expands."""
    arguments = [word for word in words[1:] if not CD_OPTION.fullmatch(word)]
    if words[0] == "popd" or len(arguments) > 1:
        return None
    if not arguments:
        return "~" if words[0] == CD_WORD else None

    folder = arguments[0]
    if folder == "-" or STACK_INDEX.fullmatch(folder) or UNREAD_FOLDER.search(folder):
        return None
    return folder


class ShellDirectory:
    """The directory a shell is in as a command runs, moved by `cd`, `pushd`, `popd` and `cd -`. `current` is None
    once the shell is somewhere unknown: a target the shell expands, a `popd` or `cd -` with nothing to return to."""

    def __init__(self, current):
        self.current = current
        self.previous = None
        self.stack = []

    def saved(self):
        """The state a `( ... )` group restores when it closes."""
        return (self.current, self.previous, tuple(self.stack))

    def restore(self, saved):
        self.current, self.previous, stack = saved
        self.stack = list(stack)

    def move_to(self, new_directory):
        self.previous = self.current
        self.current = new_directory

    def apply(self, words):
        """Moves by the `cd`, `pushd` or `popd` call in `words`."""
        command = words[0]
        arguments = [word for word in words[1:] if not CD_OPTION.fullmatch(word)]
        if command == "popd":
            self.move_to(self.stack.pop() if self.stack else None)
            return
        if command == CD_WORD and arguments == ["-"]:
            self.current, self.previous = self.previous, self.current
            return
        folder = cd_folder(words)
        if command == "pushd":
            self.stack.append(self.current)
        if folder is None or self.current is None:
            self.move_to(None)
            return
        self.move_to(os.path.normpath(os.path.join(self.current, path_word(folder))))
