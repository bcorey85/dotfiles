"""script_utils.py: helpers for toolkit scripts that read plain text, lines, paths and files and need no module rule.

Installed as ~/.claude/scripts/lib/script_utils.py. Scripts under ~/.claude/scripts/ import it from there by adding
that directory to sys.path."""
import argparse
import datetime
import difflib
import json
import os
import pathlib
import re
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import time
import uuid
from collections import namedtuple

FENCE_OPEN = re.compile(r"^\s*(`{3,}|~{3,})")
MARKDOWN_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
INLINE_CODE_OR_COMMENT_OPEN = re.compile(r"`[^`]*`|<!--")
PATH_CHARS = r"\w@.\-"
PATH_TEXT = rf"[{PATH_CHARS}/]+\.\w+"


def line_suffix(approx="", gap=""):
    """The regex of a `:12-20, 30` line part; `approx` and `gap` let each number take a `~` and the list take spaces."""
    return rf":{approx}\d+(?:[-,]{gap}{approx}\d+)*"


# A backtick may close between the path and the line (`path`:12).
PATH_LINE = re.compile(rf"`?({PATH_TEXT}`?{line_suffix()})`?")
# The code-reviewer's blocker tag, bold or plain; callers anchor it and pick the case rule.
BLOCKER_TAG_PATTERN = r"\*{0,2}\[blocker\]\*{0,2}"
FILE_NAME = re.compile(rf"^{PATH_TEXT}(?::\d|$)")
# A quoted span of a reviewer finding. It differs from `message_text.QUOTED_SPAN`: straight double quotes only,
# single quotes bounded by non-word characters (an apostrophe inside a word opens none), and a backtick span that
# may run over lines.
FINDING_QUOTED_SPAN = re.compile(r"\"[^\"\n]*\"|(?<!\w)'[^'\n]*'(?!\w)|`[^`]*`")
BACKTICKED = re.compile(r"`([^`]+)`")
# Subagent types: the agents that change code, and the agents that review it (code-reviewer, perf-reviewer-deep, ...).
CODERS = re.compile(r"^(backend-|frontend-)?coder(-deep)?$")
REVIEWERS = re.compile(r"^([a-z]+-)*reviewer(-deep)?$")
# The agent the /code skill forks into (its `agent:` line). It has no Edit or Write tool.
FORK_AGENT_TYPE = "code-fork"
# A markdown file's opening `---` frontmatter block, and one `- name` line of a block list in it.
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---[ \t]*(?:\n|\Z)", re.DOTALL)
FRONTMATTER_LIST_ITEM = re.compile(r"^\s+-\s+(.+?)\s*$")
# The line that starts the stamp the coder gate appends to a hand-back message. Everything after it is the gate's text.
HAND_BACK_GATE_MARKER = "\n\nHAND-BACK GATE:"
TIMEOUT_EXIT_CODE = 124
COMMAND_NOT_FOUND_EXIT_CODE = 127
REPO_NAME_SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "tools" / "repo-name"
REPO_NAME_TIMEOUT_SECONDS = 10
CONVERSATION_RECORD_TYPES = ("user", "assistant")
TRANSCRIPT_UNREADABLE = "transcript unreadable"
ENV_NAME = r"[A-Za-z_][A-Za-z0-9_]*"
# A literal value is plain characters or a quoted string with no `$`, backtick, `;`, `&`, `|`, `<`, `>` (and no
# backslash in a double-quoted one): the shell would run or expand anything else, so it is not a setting that can be
# copied. A plain word has no `~` either: the shell expands it at the start of a value and after a `:`, which
# shlex.split does not.
ENV_VALUE = r""""[^"$`;&|<>\\]*"|'[^'$`;&|<>]*'|[^\s"'$`;&|<>()\\~]*"""
ENV_ASSIGNMENT = re.compile(rf"({ENV_NAME})=({ENV_VALUE})")
# The NAME= start of one shell word, after shlex.split.
ENV_ASSIGNMENT_NAME = re.compile(rf"{ENV_NAME}=")
# What must follow the assignments: a word that is not another assignment and does not start with a shell control
# operator, a comment, a grouping or a negation. Without it "A=1 && cargo test" would read "&&" as the command.
COMMAND_WORD_AHEAD = rf"(?!{ENV_NAME}=)(?![;&|<>()#{{}}!])(?=\S)"
# The NAME=value words a command line starts with, each followed by whitespace, which the shell passes to the command.
# A command word must follow them. Only literal values: this reading builds the settings that get copied.
ENV_ASSIGNMENTS = re.compile(rf"(?:{ENV_NAME}=(?:{ENV_VALUE})\s+)+{COMMAND_WORD_AHEAD}")
# The same words with any value, one that expands a variable or runs a command included (`PATH=/x:$PATH cargo test`):
# the shell passes those to the command as well, so a reading that only finds where the command starts accepts them.
ENV_PREFIX_VALUE = r"""(?:"[^"]*"|'[^']*'|\$\([^)]*\)|[^\s"'`;&|<>()])*"""
ENV_PREFIX = re.compile(rf"(?:{ENV_NAME}={ENV_PREFIX_VALUE}\s+)+{COMMAND_WORD_AHEAD}")


def environment_from_assignments(assignments):
    """{name: value} for NAME=value shell words such as `A=1` or `B="two words"`. Raises ValueError on a word that is
    not one."""
    environment = {}
    for assignment in assignments:
        try:
            words = shlex.split(assignment)
        except ValueError:
            words = []
        is_one_assignment = len(words) == 1 and ENV_ASSIGNMENT_NAME.match(words[0])
        if not is_one_assignment:
            raise ValueError(f"needs NAME=value, got {assignment!r}")

        name, value = words[0].split("=", 1)
        environment[name] = value
    return environment


def last_per_name(assignments):
    """The `NAME=value` words with one word per name: the last one given for a name wins."""
    chosen = {}
    for assignment in assignments:
        chosen[assignment.split("=", 1)[0]] = assignment
    return list(chosen.values())


def repo_name_from_url(url):
    """The last part of a git remote URL without `.git`: `git@host:org/app.git` and `https://host/org/app/` give app."""
    return re.split(r"[/:]", url.rstrip("/"))[-1].removesuffix(".git")


def fenced_line_indexes(lines):
    """Indexes of the lines inside a fenced code block, the fence lines themselves included. A fence is closed by
    the same character, at least as long as the opener. A fence that is never closed runs to the last line."""
    fenced = set()
    for block, _is_closed in _fenced_blocks(lines):
        fenced.update(block)
    return fenced


def closed_fence_indexes(lines):
    """Same as `fenced_line_indexes`, but a fence that is never closed is left out: only blocks with a closing fence
    count."""
    fenced = set()
    for block, is_closed in _fenced_blocks(lines):
        if is_closed:
            fenced.update(block)
    return fenced


def _fenced_blocks(lines):
    """Each fenced block as (its line indexes, whether a closing fence ended it), in order."""
    blocks = []
    block = []
    opener = None
    for index, line in enumerate(lines):
        is_opening = opener is None
        if is_opening:
            opener = _fence_opener(line)
        if opener is None:
            continue
        block.append(index)
        if not is_opening and _closes_fence(line, opener):
            blocks.append((block, True))
            block = []
            opener = None
    if block:
        blocks.append((block, False))
    return blocks


def _fence_opener(line):
    """The fence text that opens a fenced block on this line, or None."""
    match = FENCE_OPEN.match(line)
    if not match:
        return None
    return match.group(1)


def _closes_fence(line, opener):
    """Whether the line closes a fence opened with `opener`: the same character, at least as long."""
    stripped = line.strip()
    if not stripped:
        return False
    return stripped[0] == opener[0] and set(stripped) == {opener[0]} and len(stripped) >= len(opener)


JSON_TYPE_NAMES = ((str, "a string"), (bool, "a boolean"), (int, "a number"), (float, "a number"), (list, "a list"),
                   (dict, "an object"), (type(None), "null"))


def json_type_name(value):
    """The name of a decoded JSON value's type, as a phrase for an error message."""
    return next(name for kind, name in JSON_TYPE_NAMES if isinstance(value, kind))


def is_int(value):
    """Whether a decoded JSON value is an integer; a boolean is not."""
    return isinstance(value, int) and not isinstance(value, bool)


def positive_int(text):
    """An argparse type: the integer in text, which must be above zero."""
    try:
        number = int(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"{text!r} is not an integer") from error
    if number <= 0:
        raise argparse.ArgumentTypeError(f"{text!r} is not a positive integer")
    return number


def is_string_list(value):
    """Whether a decoded JSON value is a list whose every entry is a string."""
    return isinstance(value, list) and all(isinstance(entry, str) for entry in value)


def is_nonblank_string_list(value):
    """Whether a decoded JSON value is a list whose every entry is a string with text in it."""
    return is_string_list(value) and all(entry.strip() for entry in value)


def help_requested(arguments):
    # A stored check command is one argument holding a whole shell command, so it never equals either flag.
    return any(argument in ("--help", "-h") for argument in arguments)


