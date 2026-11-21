"""shell_write_paths.py: plain helpers for the paths a shell write names, with no rule of any one gate.

Toolkit scripts import it after putting scripts/lib on sys.path."""
import os
import subprocess

import shell_directory
from code_text import trim
from hook_input import bash_basename, bash_dirname


def is_stream_or_device(word):
    """True for a target word that is no file: a stream (`&1`) or a /dev file. `..` is collapsed first, so
    `/dev/../home/x` is a file."""
    word = trim(word)
    return word.startswith("&") or os.path.normpath(word).startswith("/dev/")


def resolve_target(raw, cwd):
    """The path a write target word names against cwd, or None for a stream (`&1`), an option or a /dev file."""
    path = shell_directory.path_word(trim(raw))
    if not path or path.startswith("-") or is_stream_or_device(path):
        return None
    if not shell_directory.path_word_is_absolute(raw):
        path = cwd + "/" + path
    return path


def is_git_tracked(path):
    """True when git lists the file in the folder of path."""
    command = ["git", "-C", bash_dirname(path), "ls-files", "--error-unmatch", "--", bash_basename(path)]
    try:
        finished = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        return False
    return finished.returncode == 0
