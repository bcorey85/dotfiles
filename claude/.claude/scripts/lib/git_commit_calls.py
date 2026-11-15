"""git_commit_calls.py: whether a git call makes a commit, read from its words (git_call_commits) or its text
(COMMITTING_CALL). The one owner of which subcommands commit and which flags stop them, and of the placement of
each committing call in the directory it lands in (git_commit_dirs)."""
import posixpath
import re
from typing import NamedTuple

import script_utils
from shell_command import (
    LAUNCHER_PROGRAMS,
    ShellDirectory,
    command_after_wrappers,
    git_c_directory,
    git_c_settings,
    git_options,
    group_closes,
    is_git_word,
    options_before_separator,
    split_command_steps,
    split_simple_commands,
    without_flag_values,
    wrapper_moves_directory,
)

# Subcommands that make a commit when they run; `rebase` does so only with `--continue` or `--skip`.
COMMITTING_SUBCOMMANDS = ("commit", "merge", "cherry-pick", "revert", "am")
# Flags that end or leave a merge, cherry-pick, revert or am in progress, so the call makes no commit. git refuses
# them beside any other argument, so they count only as the call's one argument.
SEQUENCE_ENDING_FLAGS = ("--abort", "--quit")
# Flags that make a call leave its result uncommitted, or (`am`) only show the current patch. `am --skip` is not
# one: it drops the current patch and applies and commits the rest of the series, as `rebase --skip` does.
NO_COMMIT_FLAGS = {"merge": ("--no-commit", "--squash", "--ff-only"), "cherry-pick": ("-n", "--no-commit"),
                   "revert": ("-n", "--no-commit"), "am": ("--show-current-patch",)}
# The options that take the next word as their value, which may be any text, so a stop flag given as one is no stop.
VALUE_OPTIONS = {
    "merge": ("-m", "-F", "-s", "-X", "--file", "--strategy", "--strategy-option", "--into-name", "--cleanup"),
    "am": ("--exclude", "--include", "--directory"),
    "cherry-pick": ("-m", "--mainline", "--strategy", "-X", "--strategy-option", "--cleanup"),
    "revert": ("-m", "--mainline", "--strategy", "-X", "--strategy-option", "--cleanup"),
}
# The flags of `merge` that choose whether it commits; the last one among the arguments wins.
COMMIT_FLAGS = ("--commit", "--no-commit")
# `--commit` after `--squash` undoes it, as does `--no-squash`.
SQUASH_FLAGS = ("--commit", "--squash", "--no-squash")
# The flags that choose whether a merge fast-forwards; the last one among the arguments wins.
FF_FLAGS = ("--ff", "--no-ff", "--ff-only")
# For each stopping flag, the later flags of its group that undo it: git takes the last flag of a group.
OVERRIDING_FLAGS = {
    ("merge", "--no-commit"): ("--commit",), ("merge", "--squash"): ("--commit", "--no-squash"),
    ("merge", "--ff-only"): ("--ff", "--no-ff"),
}


def stopping_flags(subcommand):
    """The flags that make a call of `subcommand` commit nothing. `commit` has none: a message may hold any text."""
    if subcommand == "commit":
        return ()
    return SEQUENCE_ENDING_FLAGS + NO_COMMIT_FLAGS.get(subcommand, ())


def argument_word_pattern(subcommand):
    """The text pattern for one argument of a call of `subcommand`, up to a quote, blank or operator: a value option
    with the word after it (its value) counts as one argument."""
    word = r"[^\s;&|\"']+"
    value_options = VALUE_OPTIONS.get(subcommand, ())
    if not value_options:
        return word
    value_option = "(?:" + "|".join(re.escape(option) for option in value_options) + r")(?![\w-])"
    return "(?:" + value_option + r"[ \t]+" + word + "|(?!" + value_option + ")" + word + ")"


def overrider_pattern(overrider):
    """The text pattern for one overriding flag: the value of a `--name=value` flag is read in any case."""
    name, equals, value = overrider.partition("=")
    if not equals:
        return re.escape(overrider)
    return re.escape(name + equals) + "(?i:" + re.escape(value) + ")"


