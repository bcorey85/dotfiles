"""commit_pathspec.py: whether a `git commit` names the files it commits, read from its words."""
import re

from git_commit_calls import commit_flag_letters, commit_takes_next_word
from git_subcommand_options import is_pathspec_from_file
from shell_command import (
    is_long_prefix,
    is_short_cluster,
    options_before_separator,
    without_flag_values,
)

# (option, shortest accepted abbreviation): the options that make `git commit` commit nothing.
DRY_RUN_OPTIONS = (("--dry-run", "--dr"), ("--short", "--sh"), ("--porcelain", "--por"), ("--long", "--l"))

# A pathspec that matches every file of the tree, from any folder.
WHOLE_TREE_PATHSPEC = re.compile(r"(\./*|:/+|:\(top\)\.?/*|\*)")


def option_sweeps_index(option):
    """True for `-a`/`-i` (in a short cluster) or `--all`/`--include`: the commit takes the whole index."""
    if is_short_cluster(option):
        letters = commit_flag_letters(option)
        return "a" in letters or "i" in letters
    # `--i` and `--in` are ambiguous with `--interactive`.
    return option == "--all" or is_long_prefix(option.split("=")[0], "--include", "--inc")


def implies_dry_run(option):
    """True for `--dry-run` and the options that imply it, or an abbreviation git accepts."""
    name = option.split("=")[0]
    # `--d` is ambiguous with `--date`.
    return any(is_long_prefix(name, full, shortest) for full, shortest in DRY_RUN_OPTIONS)


def names_whole_tree(words):
    """True when a pathspec after `--` names the whole tree (`.`, `./`, `:/`, `:(top)`, `*`): it commits every file."""
    if "--" not in words:
        return False
    paths = words[words.index("--") + 1:]
    return any(WHOLE_TREE_PATHSPEC.fullmatch(path) for path in paths)


def is_bare_commit(arguments):
    """True when a `git commit` with these arguments commits whatever the index holds: no `-- <path>` and no
    `--pathspec-from-file`, or `-a`/`--all`, `-i`/`--include`. An exact `--amend` is never bare (rule 2 judges
    it), nor is `--dry-run`, or `--short`, `--porcelain` or `--long`, which imply it, or an abbreviation of one: they
    commit nothing.
    A path word with no `--` does not count."""
    words = without_flag_values(arguments, takes_value=commit_takes_next_word)
    options = options_before_separator(words)
    is_dry_run = any(implies_dry_run(option) for option in options)
    if "--help" in options or "-h" in options:
        return False
    if "--amend" in options or is_dry_run:
        return False
    if any(option_sweeps_index(option) for option in options):
        return True
    if any(is_pathspec_from_file(option) for option in options):
        return False
    if names_whole_tree(words):
        return True
    return len(words) <= len(options) + 1