def json_string_list(text):
    """The list of strings that the JSON text holds, or None when the text is not JSON or not a list of strings."""
    try:
        loaded = json.loads(text)
    except ValueError:
        return None
    return loaded if is_string_list(loaded) else None


def unfenced_text(text):
    """The text without whitespace around it and without one wrapping code fence."""
    text = text.strip()
    opener = FENCE_OPEN.match(text)
    if not opener:
        return text
    fence = opener.group(1)
    fenced_lines = text.splitlines()[1:]
    closer = fenced_lines[-1].strip() if fenced_lines else ""
    if closer and set(closer) == {fence[0]} and len(closer) >= len(fence):
        fenced_lines = fenced_lines[:-1]
    return "\n".join(fenced_lines).strip()


def heading_section_indexes(lines, heading_text):
    """0-based indexes of the lines under every markdown heading whose text is exactly heading_text, the heading line
    itself left out. A section runs to the next heading of its own level or a higher one; a deeper heading stays inside
    it. A `#` line inside a fenced block is not a heading, and the fenced lines belong to the section that holds them.
    Returns [] when no heading matches."""
    fenced = fenced_line_indexes(lines)
    indexes = []
    open_level = None
    for index, line in enumerate(lines):
        heading = None if index in fenced else MARKDOWN_HEADING.match(line)
        if heading is None and open_level is not None:
            indexes.append(index)
            continue
        if heading is None:
            continue

        level = len(heading.group(1))
        if open_level is not None and level <= open_level:
            open_level = None
        if open_level is None and heading.group(2).strip() == heading_text:
            open_level = level
        elif open_level is not None:
            indexes.append(index)
    return indexes


def top_level_sections(lines):
    """0-based indexes of the lines that start a `## ` section, in order. A `## ` line inside a fenced code block is
    not a heading."""
    fenced = fenced_line_indexes(lines)
    return [index for index, line in enumerate(lines) if line.startswith("## ") and index not in fenced]


def text_similarity(first, second):
    """How alike two strings are, from 0 to 1. Long strings are compared in full, with no junk heuristic.

    For two token lists or other sequences, use `sequence_similarity` (bounded edit distance, n-gram overlap)."""
    return difflib.SequenceMatcher(None, first, second, autojunk=False).ratio()


