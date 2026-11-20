"""Option facts for git subcommands: false config values, the protected branch names,
and how `checkout`, `switch` and `restore` options take their values. The git discipline gate and
git_destructive_calls.py import them from here. git's own options before the subcommand live in
shell_command.git_options."""
from shell_command import flags_before_value, is_long_prefix, is_short_cluster

PROTECTED_BRANCHES = {"main", "master"}
# Every value git reads as false for a boolean setting; the config values are already lowercased.
GIT_FALSE_VALUES = {"false", "no", "off", "0", ""}
# git accepts `--c` as `--conflict` on checkout; on switch `--c` is ambiguous and git refuses it, so the wider match
# only denies calls git would reject.
CONFLICT_SHORTEST = "--c"
# `restore -s<tree>` and `-U<n>` take a value, so the letters after them are not flags.
RESTORE_VALUE_LETTERS = "sU"
# `checkout -b|-B` and `switch -c|-C` take the new branch name, so the letters after them are not flags.
SWITCH_VALUE_LETTERS = {"checkout": "bB", "switch": "cC"}


def restore_stages(argument):
    """True when one `restore` option is `--staged` (or an abbreviation) or a short cluster holding `S`."""
    if is_short_cluster(argument):
        return "S" in flags_before_value(argument, RESTORE_VALUE_LETTERS)
    return is_long_prefix(argument, "--staged", "--st")


def restore_restores_worktree(argument):
    """True when one `restore` option is `--worktree` (or an abbreviation) or a short cluster holding `W`."""
    if is_short_cluster(argument):
        return "W" in flags_before_value(argument, RESTORE_VALUE_LETTERS)
    return is_long_prefix(argument, "--worktree", "--w")


def discards_on_switch(argument, value_letters):
    """True for `-f`, `--force` and `--discard-changes`, which reset the index to the target branch. value_letters are
    the cluster letters that take the branch name."""
    if is_short_cluster(argument):
        return "f" in flags_before_value(argument, value_letters)
    return is_long_prefix(argument, "--force", "--f") or is_long_prefix(argument, "--discard-changes", "--di")


def is_orphan_option(argument):
    """True for `--orphan`, its abbreviations, and `--orphan=<branch>`."""
    option_name = argument.split("=")[0]
    return is_long_prefix(option_name, "--orphan", "--or")


def takes_separate_value(argument):
    # `--conflict <style>`, `--pathspec-from-file <file>`, `--unified <n>`, `--inter-hunk-context <n>` and a short
    # cluster ending in `U` (`-U <n>`, `-pU <n>`) carry their value in the next word.
    if is_short_cluster(argument):
        return argument.endswith("U")
    if is_long_prefix(argument, "--conflict", CONFLICT_SHORTEST):
        return True
    if is_long_prefix(argument, "--unified", "--u"):
        return True
    if is_long_prefix(argument, "--inter-hunk-context", "--in"):
        return True
    return is_long_prefix(argument, "--pathspec-from-file", "--pathspec-fr")