def stop_flag_pattern(subcommand, flag):
    """The text pattern, read after a committing subcommand, for one of its stopping flags. A sequence-ending flag
    counts directly after the subcommand only. Any other flag counts anywhere among the arguments, but not as the
    value of a value option."""
    flag_pattern = re.escape(flag) + r"(?![\w-])"
    if flag in SEQUENCE_ENDING_FLAGS:
        return r"[ \t]+" + flag_pattern
    # The last flag of a group wins (OVERRIDING_FLAGS), so a stopping flag does not stop the call when a later flag of
    # its group undoes it.
    overriders = OVERRIDING_FLAGS.get((subcommand, flag), ())
    later_override = ""
    if overriders:
        names = "|".join(overrider_pattern(overrider) for overrider in overriders)
        later_override = r"(?![^;&|\n\"']*[ \t](?:" + names + r")(?![\w-]))"
    return r"(?:[ \t]+" + argument_word_pattern(subcommand) + r")*[ \t]+" + flag_pattern + later_override


def committing_call_alternative(subcommand):
    """The text pattern for one committing subcommand, not followed in its simple command (up to a quote) by a flag
    of stopping_flags (stop_flag_pattern)."""
    pattern = re.escape(subcommand) + r"\b(?!-)"
    flags = stopping_flags(subcommand)
    if not flags:
        return pattern
    stops = [stop_flag_pattern(subcommand, flag) for flag in flags]
    return pattern + r"(?!" + "|".join(stops) + ")"


# The subcommand words of a call that makes a commit, for the patterns that read text shlex cannot split.
# `(?!-)` after one: `git commit-tree`, `git commit-graph` and `git merge-base` write no commit on a branch.
COMMITTING_CALL = ("(?:" + "|".join(committing_call_alternative(name) for name in COMMITTING_SUBCOMMANDS)
                   + r"|rebase[ \t]+--(?:continue|skip)\b(?!-))")


def last_flag(arguments, flags):
    """The last of `flags` among the arguments, or None when none is there."""
    found = None
    for argument in arguments:
        if argument in flags:
            found = argument
    return found


def merge_stays_uncommitted(arguments):
    """True when the last of COMMIT_FLAGS is `--no-commit`, or the last of SQUASH_FLAGS is `--squash`, or the last of
    FF_FLAGS is `--ff-only`."""
    if last_flag(arguments, COMMIT_FLAGS) == "--no-commit":
        return True
    if last_flag(arguments, SQUASH_FLAGS) == "--squash":
        return True
    return last_flag(arguments, FF_FLAGS) == "--ff-only"


def config_value(name, options, directory, git_timeout):
    """The value of the config key `name` for a call with git options `options` run in `directory`: the call's own `-c`
    option first, then the config of `directory`; "" when it is unset; None when it cannot be read (git fails or times
    out, or `directory` is None). Section and key names are not case-sensitive, so `name` must have no subsection,
    whose case git keeps."""
    from_options = git_c_settings(options).get(name.lower())
    if from_options is not None:
        return from_options
    if directory is None:
        return None
    # `--default ""` makes an unset key exit 0, so None means the read itself failed or timed out.
    return script_utils.git_output(directory, "config", "--default", "", "--get", name, timeout=git_timeout)


def git_call_commits(words):
    """True when the git call in `words` makes a commit by itself: `commit`, `merge`, `cherry-pick`, `revert` or `am`,
    unless the call is `--abort` or `--quit` alone or leaves the result uncommitted
    (NO_COMMIT_FLAGS), or `rebase --continue` or `rebase --skip`. A stop flag given as an option's value (VALUE_OPTIONS)
    is no stop. An alias that expands to one of these is the caller's to read, since only the repo's config names
    it."""
    _options, index = git_options(words)
    if index == len(words):
        return False
    subcommand = words[index]
    arguments = options_before_separator(words[index + 1:])
    if subcommand == "rebase":
        return "--continue" in arguments or "--skip" in arguments
    if subcommand not in COMMITTING_SUBCOMMANDS:
        return False
    if subcommand == "commit":
        return True
    arguments = without_flag_values(arguments, VALUE_OPTIONS.get(subcommand, ()))
    if len(arguments) == 1 and arguments[0] in SEQUENCE_ENDING_FLAGS:
        return False
    if subcommand == "merge":
        return not merge_stays_uncommitted(arguments)
    if subcommand == "am":
        arguments = ["--show-current-patch" if argument.startswith("--show-current-patch=") else argument
                     for argument in arguments]
    return not any(flag in arguments for flag in NO_COMMIT_FLAGS[subcommand])


def runs_commit_call(words):
    """True when the simple command has a git call (git_call_starts) that makes a commit: commit, merge,
    cherry-pick, revert, am, rebase --continue or --skip (git_call_commits). A git word past index 0 counts
    only behind a LAUNCHER_PROGRAMS program or `find -exec`/`-execdir` (runs_through_launcher).
    Aliases are not read here; git_alias_commits.git_words_make_commit judges them (through placement)."""
    words = command_after_wrappers(words)
    return any(git_call_commits(words[index:]) for index in git_call_starts(words))