def rounded_percent(part, total):
    """`part` as a whole percent of `total`, rounded half up; 0 when `total` is 0."""
    if total == 0:
        return 0
    return (100 * part + total // 2) // total


def or_list(words):
    """An English list of plain strings: "a", "a or b", "a, b or c". An empty list gives an empty string."""
    if len(words) < 2:
        return "".join(words)
    return ", ".join(words[:-1]) + f" or {words[-1]}"


class GitCallError(RuntimeError):
    """A git call that failed where the caller cannot go on without its answer."""


class ItemNumberError(ValueError):
    """A 1-based item number that names no item."""

    def __init__(self, number, item_count):
        super().__init__(f"{number} names no item: there are {item_count}")
        self.number = number
        self.item_count = item_count


def numbered_items(numbers, items):
    """The items the 1-based `numbers` name, in the order of `numbers`. A number that names none raises
    ItemNumberError."""
    for number in numbers:
        if not 1 <= number <= len(items):
            raise ItemNumberError(number, len(items))
    return [items[number - 1] for number in numbers]


def drop_numbered(items, dropped_numbers, kept_numbers):
    """(`items` without the ones at the 1-based `dropped_numbers`, `kept_numbers` renumbered to follow the drop).
    A kept number that names a dropped item is removed from the result."""
    dropped = set(dropped_numbers)
    kept_items = [item for number, item in enumerate(items, 1) if number not in dropped]
    new_number = {}
    for number in range(1, len(items) + 1):
        if number not in dropped:
            new_number[number] = len(new_number) + 1
    return kept_items, [new_number[number] for number in kept_numbers if number in new_number]


def wait_for(check, timeout_seconds, interval_seconds):
    """Call check() until it returns a truthy value, then return that value. Check once, then every
    interval_seconds, for at most timeout_seconds. Return None when nothing was found in that time."""
    deadline = time.monotonic() + timeout_seconds
    while True:
        found = check()
        if found:
            return found
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        time.sleep(min(interval_seconds, remaining))


# What run_process returns; it unpacks as (exit code, stdout, stderr). collections.namedtuple, not typing.NamedTuple:
# hooks import this module, and typing adds to every hook's start-up.
ProcessResult = namedtuple("ProcessResult", ["code", "stdout", "stderr"])


def run_process(command, cwd, stdin=None, timeout=None, env=None, on_start=None):
    """Run a command (a list, or a string for the shell) in cwd and return (exit code, stdout, stderr), both as text.
    A byte that is not UTF-8 decodes as U+FFFD. `env`, when given, is the command's whole environment. When the
    command does not finish in `timeout` seconds, kill its whole process group, so a shell command that started a
    server cannot keep the pipes open, and return (None, stdout, stderr) with what it printed. `on_start`, when
    given, is called with the process pid once it runs, so a caller can track the process group it leads."""
    stdin_pipe = subprocess.PIPE if stdin is not None else None
    process = subprocess.Popen(command, cwd=cwd, env=env, stdin=stdin_pipe,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                               errors="replace", shell=isinstance(command, str), start_new_session=True)
    if on_start:
        on_start(process.pid)
    try:
        stdout, stderr = process.communicate(stdin, timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
        return ProcessResult(None, stdout, stderr)
    return ProcessResult(process.returncode, stdout, stderr)


def git_output(cwd, *args, timeout=None):
    """Standard output of `git <args>` run in cwd, without its trailing newlines, or None when git fails, is missing or
    takes longer than `timeout` seconds. A warning on stderr never becomes part of the answer. Paths come back as
    they are: quoting is off, and bytes that are not UTF-8 decode as os.fsdecode does, so os.fsencode gives them
    back."""
    try:
        finished = subprocess.run(["git", "-c", "core.quotepath=false", *args], cwd=cwd, stdin=subprocess.DEVNULL,
                                  capture_output=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None
    if finished.returncode != 0:
        return None
    return os.fsdecode(finished.stdout).rstrip("\n")


# What main_checkout_dir returns: the folder, and whether it is a bare common dir rather than a checkout folder.
MainCheckout = namedtuple("MainCheckout", ["folder", "is_bare"])


def main_checkout_dir(repo):
    """The MainCheckout of the repo that holds `repo` (that of a linked worktree too): the parent of the git common
    dir when it is named `.git`, else the common dir itself with is_bare set (a bare repo; a submodule's common dir
    under `.git/modules/` reads the same way, so its folder is not a checkout). None when git cannot answer."""
    common_dir = git_output(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if not common_dir:
        return None

    common_path = pathlib.Path(common_dir)
    if common_path.name == ".git":
        return MainCheckout(common_path.parent, False)
    return MainCheckout(common_path, True)


def first_nonempty_line(text_file):
    """The first line of the file that holds text, stripped, or "" when it holds none."""
    for line in text_file.read_text(errors="replace").splitlines():
        if line.strip():
            return line.strip()
    return ""


def work_tree_blob(repo, path, keep_object=False):
    """The blob id of the work-tree content of `path` in `repo`, or None when the file is absent or git cannot hash
    it. With `keep_object`, git also stores the content, so `restore_blob` can write it back later."""
    if not (pathlib.Path(repo) / path).is_file():
        return None
    write_flag = ["-w"] if keep_object else []
    return git_output(repo, "hash-object", *write_flag, "--", path)


def restore_blob(repo, path, blob):
    """Puts the work-tree file `path` back to the content of `blob` (a blob id git holds), or deletes it when `blob`
    is None. Returns True when the file now matches; False when git cannot read the blob or the file cannot be
    written, with the file left as it was."""
    target = pathlib.Path(repo) / path
    if blob is None:
        try:
            target.unlink(missing_ok=True)
        except OSError:
            return False
        return True
    try:
        # --filters applies the smudge and eol conversion of `path`, so a CRLF file comes back CRLF.
        finished = subprocess.run(["git", "cat-file", "--filters", f"--path={path}", blob], cwd=repo,
                                  stdin=subprocess.DEVNULL, capture_output=True)
    except OSError:
        return False
    if finished.returncode != 0:
        return False
    try:
        write_text_atomically(target, finished.stdout)
    except OSError:
        return False
    return True


# What the index of a repo holds for one path: the file mode and the blob id. A namedtuple for the reason above.
IndexEntry = namedtuple("IndexEntry", ["mode", "blob"])


def index_entries(repo, paths):
    """The index entry of each of `paths` in `repo`, read with one git call: a dict of path to the IndexEntry, or to
    None when the path is not in the index (an untracked file). Raises GitCallError when git fails, so a failed
    listing never reads as "not in the index"."""
    entries = dict.fromkeys(paths)
    if not entries:
        return entries
    listing = git_output(repo, "--literal-pathspecs", "ls-files", "--stage", "-z", "--", *entries)
    if listing is None:
        raise GitCallError(f"`git ls-files --stage` failed in {repo}")
    if not listing:
        return entries
    # One entry reads `<mode> <blob> <stage>\t<path>`; a path with a merge conflict lists several stages, and the
    # first is enough to tell the entry changed.
    for record in listing.split("\0"):
        description, _tab, listed_path = record.partition("\t")
        if listed_path not in entries or entries[listed_path] is not None:
            continue
        mode, blob, _stage = description.split(" ")
        entries[listed_path] = IndexEntry(mode, blob)
    return entries


def index_entry(repo, path):
    """The IndexEntry the index of `repo` holds for `path`, or None when the path is not in the index (an untracked
    file). Raises GitCallError when git fails."""
    return index_entries(repo, [path])[path]


def restore_index_entry(repo, path, entry):
    """Puts the index entry of `path` back to `entry` (an IndexEntry from `index_entry`), or takes the path out of the
    index when `entry` is None. Leaves the work tree alone. Returns True when the index now holds `entry`."""
    if entry is None:
        return git_output(repo, "--literal-pathspecs", "rm", "--cached", "-q", "--ignore-unmatch", "--",
                          path) is not None
    cache_info = f"{entry.mode},{entry.blob},{path}"
    return git_output(repo, "update-index", "--add", "--cacheinfo", cache_info) is not None


def restore_index_entries(repo, entries_before):
    """Puts the index entry of each path of `entries_before` (a dict of path to IndexEntry, or None for a path that was
    not in the index) back to what it was, when it differs now. Returns the set of paths whose entry could not be read
    or restored; a failed index read names every path."""
    try:
        entries_now = index_entries(repo, list(entries_before))
    except GitCallError:
        return set(entries_before)
    failed = set()
    for path, entry in entries_before.items():
        if entries_now[path] == entry:
            continue
        if not restore_index_entry(repo, path, entry):
            failed.add(path)
    return failed


def blob_at_commit(repo, commit, path):
    """The blob id of `path` in `commit` of `repo`, or None when the commit has no such file or git cannot say."""
    return git_output(repo, "rev-parse", "--verify", "-q", f"{commit}:{path}")


def matches_head(repo, path):
    """Whether `path` has no diff against HEAD in `repo`: a file HEAD tracks with the same content, or a file that is
    absent and that HEAD does not track. A deleted tracked file and a new file are diffs, so is a present file in a
    repo with no commit; an absent file there is no diff."""
    head_blob = blob_at_commit(repo, "HEAD", path)
    return not content_changed_since(repo, path, head_blob)


def content_changed_since(repo, path, blob):
    """Whether the work-tree content of `path` differs from `blob` (a blob id; None means the file was absent), so a
    committed edit still counts and a revert to `blob`'s content does not. Fails closed: when git cannot hash an
    existing file, it counts as changed."""
    if not (pathlib.Path(repo) / path).is_file():
        return blob is not None
    current = work_tree_blob(repo, path)
    return current is None or current != blob


def process_stderr_text(finished):
    """What a finished subprocess wrote to stderr, as text for a failure message."""
    return os.fsdecode(finished.stderr).strip()


def repo_relative(repo, given):
    """`given` (absolute, or relative to the repo root) as a path relative to the repo root, or None when it lies
    outside the repo. `repo` must be a resolved path."""
    try:
        return (pathlib.Path(repo) / given).resolve().relative_to(repo).as_posix()
    except ValueError:
        return None


def is_ancestor(repo, older, newer, timeout=None):
    """Whether commit `older` is `newer` or one of its ancestors; False when git fails."""
    return git_output(repo, "merge-base", "--is-ancestor", older, newer, timeout=timeout) is not None


def head_commit(cwd, timeout=None):
    """The commit HEAD names in cwd, or None in a repo with no commit or when git fails."""
    return git_output(cwd, "rev-parse", "--verify", "-q", "HEAD", timeout=timeout)


def head_commit_or_unborn(repo):
    """The commit HEAD names in `repo`, or None for an unborn HEAD (a repo with no commit). Raises GitCallError when
    HEAD cannot be named in a repo that has a commit."""
    head = head_commit(repo)
    if head is not None:
        return head
    branch_ref = git_output(repo, "symbolic-ref", "-q", "HEAD")
    if branch_ref is None:
        raise GitCallError(f"git could not name HEAD in {repo}")
    branch_commit = git_output(repo, "for-each-ref", "--format=%(objectname)", branch_ref)
    if branch_commit != "":
        raise GitCallError(f"git could not name HEAD in {repo}")
    return None


def head_commit_time(top):
    """The HEAD commit's committer time in seconds, or None when git cannot tell (no commit yet)."""
    stamp = git_output(top, "log", "-1", "--format=%ct")
    if not stamp:
        return None
    return float(stamp)


def commits_since(repo, commit):
    """The "<short hash> <subject>" of each commit HEAD gained since `commit`, oldest first. `commit` None means the
    repo had no commit: every commit of HEAD counts. Returns None when git cannot say, so a caller tells that apart
    from no commits ([])."""
    rev_range = f"{commit}..HEAD"
    if commit is None:
        try:
            head = head_commit_or_unborn(repo)
        except GitCallError:
            return None
        if head is None:
            return []
        rev_range = "HEAD"
    listing = git_output(repo, "log", "--reverse", "--format=%h %s", rev_range)
    if listing is None:
        return None
    return listing.splitlines()


def untracked_paths(directory):
    """Sorted untracked paths that .gitignore does not hide, relative to directory, or None when git fails."""
    listing = git_output(directory, "ls-files", "--others", "--exclude-standard", "-z")
    if listing is None:
        return None
    return sorted(name for name in listing.split("\0") if name)


def repo_file_paths(directory):
    """Sorted paths of the tracked files and the untracked files .gitignore does not hide, relative to directory, or
    None when git fails. A tracked file deleted in the work tree is still listed."""
    listing = git_output(directory, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
    if listing is None:
        return None
    return sorted({name for name in listing.split("\0") if name})


def repo_file_paths_or_raise(directory):
    """The paths `repo_file_paths` lists. Raises GitCallError when git fails."""
    paths = repo_file_paths(directory)
    if paths is None:
        raise GitCallError(f"`git ls-files --cached --others --exclude-standard` failed in {directory}")
    return paths


def read_text_lines(path):
    """The file's lines as (line number, text) pairs from 1, or None when it is not UTF-8 text (it holds a NUL or
    bytes that do not decode) or cannot be read. A failed read is returned as None, not raised: the caller treats it
    like binary content."""
    try:
        raw = pathlib.Path(path).read_bytes()
    except OSError:
        return None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if "\0" in text:
        return None
    lines = text.split("\n")
    if lines[-1] == "":
        lines.pop()
    return list(enumerate(lines, start=1))


def changed_files(directory, base="HEAD", with_deleted=False):
    """Sorted paths git shows changed against base, relative to directory: tracked changes (deletions excluded unless
    `with_deleted`) plus untracked files that .gitignore does not hide."""
    diff_args = ["diff", "--name-only", "--relative"]
    if not with_deleted:
        diff_args.append("--diff-filter=d")
    tracked_files = git_output(directory, *diff_args, base) or ""
    untracked = untracked_paths(directory) or []
    names = [name for name in tracked_files.split("\n") if name]
    return sorted(set(names + untracked))


def git_path(cwd, name):
    """The absolute path git keeps `name` at for the repo of cwd (inside its git dir), or None when git cannot say."""
    found = git_output(cwd, "rev-parse", "--path-format=absolute", "--git-path", name)
    if found is None:
        return None
    return pathlib.Path(found)


def path_is_under(path, prefix):
    # True when path is prefix itself or lies below it, compared as text so "ab" is not under "a".
    return path == prefix or path.startswith(prefix.rstrip("/") + "/")


def resolved_parent_path(path):
    # The absolute path with the folders resolved and the last name kept, so a symlink target names the link.
    absolute = os.path.normpath(os.path.abspath(path))
    parent = os.path.realpath(os.path.dirname(absolute))
    return os.path.join(parent, os.path.basename(absolute))


def details_with_outcome(outcomes, outcome):
    # {key: detail} for each entry of an {key: {"outcome": ..., "detail": ...}} map that has this outcome, in map order.
    return {key: entry["detail"] for key, entry in outcomes.items() if entry["outcome"] == outcome}


CommandResult = namedtuple("CommandResult", "code output timed_out")


def run_command_result(command, cwd=None, stdin=None, timeout=None, env=None):
    """Run a command as run_process does and return a CommandResult: the exit code, stdout and stderr joined and
    stripped, and whether the run passed `timeout`. A program that is not found exits COMMAND_NOT_FOUND_EXIT_CODE; a
    run past `timeout` seconds exits TIMEOUT_EXIT_CODE with a note after what it printed. timed_out is True only for
    that run, never for a program that exits with the same code itself. `env`, when given, is the command's whole
    environment."""
    try:
        code, stdout, stderr = run_process(command, cwd, stdin=stdin, timeout=timeout, env=env)
    except FileNotFoundError:
        program = command if isinstance(command, str) else command[0]
        return CommandResult(COMMAND_NOT_FOUND_EXIT_CODE, f"{program}: command not found", False)

    output = (stdout + stderr).strip()
    if code is None:
        timed_out_output = (output + f"\ntimed out after {timeout} seconds").strip()
        return CommandResult(TIMEOUT_EXIT_CODE, timed_out_output, True)
    return CommandResult(code, output, False)


def run_command(command, cwd=None, stdin=None, timeout=None, env=None):
    """Run a command as run_command_result does and return (exit code, output)."""
    result = run_command_result(command, cwd, stdin=stdin, timeout=timeout, env=env)
    return result.code, result.output


def run_or_raise(argv, error_type, cwd=None, check=False, stdin=None, ok_codes=(0,), timeout=None, as_bytes=False,
                env=None):
    """Run argv and return the CompletedProcess, its output decoded as UTF-8 with no newline translation (with
    as_bytes, stdin is bytes and stdout stays raw bytes). env, when given, is the child's whole environment. Raise
    error_type when argv cannot start or runs past `timeout` seconds and, with check, when its exit code is not in
    ok_codes, naming the command and its stderr, or its stdout when stderr is empty."""
    stdin_bytes = stdin if as_bytes or stdin is None else stdin.encode()
    try:
        finished = subprocess.run(argv, cwd=cwd, input=stdin_bytes, capture_output=True, timeout=timeout,
                                  env=env)
    except OSError as error:
        raise error_type(f"cannot run {argv[0]}: {error}") from error
    except subprocess.TimeoutExpired as error:
        raise error_type(f"`{' '.join(argv)}` ran past {timeout} seconds") from error

    if not as_bytes:
        finished.stdout = finished.stdout.decode("utf-8", "replace")
    finished.stderr = finished.stderr.decode("utf-8", "replace")
    if check and finished.returncode not in ok_codes:
        stdout_text = finished.stdout.decode("utf-8", "replace") if as_bytes else finished.stdout
        detail = finished.stderr.strip() or stdout_text.strip()
        raise error_type(f"`{' '.join(argv)}` failed: {detail}")
    return finished


def remote_default_branch(folder, error_type):
    """The remote's default branch as `origin/<name>`, read from origin/HEAD; None when origin/HEAD is not set.
    Raises error_type when git fails for any other reason."""
    argv = ["git", "-C", str(folder), "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"]
    finished = run_or_raise(argv, error_type, check=True, ok_codes=(0, 1))
    name = finished.stdout.strip()
    if finished.returncode != 0 or not name:
        return None
    return name


def repo_root(cwd, timeout=None):
    """The top level of the git work tree that holds cwd, or None outside one."""
    top = git_output(cwd, "rev-parse", "--show-toplevel", timeout=timeout)
    if not top:
        return None
    return pathlib.Path(top)


def work_tree_top(path, timeout=None):
    """The real path of the work tree that holds path, an existing file or a directory, as a string; None for no path
    or outside a work tree."""
    if not path:
        return None
    directory = os.path.dirname(path) if os.path.isfile(path) else path
    top = repo_root(directory, timeout=timeout)
    return os.path.realpath(top) if top else None


def current_branch(cwd, timeout=None):
    """The checked-out branch name: "" on a detached HEAD, None when git fails."""
    return git_output(cwd, "branch", "--show-current", timeout=timeout)


def remote_ref_state(repo, remote, ref):
    """(has_ref, git_error): True when the remote has the full ref, False when it answered that it has none, None with
    the git error when the lookup fails. `ls-remote --exit-code` exits 2 for an answered "no such ref"."""
    listed = subprocess.run(["git", "-C", repo, "ls-remote", "--exit-code", remote, ref], capture_output=True,
                            stdin=subprocess.DEVNULL)
    if listed.returncode == 0:
        return True, ""
    if listed.returncode == 2:
        return False, ""
    return None, process_stderr_text(listed)


def branch_merge_ref(repo, branch):
    """The upstream ref set for the branch in git config, or None when none is set or git fails."""
    return git_output(repo, "config", "--get", f"branch.{branch}.merge")


def branch_remote(repo, branch):
    """The remote set for the branch in git config, or None when none is set or git fails."""
    return git_output(repo, "config", "--get", f"branch.{branch}.remote")


def repo_name(cwd):
    """The repository name that tools/repo-name prints (a linked worktree reports its main checkout). When the script
    fails, the name of cwd, as repo-name prints outside a repo. REPO_NAME_SCRIPT names another script."""
    script = os.environ.get("REPO_NAME_SCRIPT") or str(REPO_NAME_SCRIPT)
    try:
        finished = subprocess.run([script], cwd=cwd, capture_output=True, text=True, timeout=REPO_NAME_TIMEOUT_SECONDS)
    except (OSError, subprocess.SubprocessError):
        finished = None

    name = finished.stdout.strip() if finished is not None and finished.returncode == 0 else ""
    return name or pathlib.Path(cwd).resolve().name


def run_retrying(argv, retry_exit_codes, attempts, backoff_seconds, timeout_seconds, sleep=time.sleep, **run_kwargs):
    """Run argv with captured text output, at most `attempts` times, and return the last CompletedProcess. A run is
    tried again, after sleeping backoff_seconds times the number of runs so far, when its exit code is in
    retry_exit_codes or it does not finish in timeout_seconds. Any other exit code is returned at once. When the last
    run times out, subprocess.TimeoutExpired is raised; when it exits with a retry code, that result is returned."""
    for attempt in range(1, attempts + 1):
        is_last = attempt == attempts
        done = _run_text_or_none_on_timeout(argv, timeout_seconds, is_last, run_kwargs)
        if done is not None and (done.returncode not in retry_exit_codes or is_last):
            return done
        sleep(backoff_seconds * attempt)


def _run_text_or_none_on_timeout(argv, timeout_seconds, is_last, run_kwargs):
    """One captured text run of argv: its CompletedProcess, or None on a timeout, which is raised on the last try."""
    try:
        return subprocess.run(argv, capture_output=True, text=True, errors="replace", timeout=timeout_seconds,
                              **run_kwargs)
    except subprocess.TimeoutExpired:
        if is_last:
            raise
    return None


def attempts_within(wait_seconds, backoff_seconds):
    """The most tries of a run_retrying loop whose pauses (backoff_seconds times 1, then times 2, ...) add up to no
    more than wait_seconds. Always at least 1."""
    attempts = 1
    waited = 0
    while waited + backoff_seconds * attempts <= wait_seconds:
        waited += backoff_seconds * attempts
        attempts += 1
    return attempts


# A ledger read whose cache is behind exits 75 at once and starts a worker that catches up. Every caller waits up to
# wait_seconds of pauses between tries (LEDGER_WAIT_SECONDS by default; each try may also run up to
# LEDGER_CALL_TIMEOUT_SECONDS), then reports the read as not done; the ledger never blocks the work.
LEDGER_BUSY_EXIT = 75
LEDGER_WAIT_SECONDS = 90
LEDGER_BACKOFF_SECONDS = 3
LEDGER_CALL_TIMEOUT_SECONDS = 60
# These two exist so a test need not wait.
LEDGER_BACKOFF_ENV = "LEDGER_READ_BACKOFF_SECONDS"
LEDGER_CALL_TIMEOUT_ENV = "LEDGER_READ_CALL_TIMEOUT_SECONDS"


class LedgerUnreadError(Exception):
    """A ledger read gave no answer. Callers carry on without it and say what was not read."""


class LedgerNotInstalledError(LedgerUnreadError):
    """No `ledger` program is on PATH or in the cargo bin folder."""


class LedgerBusyError(LedgerUnreadError):
    """A ledger read found the cache still behind (exit 75) or timed out on its last try. The message names the
    command, the seconds of pauses and the ledger's own last stderr line."""


def ledger_failure_reason(done):
    """The last stderr line of a finished ledger call, or `exited <code>` when it wrote none."""
    stderr_lines = done.stderr.strip().splitlines()
    return stderr_lines[-1] if stderr_lines else f"exited {done.returncode}"


def ledger_bin():
    """The path of the `ledger` program: the first on PATH, else the one `cargo install` puts in
    ${CARGO_HOME:-~/.cargo}/bin. None when neither exists. A hook or a Bash tool call can run without the login
    shell's PATH, so the cargo folder is checked by its path. Same lookup as ledger_bin in lib/_ledger.sh."""
    on_path = shutil.which("ledger")
    if on_path:
        return on_path

    cargo_home = os.environ.get("CARGO_HOME")
    if not cargo_home:
        home = os.environ.get("HOME")
        if not home:
            return None
        cargo_home = os.path.join(home, ".cargo")
    cargo_ledger = os.path.join(cargo_home, "bin", "ledger")
    if os.path.isfile(cargo_ledger) and os.access(cargo_ledger, os.X_OK):
        return cargo_ledger
    return None


def missing_ledger_warning():
    """The line a report shows the user when telemetry is on and no ledger is found: the run's rows went to the
    fallback jsonl files, which the ledger's readers never see. None otherwise."""
    if not telemetry_switch_on() or ledger_bin():
        return None
    return ("No ledger found on PATH or in the cargo bin folder ($CARGO_HOME/bin, default ~/.cargo/bin): this run's "
            "review rows went to the jsonl files under ~/.claude, where the ledger's readers do not see them. "
            "Install the ledger or put its folder on PATH.")


def read_ledger(args, wait_seconds=LEDGER_WAIT_SECONDS):
    """Run `ledger <args>` and return its CompletedProcess for any exit but 75. Exit 75 and a call that does not
    finish in time are tried again, with pauses totalling wait_seconds (each try may also run up to
    LEDGER_CALL_TIMEOUT_SECONDS); 0 means one try. Then LedgerBusyError is raised. Raises
    LedgerNotInstalledError when ledger_bin finds no ledger."""
    ledger = ledger_bin()
    if ledger is None:
        raise LedgerNotInstalledError("ledger not installed")

    backoff = float(os.environ.get(LEDGER_BACKOFF_ENV, LEDGER_BACKOFF_SECONDS))
    timeout = float(os.environ.get(LEDGER_CALL_TIMEOUT_ENV, LEDGER_CALL_TIMEOUT_SECONDS))
    attempts = attempts_within(wait_seconds, LEDGER_BACKOFF_SECONDS)
    waited = round(backoff * attempts * (attempts - 1) / 2)
    command = " ".join(["ledger", *args])
    try:
        done = run_retrying([ledger, *args], (LEDGER_BUSY_EXIT,), attempts, backoff, timeout)
    except subprocess.TimeoutExpired:
        raise LedgerBusyError(f"{command}: no answer within {timeout:g} s per try ({waited} s of pauses)") from None
    if done.returncode != LEDGER_BUSY_EXIT:
        return done

    raise LedgerBusyError(f"{command}: {ledger_failure_reason(done)} ({waited} s of pauses)")


def last_change_ns(path):
    """Later of mtime and ctime in nanoseconds: a file moved in after another file was written keeps its old
    mtime but gets a new ctime. path is a pathlib.Path."""
    file_stat = path.stat()
    return max(file_stat.st_mtime_ns, file_stat.st_ctime_ns)


def joined_distinct(values, separator=" - "):
    """The non-empty values joined by separator, each distinct value once, in order."""
    kept = []
    for value in values:
        if value and value not in kept:
            kept.append(value)
    return separator.join(kept)


def ask_text(item):
    # The shared reader copies a finding into the question (and the reverse) when only one is given: show it once.
    return joined_distinct([str(item.get("finding") or ""), str(item.get("question") or "")])


def hanging_indent_lines(lead, text, indent="   "):
    """The lines of text (any value, printed as text), the first behind lead and each later one behind indent. No
    lines for empty text."""
    text_lines = str(text).splitlines()
    if not text_lines:
        return []
    return [lead + text_lines[0], *(indent + line for line in text_lines[1:])]


def visible_text(line, in_comment):
    """Return (line without HTML comment text, still inside an unclosed comment). A `<!--` inside an
    inline code span opens nothing."""
    text = ""
    rest = line
    while rest:
        if in_comment and "-->" not in rest:
            return text, True
        if in_comment:
            rest = rest[rest.find("-->") + 3:]
            in_comment = False
            continue
        match = INLINE_CODE_OR_COMMENT_OPEN.search(rest)
        if match is None:
            text += rest
            break
        if match.group(0) == "<!--":
            text += rest[:match.start()]
            in_comment = True
        else:
            text += rest[:match.end()]
        rest = rest[match.end():]
    return text, in_comment


def is_blocker(item):
    """True for a mapping whose `blocker` field reads true or yes."""
    return isinstance(item, dict) and str(item.get("blocker", "")).strip().lower() in ("true", "yes")


def one_line(text, limit=200):
    """The text on one line: runs of whitespace collapse to a space, cut at `limit` characters."""
    return re.sub(r"\s+", " ", str(text)).strip()[:limit]


def write_command_outputs(output_file, command_outputs):
    """Write each (command, outcome, output) to the file as `$ <command>`, the outcome line and the whole output, one
    section per command, making the file's folder."""
    sections = [f"$ {command}\n{outcome}\n{output}" for command, outcome, output in command_outputs]
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text("\n\n".join(sections))


# What stands before and after a repo-relative path that a finding or note holds as a whole token: no longer path
# around it (`pkg/app.py`, `app.py/x`, `app.pyc`), but a sentence's closing dot may follow (`edit app.py.`).
PATH_TOKEN_START = r"(?<![\w./-])"
PATH_TOKEN_END = r"(?![\w/-]|\.\w)"


def names_path(path, text, as_token=False):
    """True when `text` holds `path` as a whole path: not the start or the middle of a longer name (`/x/app-v2`).
    With `as_token`, the boundaries are PATH_TOKEN_START and PATH_TOKEN_END, for a repo-relative path in prose."""
    if as_token:
        return re.search(f"{PATH_TOKEN_START}{re.escape(path)}{PATH_TOKEN_END}", text) is not None
    return re.search(rf"(?<![\w.@+-]){re.escape(path)}(?![\w.@+-])", text) is not None


CURRENT_FOLDER_PREFIX = re.compile(rf"{PATH_TOKEN_START}\./")


def texts_relative_to(finding_texts, root):
    """The finding texts with each `root/` prefix and each leading `./` cut out, so a path under `root` or written
    `./lib/x.py` reads as its repo-relative path."""
    root_prefix = f"{root}/"
    return [CURRENT_FOLDER_PREFIX.sub("", text.replace(root_prefix, "")) for text in finding_texts]


def texts_name_path(finding_texts, path, root):
    """Whether one of the finding texts holds `path` as a whole token. A path under `root` counts as `path`."""
    relative_texts = texts_relative_to(finding_texts, root)
    return any(names_path(path, text, as_token=True) for text in relative_texts)


def path_has_tail(path, tail):
    """True when `path` is `tail` or ends with `/` and `tail`."""
    return path == tail or path.endswith(f"/{tail}")


def texts_name_path_by_suffix(finding_texts, path, root, known_paths):
    """Whether one of the finding texts holds a proper trailing part of `path` (`x.py` for `lib/x.py`) that has a `/` or
    a `.` in it, as a whole token, and `path` is the only one of `known_paths` that ends with that part. A part that
    two known paths end with names neither."""
    parts = path.split("/")
    for start in range(1, len(parts)):
        suffix = "/".join(parts[start:])
        if "/" not in suffix and "." not in suffix:
            continue
        if not texts_name_path(finding_texts, suffix, root):
            continue
        owners = [known for known in known_paths if path_has_tail(known, suffix)]
        if owners == [path]:
            return True
    return False


def texts_name_repo_file(finding_texts, path, root, known_paths):
    """Whether the finding texts name `path`: in full, with a `./` prefix, or by a trailing part of it that no other of
    `known_paths` ends with."""
    if texts_name_path(finding_texts, path, root):
        return True
    return texts_name_path_by_suffix(finding_texts, path, root, known_paths)


def pop_option(arguments, flag):
    """(the arguments without the first `flag` and its value, that value). The value is None when `flag` is not
    given and "" when `flag` is the last word."""
    arguments = list(arguments)
    if flag not in arguments:
        return arguments, None
    position = arguments.index(flag)
    value = arguments[position + 1] if position + 1 < len(arguments) else ""
    return arguments[:position] + arguments[position + 2:], value


def leading_env_assignments(command_lines):
    """The `NAME=value` words that the command lines start with, as written (quotes kept), one per variable name: the
    first line to set a name decides its value. Order is first seen. A line that is only an assignment, with no command
    after it, sets nothing."""
    assignments = {}
    for line in command_lines:
        leading = ENV_ASSIGNMENTS.match(str(line).lstrip())
        if leading is None:
            continue
        for assignment_match in ENV_ASSIGNMENT.finditer(leading.group(0)):
            assignments.setdefault(assignment_match.group(1), assignment_match.group(0))
    return list(assignments.values())


def without_leading_env_assignments(command):
    """The command with the NAME=value words it starts with taken off, whatever their values; the command itself when
    it starts with none."""
    stripped = command.strip()
    leading = ENV_PREFIX.match(stripped)
    return stripped[leading.end():] if leading else stripped


def first_command_word(command):
    """The first word of a command after any leading NAME=value assignments, or "" for an empty command."""
    words = without_leading_env_assignments(command).split()
    return words[0] if words else ""


def backticked_spans(line):
    """The text of each `backticked` span of a line, in order."""
    return BACKTICKED.findall(line)


def without_backticked_spans(line):
    """The line with every backticked span taken out."""
    return BACKTICKED.sub("", line)


def pre_tool_use_deny(reason):
    """Print the PreToolUse hook output that denies the tool call and shows `reason` to the model."""
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                             "permissionDecisionReason": reason}}))


def subagent_transcript_path(session_transcript, agent_id):
    """Where Claude Code keeps the transcript of a subagent of the session: `<session transcript without
    .jsonl>/subagents/agent-<id>.jsonl`."""
    return os.path.join(os.path.splitext(session_transcript)[0], "subagents", subagent_transcript_name(agent_id))


SUBAGENT_NAME_PREFIX = "agent-"
SUBAGENT_META_SUFFIX = ".meta.json"


def subagent_transcript_name(agent_id):
    """The file name Claude Code gives the transcript of the subagent `agent_id`."""
    return f"{SUBAGENT_NAME_PREFIX}{agent_id}.jsonl"


def subagent_meta_name(agent_id):
    """The file name Claude Code gives the meta file of the subagent `agent_id`. Pass "*" for a glob pattern."""
    return f"{SUBAGENT_NAME_PREFIX}{agent_id}{SUBAGENT_META_SUFFIX}"


def subagent_id_from_meta_name(file_name):
    """The agent id in the meta file name `subagent_meta_name` makes."""
    return file_name.removeprefix(SUBAGENT_NAME_PREFIX).removesuffix(SUBAGENT_META_SUFFIX)


def sibling_transcript_path(agent_transcript, agent_id):
    """Where the transcript of the subagent `agent_id` sits beside `agent_transcript`, in the same folder."""
    return os.path.join(os.path.dirname(agent_transcript), subagent_transcript_name(agent_id))


TRANSCRIPT_TAIL_BYTES = 65536


def transcript_tail_lines(transcript_path, tail_bytes):
    """The lines in the last `tail_bytes` bytes of a transcript. A first line cut by the seek is dropped. Raises
    OSError when the file cannot be read."""
    with open(transcript_path, "rb") as transcript:
        size = transcript.seek(0, os.SEEK_END)
        transcript.seek(max(0, size - tail_bytes))
        tail_lines = transcript.read().decode("utf-8", errors="replace").split("\n")
    if size > tail_bytes:
        tail_lines = tail_lines[1:]  # the first line is cut
    return tail_lines


def _last_nonblank_line(lines):
    """The last line with text in it, or "" when there is none."""
    last_line = ""
    for line in lines:
        if line.strip():
            last_line = line
    return last_line


def read_json_object(file, report_torn=False):
    """The JSON object in `file` (a str or a Path), or {} when it is missing, unreadable, torn (a writer part-way
    through) or holds no object. A torn file is named on stderr only when `report_torn` is set, so a hook that reads
    state files stays quiet."""
    file = pathlib.Path(file)
    try:
        found = json.loads(file.read_text(encoding="utf-8"))
    except OSError:
        return {}
    except ValueError as error:
        if report_torn:
            print(f"read_json_object: {file} is not valid JSON, {type(error).__name__}: {error}", file=sys.stderr)
        return {}
    return found if isinstance(found, dict) else {}


def _transcript_tail(transcript_path, caller, unreadable=None):
    """The tail lines of a transcript, or None when it is missing, or `unreadable` when the read failed (that case
    prints a `could not read` line naming `caller` on stderr)."""
    try:
        return transcript_tail_lines(transcript_path, TRANSCRIPT_TAIL_BYTES)
    except FileNotFoundError:
        return None
    except OSError as error:
        print(f"{caller}: could not read {transcript_path}, {type(error).__name__}: {error}", file=sys.stderr)
        return unreadable


def last_transcript_record(transcript_path):
    """The last record of a transcript as a dict. None for a transcript that is missing, unreadable, empty, whose
    last line is torn (an agent part-way through an append) or whose last record is not an object."""
    tail_lines = _transcript_tail(transcript_path, "last_transcript_record")
    # A failed read counts as alive (None): the open-work gates keep waiting, and the dead-reviewer gate passes.
    if tail_lines is None:
        return None
    try:
        record = json.loads(_last_nonblank_line(tail_lines))
    except ValueError:
        return None
    return record if isinstance(record, dict) else None


def last_api_error(transcript_path, report_unreadable=False):
    """The transcript's last user or assistant record when it is an API error message, else None. Records of any
    other type (turn durations, informational notes, last-prompt, cost state) that Claude Code writes after the
    error are skipped. None also for a transcript that is missing, empty, or whose last line is torn, and for an
    unreadable one unless `report_unreadable` is set: then it returns TRANSCRIPT_UNREADABLE."""
    unreadable = TRANSCRIPT_UNREADABLE if report_unreadable else None
    tail_lines = _transcript_tail(transcript_path, "last_api_error", unreadable)
    if tail_lines is None or tail_lines == TRANSCRIPT_UNREADABLE:
        return tail_lines
    last_line = _last_nonblank_line(tail_lines)
    if transcript_record(last_line) is None:
        return None
    for line in reversed(tail_lines):
        record = transcript_record(line)
        if record is None or record.get("type") not in CONVERSATION_RECORD_TYPES:
            continue
        return record if record.get("isApiErrorMessage") is True else None
    return None


def ends_on_api_error(transcript_path):
    """True when the last user or assistant record of a transcript is an API error message: the agent may never
    report. False for a transcript that is missing, unreadable, empty, or whose last such record is anything else,
    so a later record shows the agent went on."""
    return last_api_error(transcript_path) is not None


def epoch_of_timestamp(timestamp):
    """Epoch seconds of an ISO 8601 timestamp such as `2026-11-15T06:22:12.305Z`; a timestamp with no zone reads as
    UTC. Raises ValueError for any other."""
    # Python 3.10's fromisoformat does not read a trailing Z.
    moment = datetime.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=datetime.timezone.utc)
    return moment.timestamp()


