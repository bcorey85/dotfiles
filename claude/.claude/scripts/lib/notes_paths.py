"""A repo's notes paths: the Markdown files a commit ships without review, and that the tree a review credits leaves
out, so a plan ticked after the review keeps the commit credit.

A notes path is a Markdown file under the repo's top-level docs/ folder, or a Markdown file at a path listed in the
repo's `.claude/notes-paths` (one entry per line: a `/` ending is a folder prefix, else an exact file; blank lines and
`#` lines are skipped). The list is read from HEAD, so an edit that is only staged or in the working tree grants
nothing. An entry must be a normalized repo-root-relative literal.
"""
import script_utils

DOCS_FOLDER = "docs/"
NOTES_SUFFIX = ".md"
NOTES_PATHS_FILE = ".claude/notes-paths"
COMMITTED_LIST = "HEAD:" + NOTES_PATHS_FILE
# Characters a shell or git would expand in a pathspec, and a newline.
EXPANDING_CHARS = set("*?[]{}$`~\\\n")
NOTES_ENTRY_FORM = ("a normalized repo-root-relative literal: no leading `/` or `./`, no glob, no `..`; "
                    "a folder ends in `/`")


def committed_list(top, timeout=None):
    """The text of the repo's `.claude/notes-paths` at HEAD, or None with no file, no HEAD or a git failure."""
    return script_utils.git_output(top, "show", COMMITTED_LIST, timeout=timeout)


def notes_entries(text):
    """(line number, entry) of each entry of a notes-paths list: blank lines and `#` lines are skipped."""
    lines = [(number, line.strip()) for number, line in enumerate(text.splitlines(), 1)]
    return [(number, line) for number, line in lines if line and not line.startswith("#")]


def notes_entry_error(entry):
    """Why a `.claude/notes-paths` entry is not a normalized repo-relative literal, or None when it is."""
    segments = entry.removesuffix("/").split("/")
    if EXPANDING_CHARS & set(entry) or any(segment in ("", ".", "..") for segment in segments):
        return f"entry {entry!r} is not {NOTES_ENTRY_FORM}"
    return None


def notes_list_errors(text, name):
    """One `name:line: message` per entry of the list text that is not a normalized repo-relative literal."""
    errors = []
    for number, entry in notes_entries(text):
        error = notes_entry_error(entry)
        if error:
            errors.append(f"{name}:{number}: {error}")
    return errors


def committed_notes_list(top, timeout=None):
    """(entries, errors) of the repo's committed list. No list or a git failure gives ([], []). Any bad entry gives
    ([], errors): the caller decides how to report them."""
    listed = committed_list(top, timeout=timeout)
    if listed is None:
        return [], []
    errors = notes_list_errors(listed, COMMITTED_LIST)
    if errors:
        return [], errors
    return [entry for _, entry in notes_entries(listed)], []


def matches_notes_entry(path, entry):
    """True when the path is under the folder the entry names (it ends in `/`) or is the file it names."""
    if entry.endswith("/"):
        return path.startswith(entry)
    return path == entry


def is_notes_path(path, declared_paths):
    """True when the repo-root-relative path is Markdown under docs/ or at a path one of the entries names."""
    if not path.endswith(NOTES_SUFFIX):
        return False
    if path.startswith(DOCS_FOLDER):
        return True
    return any(matches_notes_entry(path, entry) for entry in declared_paths)


def exclude_pathspecs(declared_paths):
    """The git pathspecs that leave out of a repo-root `git diff` exactly the tracked paths is_notes_path counts."""
    specs = [f":(exclude,glob){DOCS_FOLDER}**/*{NOTES_SUFFIX}"]
    for entry in declared_paths:
        if entry.endswith("/"):
            specs.append(f":(exclude,glob){entry}**/*{NOTES_SUFFIX}")
        elif entry.endswith(NOTES_SUFFIX):
            specs.append(f":(exclude,literal){entry}")
    return specs
