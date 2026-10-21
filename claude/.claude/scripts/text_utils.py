"""Plain-text and file helpers that read no module table or rule. Python 3.9 stdlib only.

Not a hook or a command. Scripts import it from their own directory. Merge it into the shared script_utils module
when that lands.
"""
import json
import os
import pathlib
import re

PATH_LINE = re.compile(r"`?([\w@./-]+\.\w+:\d+(?:[-,]\d+)*)`?")
FILE_NAME = re.compile(r"^[\w@./-]+\.\w+(?::\d|$)")
QUOTE_OPENERS =" :[{,\t\n"


def one_line(text, limit=200):
    """The text on one line: runs of whitespace collapse to a space, cut at `limit` characters."""
    return re.sub(r"\s+", " ", str(text)).strip()[:limit]


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