def without_paths(files, paths):
    """`files` (a {path: entry} mapping or a list of paths) with the paths in `paths` left out, in the same shape."""
    left_out = set(paths)
    if isinstance(files, dict):
        return {path: entry for path, entry in files.items() if path not in left_out}
    return [path for path in files if path not in left_out]


def transcript_record(line):
    """The JSON object of one transcript line, None for a torn line or any other shape."""
    try:
        record = json.loads(line)
    except ValueError:
        return None
    if not isinstance(record, dict):
        return None
    return record


def tool_use_calls(line):
    """The (tool name, input dict) of each tool call one transcript line makes, in order; empty when the line is
    not JSON or makes none."""
    if '"tool_use"' not in line:
        return []
    return record_tool_calls(transcript_record(line))


def makes_own_calls(record):
    """Whether a parsed transcript record's tool calls are its own. Only user and assistant records are: an
    api-request-blob record repeats earlier calls, so counting it counts each call twice."""
    return record.get("type") in CONVERSATION_RECORD_TYPES


def record_tool_calls(record):
    """The (tool name, input dict) of each tool call a parsed transcript record makes, in order; empty when the
    record is None or makes none."""
    message = record.get("message") if record else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, list):
        return []

    calls = []
    for block in content:
        if not isinstance(block, dict) or block.get("type") != "tool_use":
            continue
        tool_input = block.get("input")
        calls.append((block.get("name"), tool_input if isinstance(tool_input, dict) else {}))
    return calls


