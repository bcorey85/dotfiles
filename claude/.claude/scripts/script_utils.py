"""script_utils.py: helpers for toolkit scripts that read plain text, lines, paths and files and need no module rule.

Installed as ~/.claude/scripts/script_utils.py. Scripts under ~/.claude/ import it from there by adding that
directory to sys.path."""
import difflib
import json
import os
import pathlib
import re
import subprocess
import time
import uuid

FENCE_OPEN = re.compile(r"^\s*(`{3,}|~{3,})")
CHECKBOX = re.compile(r"\[[xX]\]")
INLINE_CODE_OR_COMMENT_OPEN = re.compile(r"`[^`]*`|<!--")
PATH_LINE = re.compile(r"`?([\w@./-]+\.\w+:\d+(?:[-,]\d+)*)`?")
FILE_NAME = re.compile(r"^[\w@./-]+\.\w+(?::\d|$)")
QUOTE_OPENERS = " :[{,\t\n"


def fenced_line_indexes(lines):
    """Indexes of the lines inside a fenced code block, the fence lines themselves included. A fence is closed by
    the same character, at least as long as the opener. A fence that is never closed runs to the last line."""
    fenced = set()
    opener = None
    for index, line in enumerate(lines):
        if opener is None:
            match = FENCE_OPEN.match(line)
            if match:
                opener = match.group(1)
                fenced.add(index)
            continue
        fenced.add(index)
        stripped = line.strip()
        if stripped and stripped[0] == opener[0] and set(stripped) == {opener[0]} and len(stripped) >= len(opener):
            opener = None
    return fenced


def _comparable_line(line):
    return CHECKBOX.sub("[ ]", " ".join(line.split()))


def lines_added(beforeLines, afterLines):
    """The lines of afterLines that beforeLines lacks, as they read in afterLines. Blank lines, whitespace-only
    changes and a markdown checkbox ticked or unticked do not make a line added."""
    beforeKeys = [_comparable_line(line) for line in beforeLines]
    afterKeys = [_comparable_line(line) for line in afterLines]
    matcher = difflib.SequenceMatcher(None, beforeKeys, afterKeys, autojunk=False)
    added = []
    for tag, _, _, afterStart, afterEnd in matcher.get_opcodes():
        if tag in ("insert", "replace"):
            added += [afterLines[i] for i in range(afterStart, afterEnd) if afterKeys[i]]
    return added


def wait_for(check, timeoutSeconds, intervalSeconds):
    """Call check() until it returns a truthy value, then return that value. Check once, then every
    intervalSeconds, for at most timeoutSeconds. Return None when nothing was found in that time."""
    deadline = time.monotonic() + timeoutSeconds
    while True:
        found = check()
        if found:
            return found
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        time.sleep(min(intervalSeconds, remaining))


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


def visible_text(line, in_comment):
    """Return (line without HTML comment text, still inside an unclosed comment). A `<!--` inside an
    inline code span opens nothing."""
    text = ""
    rest = line
    while rest:
        if in_comment:
            end = rest.find("-->")
            if end < 0:
                return text, True
            rest = rest[end + 3:]
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


def one_line(text, limit=200):
    """The text on one line: runs of whitespace collapse to a space, cut at `limit` characters."""
    return re.sub(r"\s+", " ", str(text)).strip()[:limit]


def contains_ignoring_whitespace(text, part):
    """True when `part` occurs in `text` once every run of whitespace in both reads as one space. An empty part
    is never contained."""
    squashedPart = " ".join(str(part).split())
    return bool(squashedPart) and squashedPart in " ".join(str(text).split())


def pre_tool_use_deny(reason):
    """Print the PreToolUse hook output that denies the tool call and shows `reason` to the model."""
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                             "permissionDecisionReason": reason}}))


def sortable_unique_id(now=None):
    """An id that sorts by creation time and does not repeat: local time to the second, a dash, six random hex
    digits. `now` is epoch seconds (default: the current time)."""
    epochSeconds = now if now is not None else time.time()
    localTime = time.localtime(epochSeconds)
    stamp = time.strftime("%Y%m%dT%H%M%S", localTime)
    return stamp + "-" + uuid.uuid4().hex[:6]


