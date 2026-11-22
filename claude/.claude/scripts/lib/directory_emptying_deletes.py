"""Which directories the plain `rm` calls of one shell command would empty.

A gate denies `rm -r <dir>`. Deleting the same directory's files one call at a time, or in one call that names every
file, gives the same result and passes that check. A hook keeps no state between calls, so this module reads the file
system: a directory is emptied when the targets of the command's plain `rm` calls cover every entry it holds now.
A recursive `rm` is left to the gate that denies it.

Known limits, with no code for them: a brace target (`rm d2/{a,b}`) is skipped as an unread mark, so it never counts
toward emptying; a `cd` inside `$( ... )` is followed and stays in force after the substitution closes, while a
`cd` inside backticks is not followed; a folder named as a target (`rm d/a d/sub d/b`) counts as an entry removed,
though a plain `rm` fails on a folder.
"""
import glob
import os
import pathlib
import re
import shlex

import hook_input
import script_utils
import shell_command
import shell_command_words
import shell_directory
import shell_expansion
import shell_statements
import shell_steps

RM_COMMAND = "rm"
# Build and cache folders: emptying one is routine cleanup, as the recursive-delete gate allows.
SAFE_FOLDER_NAMES = ("node_modules", "dist", ".cache", "coverage", ".next", ".nuxt", ".turbo", ".pytest_cache",
                     ".mypy_cache", ".ruff_cache", ".tox")
GLOB_CHARACTERS = re.compile(r"[*?\[]")
RECURSIVE_LETTERS = re.compile(r"[rR]")


def is_recursive_option(word):
    """True for `--recursive` and a short-option cluster that holds `r` or `R`."""
    if word == "--recursive":
        return True
    if word.startswith("--"):
        return False
    return bool(RECURSIVE_LETTERS.search(word[1:]))


def rm_target_words(words):
    """The target words of one `rm` call: every word that is not an option, and every word after `--`. None for a
    recursive call."""
    targets = []
    options_ended = False
    for word in words[1:]:
        if options_ended:
            targets.append(word)
            continue
        if word == "--":
            options_ended = True
            continue
        if word.startswith("-") and len(word) > 1:
            if is_recursive_option(word):
                return None
            continue
        targets.append(word)
    return targets


def is_unread_target(target):
    """True for a target with a mark the gate does not read: `$`, a backtick, a brace or `~user`. Glob characters are
    read, so they are removed before the check."""
    return bool(shell_directory.UNREAD_FOLDER.search(GLOB_CHARACTERS.sub("", target)))


def expanded_target_paths(raw_target, target, directory):
    """The real paths a target names when `rm` runs in `directory`; an unquoted glob gives the entries it matches. A
    quoted glob character is a literal name."""
    # The shell expands `~` only when the raw word starts with an unquoted one; a quoted `~` is a literal name.
    if raw_target.startswith("~"):
        target = os.path.expanduser(target)
    if not shell_expansion.unquoted_expanding_word(raw_target):
        return [script_utils.resolved_parent_path(os.path.join(directory, target))]
    # The folder is no part of the pattern: its own `[`, `*` or `?` must stay literal.
    if os.path.isabs(target):
        matches = glob.glob(target)
    else:
        matches = [os.path.join(directory, match) for match in glob.glob(target, root_dir=directory)]
    return [script_utils.resolved_parent_path(match) for match in matches]


def step_target_paths(raw_words, directory):
    """The real paths the `rm` step `raw_words` deletes, run in `directory`; none for a recursive call or a step run
    in a directory the gate does not know."""
    if directory is None:
        return []
    raw_targets = rm_target_words(raw_words)
    if raw_targets is None:
        return []
    paths = []
    for raw_target in raw_targets:
        target = shell_command_words.unquoted_word(raw_target)
        # An empty target (`''`) names no file; joined to the folder it would name the folder itself.
        if not target or is_unread_target(target):
            continue
        paths.extend(expanded_target_paths(raw_target, target, directory))
    return paths


def placed_raw_words(placed):
    """The raw words of the placed simple command, quotes kept and redirections left out: the raw command of its step
    whose words, unquoted, are the placed command's. When none matches (a word that glues a quoted part to more text
    is cut differently), the placed command's resolved words stand in for them, quoted again so that unquoting them
    gives each word back whole."""
    for raw_words in shell_command.parse_raw_simple_commands(placed.step):
        unquoted = [shell_command_words.unquoted_word(raw_word) for raw_word in raw_words]
        if unquoted == placed.simple_command:
            return raw_words
    return [shlex.quote(word) for word in placed.simple_command]


def rm_raw_words(placed):
    """The words of the `rm` call of the placed simple command, from the `rm` word on; None when its command is not
    `rm`."""
    raw_words = placed_raw_words(placed)
    index = shell_command_words.command_word_index(raw_words, RM_COMMAND)
    if index is None:
        return None
    return raw_words[index:]


def rm_target_paths(command, directory):
    """The set of real paths that the plain `rm` steps of the command delete, following `cd` between the steps and
    ending a `cd` inside `( ... )` where the group closes (a `$( ... )` inside a step is no group). A `docker exec`
    call runs in a container, so it is not read. This check fails open: a step the shell reader cannot parse is
    reported on stderr and skipped, and a `cd` in it leaves the later deletes unplaced until the enclosing group
    closes."""
    code = shell_statements.shell_code(command)
    paths = set()
    placed_calls = shell_steps.placed_commands(code, os.path.abspath(directory), peel_containers=False,
                                               skip_unread=True)
    for placed in placed_calls:
        if not shell_command_words.word_names_command(placed.words[0], RM_COMMAND):
            continue
        raw_words = rm_raw_words(placed)
        if raw_words is None:
            continue
        paths.update(step_target_paths(raw_words, placed.directory))
    return paths


def is_safe_to_empty(folder):
    """True for a folder under a temp root or inside a build or cache folder."""
    if hook_input.is_under_temp_dir(folder):
        return True
    return any(part in SAFE_FOLDER_NAMES for part in pathlib.Path(folder).parts)


def is_emptied_by(folder, paths):
    """True when the folder holds at least one entry and every entry is in `paths`. A folder the gate cannot list is
    not reported: this check fails open, as a delete in a folder that cannot be read is not what it is meant to stop."""
    try:
        entries = os.listdir(folder)
    except OSError:
        return False
    if not entries:
        return False
    return all(os.path.join(folder, entry) in paths for entry in entries)


def emptied_directories(command, directory):
    """The sorted folders that the command's plain `rm` calls would empty, `directory` being where it starts."""
    paths = rm_target_paths(command, directory)
    parents = {os.path.dirname(path) for path in paths}
    return sorted(folder for folder in parents
                  if not is_safe_to_empty(folder) and is_emptied_by(folder, paths))