def bash_commands(transcript_path):
    """Every Bash command in a transcript, oldest first. A torn byte reads as a replacement character."""
    commands = []
    with open(transcript_path, encoding="utf-8", errors="replace") as transcript:
        for line in transcript:
            calls = tool_use_calls(line)
            commands += [tool_input.get("command") for name, tool_input in calls
                         if name == "Bash" and isinstance(tool_input.get("command"), str)]
    return commands


def agent_transcript_path(hook):
    """The calling subagent's transcript: the path the hook event names, else the one under the session transcript."""
    named = hook.get("agent_transcript_path")
    if named:
        return named
    return subagent_transcript_path(hook["transcript_path"], hook["agent_id"])


def _frontmatter_key_line(text, key):
    """(1-based file line, text after `key:`) of the first `key:` line in the file's frontmatter; None when there is
    no frontmatter or no such key. CRLF line ends read as LF: FRONTMATTER matches `\n` only."""
    unix_text = text.replace("\r\n", "\n")
    frontmatter = FRONTMATTER.match(unix_text)
    if frontmatter is None:
        return None
    key_line = re.compile(rf"^{re.escape(key)}:\s*(.*)$")
    for index, line in enumerate(frontmatter.group(1).splitlines()):
        match = key_line.match(line)
        if match:
            return index + 2, match.group(1)
    return None


