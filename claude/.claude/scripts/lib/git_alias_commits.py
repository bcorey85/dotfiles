"""git_alias_commits.py: whether a git call makes a commit by itself (git_commit_calls) or through an alias, set in the
repo's config or by the call's own `-c alias.<name>=` option, that expands to one. The reading of a `!` shell alias
is the caller's: it passes `shell_text_commits(text)`, so this module imports nothing of the gate."""
import shlex

from git_commit_calls import COMMITTING_SUBCOMMANDS, UNPLACED_COMMIT, config_value, git_call_commits
from shell_command import git_options, split_simple_commands

# How many aliases deep an alias that names another alias is read.
ALIAS_DEPTH_LIMIT = 4
# Subcommands git defines itself, so none is an alias: git never reads an alias of one of these names.
PLAIN_GIT_SUBCOMMANDS = ("add", "status", "diff", "log", "show", "rev-parse", "push", "fetch", "checkout",
                         "switch", "branch", "stash", "reset", "restore", "clone", "init", "tag", "remote", "config",
                         "worktree", "rm", "mv", "apply", "clean", "grep", "ls-files", "describe", "blame", "rebase",
                         "commit-tree", "commit-graph", "bisect", "reflog", "show-ref", "for-each-ref", "ls-remote",
                         "cat-file", "symbolic-ref", "update-ref", "gc", "fsck", "submodule", "archive", "bundle",
                         "format-patch", "diff-tree", "merge-base", "name-rev", "shortlog", "var", "help",
                         "version", "mergetool", "difftool", "sparse-checkout", "maintenance", "hash-object",
                         "write-tree", "read-tree", "ls-tree", "rev-list", "count-objects", "prune", "repack", "pull")


def alias_commit_text(words, index, expansion, directory, depth, shell_text_commits, git_timeout):
    """What a git alias value, run as the call `words` whose subcommand is at `index`, commits, as
    git_words_make_commit answers: a `!` shell alias that holds a commit (`shell_text_commits`) is UNPLACED_COMMIT,
    since it runs in the calling directory but may commit anywhere; git words that are a commit are True (an alias of
    another alias is read to ALIAS_DEPTH_LIMIT). The words keep git's own options, so a `-c alias.<name>=` of the
    call is read at every depth."""
    if expansion.startswith("!"):
        return UNPLACED_COMMIT if shell_text_commits(expansion[1:]) else False
    git_and_options = shlex.join(words[:index])
    call_arguments = shlex.join(words[index + 1:])
    alias_text = git_and_options + " " + expansion + " " + call_arguments
    try:
        alias_commands = split_simple_commands(alias_text)
    except ValueError:
        # An alias git runs but this reading cannot parse is taken to commit (fail closed).
        return True
    if not alias_commands:
        return False
    return git_words_make_commit(alias_commands[0], directory, depth, shell_text_commits, git_timeout)


def git_words_make_commit(words, directory, depth, shell_text_commits, git_timeout):
    """True when the git call in `words`, run in `directory`, makes a commit: by itself, or through an alias of the
    call's `-c` options or the repo's config; UNPLACED_COMMIT (truthy) when it does so through a `!` shell alias,
    whose commit may land in any directory; False otherwise. A directory of None reads no alias config. Fails open
    when git cannot be run or the alias is unset."""
    if git_call_commits(words):
        return True
    options, index = git_options(words)
    if index == len(words):
        return False
    subcommand = words[index]
    # git never reads an alias named like a subcommand it defines itself.
    if subcommand in PLAIN_GIT_SUBCOMMANDS or subcommand in COMMITTING_SUBCOMMANDS or depth >= ALIAS_DEPTH_LIMIT:
        return False
    expansion = config_value("alias." + subcommand, options, directory, git_timeout)
    if not expansion:
        return False
    next_depth = depth + 1
    return alias_commit_text(words, index, expansion, directory, next_depth, shell_text_commits, git_timeout)