def unquote(text):
    """The text without one pair of matching outer quotes."""
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    return text


def first_number(text):
    """The first run of digits in the text as an int, or None."""
    found = re.search(r"\d+", text or "")
    return int(found.group()) if found else None


def quote_opens_at(text, position):
    return text[position] in "\"'" and (position == 0 or text[position - 1] in QUOTE_OPENERS)


def unquoted_mask(text):
    """The text with every quoted span blanked, so a word inside a quoted value is not read as a key."""
    masked = list(text)
    quote = None
    for position, character in enumerate(text):
        if quote:
            masked[position] = "x"
            quote = None if character == quote else quote
        elif quote_opens_at(text, position):
            quote = character
            masked[position] = "x"
    return "".join(masked)


def top_level_braces(text):
    """The {...} groups of a flow list, split on depth-0 braces outside quotes."""
    groups = []
    depth = 0
    quote = None
    start = 0
    for position, character in enumerate(text):
        if quote:
            quote = None if character == quote else quote
        elif quote_opens_at(text, position):
            quote = character
        elif character == "{":
            if depth == 0:
                start = position
            depth += 1
        elif character == "}" and depth:
            depth -= 1
            if depth == 0:
                groups.append(text[start:position + 1])
    return groups


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


def paths_named(*texts):
    """Every normalized path that the texts name, each once, in order: a text that starts with a file name, then
    every `path:line` token inside it."""
    paths = []
    for text in texts:
        text = str(text or "")
        candidates = [normalize_path(hit) for hit in PATH_LINE.findall(text)]
        firstToken = re.split(r"[\s,;|]", text.strip().strip("`'\""), maxsplit=1)[0]
        if FILE_NAME.match(firstToken):
            candidates.insert(0, normalize_path(firstToken))
        for path in candidates:
            if path and path not in paths:
                paths.append(path)
    return paths


def _nearest_existing_folder(path):
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


def inside_git_work_tree(path, timeoutSeconds=2):
    """True when path (a file or folder, which may not exist yet) lies inside a git work tree, False when it does
    not. A symlink is followed to its target. The inside of a .git folder and a bare repo are not a work tree.
    Asks `git rev-parse --is-inside-work-tree` from the nearest existing folder. When git cannot run, does not
    answer in time or exits with an error, looks for a .git entry in that folder or a parent instead."""
    folder = _nearest_existing_folder(path)
    try:
        done = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=folder, stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=timeoutSeconds)
    except (OSError, subprocess.SubprocessError):
        return _has_git_entry_above(folder)
    if done.returncode != 0:
        return _has_git_entry_above(folder)
    return done.stdout.strip() == "true"


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


def read_jsonl(path):
    """The rows of a JSON-lines file; a missing file is no rows and a torn or non-object line is skipped."""
    path = pathlib.Path(path)
    if not path.exists():
        return []
    objectRows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            objectRows.append(row)
    return objectRows


def nearest_file_upward(startDirectory, fileName, stopDirectory):
    """The nearest file called fileName in startDirectory or a parent of it, looking no higher than stopDirectory,
    or None. A startDirectory that is not inside stopDirectory finds nothing, `..` segments included. Both are
    pathlib.Path."""
    resolvedStart = startDirectory.resolve()
    if stopDirectory.resolve() not in (resolvedStart, *resolvedStart.parents):
        return None

    directory = startDirectory
    while True:
        candidate = directory / fileName
        if candidate.is_file():
            return candidate
        if directory == stopDirectory or stopDirectory not in directory.parents:
            return None
        directory = directory.parent


def directory_relative_to(rootDirectory, directory):
    """The directory's path under rootDirectory as text, or "" when it is rootDirectory itself. Both are
    pathlib.Path."""
    return str(directory.relative_to(rootDirectory)) if directory != rootDirectory else ""