def frontmatter_value(text, key):
    """The text after `key:` on the first such line of the file's frontmatter; None when there is no frontmatter or no
    such key."""
    found = _frontmatter_key_line(text, key)
    if found is None:
        return None
    return found[1]


def frontmatter_line_number(text, key):
    """1-based file line of the first `key:` line in the file's frontmatter; 1 when there is no frontmatter or no such
    key."""
    found = _frontmatter_key_line(text, key)
    if found is None:
        return 1
    return found[0]


def frontmatter_skills(agent_text):
    """The skill names in an agent file's `skills:` frontmatter key: a block list of `- name` lines. An inline
    value after `skills:` raises ValueError."""
    frontmatter = FRONTMATTER.match(agent_text)
    if not frontmatter:
        return []

    lines = frontmatter.group(1).splitlines()
    for index, line in enumerate(lines):
        if not line.startswith("skills:"):
            continue
        inline_value = line[len("skills:"):].strip()
        if inline_value:
            raise ValueError(f"`skills:` frontmatter has the inline value {inline_value!r}; expected a block list "
                             "of `  - name` lines")
        return _block_list_items(lines[index + 1:])
    return []


def _block_list_items(lines):
    """The names of the leading `- name` lines, up to the first line that is not one."""
    names = []
    for item_line in lines:
        item = FRONTMATTER_LIST_ITEM.match(item_line)
        if not item:
            break
        names.append(item.group(1).strip("'\""))
    return names