# What a commit_call answers, besides True, for a commit that lands where no directory names (a `!` shell alias).
UNPLACED_COMMIT = "unplaced-commit"


class CommitDirs(NamedTuple):
    """What git_commit_dirs read: the directory of each placed commit, the words of each commit it could not place,
    and the words of the first committing call of either kind (None when the command holds none)."""
    commit_dirs: list
    unplaced: list
    first_call_words: list | None


class PlacedCall(NamedTuple):
    """Whether a git call makes a commit, and the directory it lands in (None when it cannot be placed)."""
    committing: bool
    directory: str | None


def runs_through_launcher(words):
    """True when the command's words start with a LAUNCHER_PROGRAMS program or a `find` with `-exec`/`-execdir`."""
    if not words:
        return False
    program = posixpath.basename(words[0])
    if program in LAUNCHER_PROGRAMS:
        return True
    return program == "find" and any(word in ("-exec", "-execdir") for word in words)


def git_call_starts(words):
    """The indexes in `words` where a git call starts: 0 when the command is git itself (its other words are its
    arguments), else each git word of a launcher's command (runs_through_launcher), else none. Takes words already
    past their wrappers (command_after_wrappers): the caller peels them once and indexes the same list."""
    if not words:
        return []
    if is_git_word(words[0]):
        return [0]
    if not runs_through_launcher(words):
        return []
    return [index for index, word in enumerate(words) if is_git_word(word)]


def committing_calls(words, simple_command, current_dir, start_dir, commit_call):
    """Each (git_words, PlacedCall) for a committing git call in `words`, the simple command after its wrappers."""
    for index in git_call_starts(words):
        git_words = words[index:]
        placed = place_commit_call(git_words, simple_command, current_dir, start_dir, commit_call)
        if placed.committing:
            yield git_words, placed


def place_commit_call(git_words, simple_command, current_dir, start_dir, commit_call):
    """The PlacedCall for the git call `git_words` of `simple_command`, run where the shell stands (`current_dir`)."""
    # An unplaced call gets its alias lookup in the start directory, a guess at where it runs.
    if current_dir is None or wrapper_moves_directory(simple_command):
        return PlacedCall(bool(commit_call(git_words, start_dir)), None)
    commit_directory = git_c_directory(git_words, current_dir)
    if commit_directory is None:
        return PlacedCall(bool(commit_call(git_words, current_dir)), None)
    commit_answer = commit_call(git_words, commit_directory)
    if commit_answer == UNPLACED_COMMIT:
        return PlacedCall(True, None)
    return PlacedCall(bool(commit_answer), commit_directory)


def git_commit_dirs(command, start_dir, commit_call):
    """The directory of each `git commit` (or other call that makes a commit:
    `commit_call(words, directory)` says which, answering True,
    or UNPLACED_COMMIT) in the command, read by what the command names: `start_dir`, moved by
    each `cd`, `pushd`, `popd` and `cd -` the command holds and by each `git -C <dir>` of the call. A `cd` inside
    `( ... )` ends where the group closes. A commit left out: one after a move to a folder the shell expands or to
    nowhere known (a `popd` or `cd -` with no earlier directory), one an `env`/`sudo` `-C` moves, one with options
    git_c_directory does not follow (`--git-dir`, `--work-tree`, a `-c` that is neither an alias nor an editor
    setting), and one commit_call answers UNPLACED_COMMIT for; the words of each go in `unplaced`. Returns a
    CommitDirs, with both lists [] when the command holds no such commit; None when the command cannot be read (the
    caller uses `start_dir`)."""
    shell = ShellDirectory(start_dir)
    outer_shells = []
    commit_dirs = []
    unplaced = []
    first_call_words = None
    for _operator, step in split_command_steps(command):
        try:
            simple_commands = split_simple_commands(step)
        except ValueError:
            return None
        opened, closed = group_closes(step)
        outer_shells.extend([shell.saved()] * opened)
        for simple_command in simple_commands:
            words = command_after_wrappers(simple_command)
            if not words:
                continue
            if words[0] in ("cd", "pushd", "popd"):
                shell.apply(words)
                continue
            for git_words, placed in committing_calls(words, simple_command, shell.current, start_dir, commit_call):
                first_call_words = first_call_words or git_words
                if placed.directory is None:
                    unplaced.append(git_words)
                elif placed.directory not in commit_dirs:
                    commit_dirs.append(placed.directory)
        for _group in range(min(closed, len(outer_shells))):
            shell.restore(outer_shells.pop())
    return CommitDirs(commit_dirs, unplaced, first_call_words)
