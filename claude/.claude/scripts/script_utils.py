"""script_utils.py: helpers for toolkit scripts that read plain values and need no module rule.

Installed as ~/.claude/scripts/script_utils.py. Scripts under ~/.claude/ import it from there by adding that
directory to sys.path."""
import difflib
import re
import time

FENCE_OPEN = re.compile(r"^\s*(`{3,}|~{3,})")
CHECKBOX = re.compile(r"\[[xX]\]")
INLINE_CODE_OR_COMMENT_OPEN = re.compile(r"`[^`]*`|<!--")


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