def preloaded_skills_prompt(agent, claude_home=None):
    """The skills `agent`'s `skills:` frontmatter preloads, as the Agent tool hands them to the agent: each SKILL.md
    body without its frontmatter, under a `Base directory for this skill:` line. `claude -p --agent` loads none of
    them, so a script that starts an agent that way appends this to its system prompt. Empty when the agent preloads
    nothing or has no agent file. `claude_home` defaults to the toolkit folder this file sits in. A named skill with
    no SKILL.md raises FileNotFoundError."""
    claude_home = claude_home or pathlib.Path(__file__).resolve().parents[2]
    agent_file = claude_home / "agents" / f"{agent}.md"
    if not agent_file.is_file():
        return ""

    agent_text = agent_file.read_text()
    try:
        skill_names = frontmatter_skills(agent_text)
    except ValueError as error:
        raise ValueError(f"{agent_file}: {error}") from error

    skill_texts = []
    for name in skill_names:
        skill_dir = claude_home / "skills" / name
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.is_file():
            raise FileNotFoundError(f"{agent_file} preloads skill {name!r}, but {skill_file} does not exist")
        skill_text = skill_file.read_text()
        skill_body = FRONTMATTER.sub("", skill_text, count=1).strip()
        skill_texts.append(f"Base directory for this skill: {skill_dir}\n\n{skill_body}")
    return "\n\n".join(skill_texts)


def telemetry_switch_on():
    """The toolkit metrics switch from telemetry/telemetry_enabled.py. A missing helper counts as off."""
    try:
        from telemetry_enabled import telemetry_enabled
    except ImportError:
        return False
    return telemetry_enabled()


def sortable_unique_id(now=None):
    """An id that sorts by creation time and does not repeat: local time to the second, a dash, six random hex
    digits. `now` is epoch seconds (default: the current time)."""
    epoch_seconds = now if now is not None else time.time()
    local_time = time.localtime(epoch_seconds)
    stamp = time.strftime("%Y%m%dT%H%M%S", local_time)
    return stamp + "-" + uuid.uuid4().hex[:6]


def first_number(text):
    """The first run of digits in the text as an int, or None."""
    found = re.search(r"\d+", text or "")
    return int(found.group()) if found else None


def normalize_path(text):
    """The first path in a free-text location: backticks, quotes and a leading ./ gone, the line suffix cut."""
    cleaned = str(text).strip().strip("`'\"").strip()
    cleaned = re.split(r"[\s,;|]", cleaned, maxsplit=1)[0]
    cleaned = cleaned.partition(":")[0]
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    return cleaned.strip("`'\"")


def split_location(text):
    """(path, line) of the first path in a free-text location such as `a.ts:12-20, b.ts:3`; line is 0 when none."""
    cleaned = str(text).strip().strip("`'\"").strip()
    path = normalize_path(cleaned)
    first = re.split(r"[\s,;|]", cleaned, maxsplit=1)[0]
    _, separator, rest = first.partition(":")
    found = re.match(r"\d+", rest) if separator else None
    return path, int(found.group()) if found else 0


def locations_named(text):
    """Every (path, line) of the `path:line` tokens inside the text, in order."""
    return [split_location(hit) for hit in PATH_LINE.findall(text)]


# A backtick span that holds only a path or a location is a pointer, not a quotation.
# The pointer's line part also takes an approximate line (`~497`) and a list with spaces (`12-14, 16`).
LOOSE_LINE_PART = line_suffix("~?", r"\s*")
LOCATION_ALONE = re.compile(rf"{PATH_TEXT}(?:{LOOSE_LINE_PART})?")
# A `~/x.py:3` is home-relative; matching from its `/` would name a wrong absolute path.
UNHOMED_PATH_LINE = re.compile(rf"(?<![~{PATH_CHARS}/])" + PATH_LINE.pattern)
# A path with a directory part and an extension, not followed by an exact line number, more path, or a call paren: a
# dotted symbol that is called (`lib/file_lock.acquire()`) is no path.
BARE_PATH = re.compile(
    rf"(?<![{PATH_CHARS}/:\[\]~])(/?(?:[{PATH_CHARS}]+/)+[{PATH_CHARS}]+\.\w+)"
    r"(?!\w|\.\w|:\d|/|\()"
)
# A path written with a leading `./`, with or without an extension (`./Makefile`, `./install/deps`): the one way to
# name a root or extensionless file. A `../x` is no match.
DOT_SLASH_PATH = re.compile(rf"(?<![{PATH_CHARS}/~])\./[{PATH_CHARS}]+(?:/[{PATH_CHARS}]+)*")
# BARE_PATH's `:\d` lookahead leaves only the `:~` form of an approximate line to reach this pattern.
APPROXIMATE_LINE_PART = re.compile(LOOSE_LINE_PART)
TextLocation = namedtuple("TextLocation", "path line end bare")


def _is_pointer(span_text):
    """Whether a quoted span is a backtick span that holds only a path or a location."""
    return span_text.startswith("`") and bool(LOCATION_ALONE.fullmatch(span_text[1:-1]))


def _quoting_spans(text):
    """(start, end) of each span of the text that quotes other text."""
    spans = []
    for span in FINDING_QUOTED_SPAN.finditer(text):
        if not _is_pointer(span.group()):
            spans.append((span.start(), span.end()))
    return spans


def _inside_a_span(position, spans):
    return any(span_start <= position < span_end for span_start, span_end in spans)


def first_unquoted_match(pattern, text, start=0):
    """The first match of the compiled pattern in the text, from index `start`, that does not begin inside a quoted
    span, or None."""
    quoting = _quoting_spans(text)
    for hit in pattern.finditer(text, start):
        if not _inside_a_span(hit.start(), quoting):
            return hit
    return None


def _first_pointer(text):
    """The first backtick pointer with a line part (`a.py:~40`) outside any quoted span, or None."""
    # The spans do not overlap, so a pointer never sits inside another span.
    for span in FINDING_QUOTED_SPAN.finditer(text):
        if _is_pointer(span.group()) and ":" in span.group():
            return span
    return None


def first_location(text):
    """The first location a free-text finding names, as a TextLocation (end is where its text stops; bare is True
    for a path with no line part), or None.
    A `path:line` or path inside a quoted span is not a location, except a backtick span that holds only a path
    or a location. A backticked approximate line (`a.py:~40`), or an unbackticked one on a path with a directory
    part, gives its path with line 0 and bare False.
    A home-relative `~/…:N` is never a location. A bare path with a directory part and an extension that comes
    before any `path:line` is the location with line 0, unless the first `path:line` after it names the same
    file."""
    with_line = first_unquoted_match(UNHOMED_PATH_LINE, text)
    pointer = _first_pointer(text)
    if pointer and (not with_line or pointer.start() < with_line.start()):
        with_line = pointer
    bare = first_unquoted_match(BARE_PATH, text)
    with_line_location = None
    if with_line:
        path, line = split_location(with_line.group())
        with_line_location = TextLocation(path, line, with_line.end(), False)
    if not bare:
        return with_line_location

    bare_path = normalize_path(bare.group(1))
    if with_line_location and (with_line.start() < bare.start() or with_line_location.path == bare_path):
        return with_line_location
    # An unquoted approximate line (`a.py:~7`) is a line part, so the path is not bare.
    approximate = APPROXIMATE_LINE_PART.match(text, bare.end())
    if approximate:
        return TextLocation(bare_path, 0, approximate.end(), False)
    return TextLocation(bare_path, 0, bare.end(), True)


def paths_named(*texts):
    """Every normalized path that the texts name, each once, in order: a text that starts with a file name, then
    every `path:line` token inside it."""
    candidates = []
    for text in texts:
        text_as_string = str(text or "")
        candidates.extend(_path_candidates(text_as_string))
    paths = []
    for path in candidates:
        if path and path not in paths:
            paths.append(path)
    return paths


def names_a_file(text):
    """True when the text holds a `path:line`, a path with a folder part and an extension, or a path written with a
    leading `./` (`./name.ext`, or `./Makefile` for a root or extensionless file), quoted or not. A bare `~/`
    path with no line number is no match."""
    # Raw text, not first_location: a path in quotes still names the file to edit.
    raw = str(text or "")
    patterns = (PATH_LINE, BARE_PATH, DOT_SLASH_PATH)
    return any(pattern.search(raw) is not None for pattern in patterns)


