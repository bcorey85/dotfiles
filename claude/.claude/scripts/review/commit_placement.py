"""commit_placement.py: where the git calls in a Bash command that make a commit land, for review_commit_gate.py.
`CommitReader` is built with the gate's own text readers (`shell_text_commits`, `readable_command`), so this module
imports nothing of the gate. It answers three questions: which calls commit (commit_call, an alias or a plain git
call), the directories they commit in as the command names them (placed_commits, for the asks check), and the
directory each earns credit in (commit_repo_dirs, which gives up on anything it cannot follow)."""
import pathlib
import shlex
import sys
from typing import NamedTuple

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / folder) for folder in (".", "../lib")]
from git_alias_commits import git_words_make_commit
from git_commit_calls import UNPLACED_COMMIT, git_commit_dirs
from shell_command import (
    git_c_directory,
    is_git_word,
    split_command_steps,
    split_simple_commands,
    without_assignments,
)

# The subcommand a deny names when no git call in the command can be read as the commit (a text match only).
DEFAULT_COMMIT_SUBCOMMAND = "commit"


class PlacedCommits(NamedTuple):
    """The commits of one command: `named_dirs`, the directory of each commit git_commit_dirs placed (None: no cwd, or
    the command cannot be read), `unplaced`, the words of each commit it could not place, and `first_call_words`, the
    words of the first commit call (None when the words show none), whose subcommand a deny names."""
    named_dirs: list | None
    unplaced: list
    first_call_words: list | None = None

    def makes_commit(self):
        """True when the command holds a commit, placed or not. A command that cannot be read counts as none (fail
        open): the text patterns have already read it, and they never see aliases."""
        return bool(self.named_dirs) or bool(self.unplaced)


class CommitReader:
    """Reads the commits in a command with the gate's text readers: `shell_text_commits(text)` says whether shell
    text holds a commit, `readable_command(command)` is the command with its quoted-heredoc
    messages emptied and line continuations removed."""

    def __init__(self, shell_text_commits, readable_command, git_timeout):
        self.shell_text_commits = shell_text_commits
        self.readable_command = readable_command
        self.git_timeout = git_timeout

    def commit_call(self, words, directory):
        """True when the git call in `words`, run in `directory`, makes a commit; UNPLACED_COMMIT when it does so
        through a `!` shell alias (git_words_make_commit)."""
        return git_words_make_commit(words, directory, 0, self.shell_text_commits, self.git_timeout)

    def placed_commits(self, command, cwd):
        """The commits of the command, read from `cwd` moved as the command moves it. A command that cannot be read
        has named_dirs None, and so has a call with no cwd: a commit the gate cannot place (`cd "$D" && git ci -m x`)
        is in `unplaced`, so the asks check reads it in the cwd repo (fail closed)."""
        if not cwd:
            return PlacedCommits(None, [])
        if "git" not in command:
            return PlacedCommits([], [])
        placed = git_commit_dirs(self.readable_command(command), cwd, self.commit_call)
        if placed is None:
            return PlacedCommits(None, [])
        return PlacedCommits(placed.commit_dirs, placed.unplaced, placed.first_call_words)

    def simple_commands(self, command):
        """The words of each simple command in the command, or None when a step cannot be read."""
        all_words = []
        for _, step in split_command_steps(self.readable_command(command)):
            try:
                all_words.extend(split_simple_commands(step))
            except ValueError:
                return None
        return all_words

    def commit_repo_dirs(self, command, cwd):
        """The directory of every git call that makes a commit (commit_dir) in the command: the cwd, moved by each
        `git -C <dir>` before the subcommand. [None] when the command cannot be read, holds no such call, or any one
        uses an option that moves the repo (--git-dir, --work-tree), a `!` shell alias, or a form
        (`env -C <dir> git commit`) the gate does not follow. A NAME=value word before `git` is dropped."""
        if not cwd:
            return [None]
        simple_commands = self.simple_commands(command)
        if simple_commands is None:
            return [None]
        committed_dirs = []
        for words in simple_commands:
            committed_in = self.commit_dir(without_assignments(words), cwd)
            if committed_in == "":
                return [None]
            if committed_in is None and self.shell_text_commits(shlex.join(words)):
                return [None]
            if committed_in is not None and committed_in not in committed_dirs:
                committed_dirs.append(committed_in)
        return committed_dirs or [None]

    def commit_dir(self, words, directory):
        """The directory a simple command `git [-C <dir>]...` commits in, from `directory`, when it is a git call that
        makes a commit (commit_call); "" when it is a git command whose options the gate does not follow, or a commit
        through a `!` shell alias, which may land anywhere; None for any other command."""
        if not words or not is_git_word(words[0]):
            return None
        moved = git_c_directory(words, directory)
        if moved is None:
            return ""
        answer = self.commit_call(words, moved)
        if answer == UNPLACED_COMMIT:
            return ""
        if answer:
            return moved
        return None