def _path_candidates(text):
    """The normalized paths one text names, a leading file name first, repeats kept."""
    candidates = [normalize_path(hit) for hit in PATH_LINE.findall(text)]
    first_token = re.split(r"[\s,;|]", text.strip().strip("`'\""), maxsplit=1)[0]
    if FILE_NAME.match(first_token):
        candidates.insert(0, normalize_path(first_token))
    return candidates


URL_TOKEN = re.compile(r"[A-Za-z][\w+.-]*://\S*")
FIRST_ABSOLUTE_PATH = re.compile(r"(?<![\w.~:/-])/[^\s`'\"<>|;:,()]+")
PATH_GOES_ON_AFTER_SPACE = re.compile(r" [\w.-]+/")


def first_absolute_path(text):
    """The first absolute path the text names, or None when it names none.

    A path that does not exist and goes on after a space as another path segment was cut at the space, so it names
    none: its head could lie in a different repo.
    """
    url_free_text = URL_TOKEN.sub(" ", text)
    found = FIRST_ABSOLUTE_PATH.search(url_free_text)
    if not found:
        return None

    path = found.group(0)
    cut_at_space = PATH_GOES_ON_AFTER_SPACE.match(url_free_text, found.end())
    if cut_at_space and not os.path.exists(path):
        return None
    return path


def nearest_existing_folder(path):
    """The path itself when it is a folder, else the nearest parent that exists, so a file not yet written still
    has a folder to look from. Symlinks are resolved first, so a link points the search at its target."""
    folder = os.path.realpath(path)
    if os.path.isdir(folder):
        return folder
    folder = os.path.dirname(folder)
    while not os.path.isdir(folder):
        parent = os.path.dirname(folder)
        if parent == folder:
            break
        folder = parent
    return folder


def inside_git_work_tree(path, timeout_seconds=2):
    """True when path (a file or folder, which may not exist yet) lies inside a git work tree, False when it does
    not. A symlink is followed to its target. The inside of a .git folder and a bare repo are not a work tree.
    Asks `git rev-parse --is-inside-work-tree` from the nearest existing folder. When git cannot run, does not
    answer in time or exits with an error, looks for a .git entry in that folder or a parent instead."""
    folder = nearest_existing_folder(path)
    answer = git_output(folder, "rev-parse", "--is-inside-work-tree", timeout=timeout_seconds)
    if answer is None:
        return _has_git_entry_above(folder)
    return answer.strip() == "true"


def is_git_ignored(path, timeout_seconds=2):
    """True only when git reports path (a file that may not exist yet) as ignored. A tracked file is never ignored,
    whatever a .gitignore pattern says. A path outside a repo, a git that cannot run, times out or errors all give
    False."""
    real_path = os.path.realpath(path)
    folder = nearest_existing_folder(real_path)
    answer = git_output(folder, "check-ignore", "-q", "--", real_path, timeout=timeout_seconds)
    return answer is not None


def _is_bare_repo(folder):
    return (os.path.isfile(os.path.join(folder, "HEAD")) and os.path.isdir(os.path.join(folder, "objects"))
            and os.path.isdir(os.path.join(folder, "refs")))


def _has_git_entry_above(folder):
    if ".git" in pathlib.PurePath(folder).parts:
        return False
    while True:
        if os.path.exists(os.path.join(folder, ".git")):
            return True
        if _is_bare_repo(folder):
            return False
        parent = os.path.dirname(folder)
        if parent == folder:
            return False
        folder = parent


def write_text_atomically(path, content):
    """Write `content` (text, or bytes for a binary-exact write) to `path` so a reader sees the old file or the new
    one, never a half-written file."""
    path = pathlib.Path(path)
    mode = "wb" if isinstance(content, bytes) else "w"
    temp_path = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")

    # A new file gets 0o666 less the umask, as write_text gives. The kernel applies the umask here, so it is never read.
    descriptor = os.open(temp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
    try:
        with os.fdopen(descriptor, mode) as temp_file:
            temp_file.write(content)
        if path.exists():
            os.chmod(temp_path, stat.S_IMODE(path.stat().st_mode))
        os.replace(temp_path, path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def append_jsonl(path, row):
    """Append one JSON row as one write, so concurrent appenders cannot interleave inside a row."""
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = (json.dumps(row) + "\n").encode("utf-8")
    descriptor = os.open(str(path), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(descriptor, line)
    finally:
        os.close(descriptor)


def largest_entries(totals, limit, size):
    """The `limit` (key, total) pairs of the dict `totals` whose `size(total)` is largest; ties sort by key."""
    return sorted(totals.items(), key=lambda pair: (-size(pair[1]), pair[0]))[:limit]


def can_append(path):
    """True when a row can be appended to the file `path` (a file not made yet needs a writable folder)."""
    path = pathlib.Path(path)
    if path.exists():
        return os.access(path, os.W_OK)
    return os.access(path.parent, os.W_OK)


def xdg_state_home():
    """`$XDG_STATE_HOME` as a path, or `~/.local/state` when it is unset, empty or relative."""
    state_home = os.environ.get("XDG_STATE_HOME")
    if not state_home or not os.path.isabs(state_home):
        return pathlib.Path.home() / ".local" / "state"
    return pathlib.Path(state_home)


def state_file_path(state_dir, name, suffix):
    """`name` plus `suffix` in `state_dir`, with every character outside letters, digits, dot, dash and underscore in
    `name` replaced by an underscore, so an id from a hook event or a branch name is one safe file name."""
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", str(name))
    return pathlib.Path(state_dir) / (safe + suffix)


def session_state_path(state_dir, session):
    """The JSON file of `session` in `state_dir`."""
    return state_file_path(state_dir, session, ".json")


def write_session_state(state_dir, session, data):
    """Write `data` as JSON to the file of `session` in `state_dir`, replacing it. No session id, no write."""
    if not session:
        return

    state_file = session_state_path(state_dir, session)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomically(state_file, json.dumps(data, indent=1))


def read_session_state(state_dir, session, error_prefix):
    """The JSON object of the session's file in `state_dir`. None for no session id or no file.
    Fail-open: a file that cannot be read as an object is reported on stderr as `<error_prefix> <file>: <error>`
    and reads as no file."""
    if not session:
        return None

    state_file = session_state_path(state_dir, session)
    try:
        data = json.loads(state_file.read_text())
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as error:
        print(f"{error_prefix} {state_file}: {error}", file=sys.stderr)
        return None

    if not isinstance(data, dict):
        print(f"{error_prefix} {state_file}: not a JSON object", file=sys.stderr)
        return None
    return data


def read_jsonl(path):
    """The rows of a JSON-lines file; a missing file is no rows and a torn or non-object line is skipped."""
    path = pathlib.Path(path)
    if not path.exists():
        return []
    object_rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            object_rows.append(row)
    return object_rows


def nearest_file_upward(start_directory, file_name, stop_directory):
    """The nearest file called file_name in start_directory or a parent of it, looking no higher than stop_directory,
    or None. A start_directory that is not inside stop_directory finds nothing, `..` segments included. Both are
    pathlib.Path."""
    resolved_start = start_directory.resolve()
    if stop_directory.resolve() not in (resolved_start, *resolved_start.parents):
        return None

    directory = start_directory
    while True:
        candidate = directory / file_name
        if candidate.is_file():
            return candidate
        if directory == stop_directory or stop_directory not in directory.parents:
            return None
        directory = directory.parent


def directory_relative_to(root_directory, directory):
    """The directory's path under root_directory as text, or "" when it is root_directory itself. Both are
    pathlib.Path."""
    return str(directory.relative_to(root_directory)) if directory != root_directory else ""


def next_numbered_dir(parent):
    """The path of the next free numbered subfolder of parent (a pathlib.Path): one above the highest folder
    name there made only of ASCII decimal digits, or 1 when there is none. Creates nothing."""
    taken = [int(folder.name) for folder in parent.glob("*")
             if folder.is_dir() and folder.name.isascii() and folder.name.isdecimal()]
    return parent / str(max(taken, default=0) + 1)


def is_executable_file_inside(root_directory, relative_path):
    """True when relative_path, taken from root_directory, names an executable file inside root_directory. Inside is
    read from the path's own text, so any link inside root_directory to a target elsewhere (such as
    `.venv/bin/python` or `node_modules/.bin/<tool>`) counts. A path with any `..` segment does not, nor an absolute
    path whose text falls outside the root. root_directory is a pathlib.Path or text."""
    if ".." in pathlib.PurePath(relative_path).parts:
        return False

    given_root = pathlib.Path(os.path.abspath(root_directory))
    resolved_root = given_root.resolve()
    given = given_root / relative_path
    inside = given.is_relative_to(given_root) or given.is_relative_to(resolved_root)
    if not inside:
        return False

    return given.is_file() and os.access(given, os.X_OK)


def items_missing_by_key(items, others, key):
    """The items whose `key` no item of `others` has."""
    other_keys = {key(other) for other in others}
    return {item for item in items if key(item) not in other_keys}
