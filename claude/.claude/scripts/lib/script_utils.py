"""script_utils.py: helpers for toolkit scripts that read plain text, lines, paths and files and need no module rule.

Installed as ~/.claude/scripts/lib/script_utils.py. Scripts under ~/.claude/scripts/ import it from there by adding
that directory to sys.path."""
import difflib
import json
import os
import pathlib
import re
import signal
import stat
import subprocess
import time
import uuid

FENCE_OPEN = re.compile(r"^\s*(`{3,}|~{3,})")
MARKDOWN_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
CHECKBOX = re.compile(r"\[[xX]\]")
INLINE_CODE_OR_COMMENT_OPEN = re.compile(r"`[^`]*`|<!--")
PATH_LINE = re.compile(r"`?([\w@./-]+\.\w+:\d+(?:[-,]\d+)*)`?")
FILE_NAME = re.compile(r"^[\w@./-]+\.\w+(?::\d|$)")
QUOTE_OPENERS = " :[{,\t\n"
BACKTICKED = re.compile(r"`([^`]+)`")
TIMEOUT_EXIT_CODE = 124
COMMAND_NOT_FOUND_EXIT_CODE = 127
REPO_NAME_SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "tools" / "repo-name"
REPO_NAME_TIMEOUT_SECONDS = 10
# A literal value is plain characters or a quoted string with no `$`, backtick, `;`, `&`, `|`, `<`, `>` (and no
# backslash in a double-quoted one): the shell would run or expand anything else, so it is not a setting that can be
# copied. A plain word has no `~` either: the shell expands it at the start of a value and after a `:`, which
# shlex.split does not.
ENV_VALUE = r""""[^"$`;&|<>\\]*"|'[^'$`;&|<>]*'|[^\s"'$`;&|<>()\\~]*"""
ENV_ASSIGNMENT = re.compile(rf"([A-Za-z_][A-Za-z0-9_]*)=({ENV_VALUE})")
# What must follow the assignments: a word that is not another assignment and does not start with a shell control
# operator, a comment, a grouping or a negation. Without it "A=1 && cargo test" would read "&&" as the command.
COMMAND_WORD_AHEAD = r"(?![A-Za-z_][A-Za-z0-9_]*=)(?![;&|<>()#{}!])(?=\S)"
# The NAME=value words a command line starts with, each followed by whitespace, which the shell passes to the command.
# A command word must follow them. Only literal values: this reading builds the settings that get copied.
ENV_ASSIGNMENTS = re.compile(rf"(?:[A-Za-z_][A-Za-z0-9_]*=(?:{ENV_VALUE})\s+)+{COMMAND_WORD_AHEAD}")
# The same words with any value, one that expands a variable or runs a command included (`PATH=/x:$PATH cargo test`):
# the shell passes those to the command as well, so a reading that only finds where the command starts accepts them.
ENV_PREFIX_VALUE = r"""(?:"[^"]*"|'[^']*'|\$\([^)]*\)|[^\s"'`;&|<>()])*"""
ENV_PREFIX = re.compile(rf"(?:[A-Za-z_][A-Za-z0-9_]*={ENV_PREFIX_VALUE}\s+)+{COMMAND_WORD_AHEAD}")


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
        if heading is None:
            if open_level is not None:
                indexes.append(index)
            continue

        level = len(heading.group(1))
        if open_level is not None and level <= open_level:
            open_level = None
        if open_level is None and heading.group(2).strip() == heading_text:
            open_level = level
        elif open_level is not None:
            indexes.append(index)
    return indexes


def _comparable_line(line):
    return CHECKBOX.sub("[ ]", " ".join(line.split()))


def lines_added(before_lines, after_lines):
    """The lines of after_lines that before_lines lacks, as they read in after_lines. Blank lines, whitespace-only
    changes and a markdown checkbox ticked or unticked do not make a line added."""
    before_keys = [_comparable_line(line) for line in before_lines]
    after_keys = [_comparable_line(line) for line in after_lines]
    matcher = difflib.SequenceMatcher(None, before_keys, after_keys, autojunk=False)
    added = []
    for tag, _, _, after_start, after_end in matcher.get_opcodes():
        if tag in ("insert", "replace"):
            added += [after_lines[i] for i in range(after_start, after_end) if after_keys[i]]
    return added


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


def run_process(command, cwd, stdin=None, timeout=None, env=None):
    """Run a command (a list, or a string for the shell) in cwd and return (exit code, stdout, stderr), both as text.
    `env`, when given, is the command's whole environment. When the command does not finish in `timeout` seconds, kill
    its whole process group, so a shell command that started a server cannot keep the pipes open, and return (None,
    stdout, stderr) with what it printed."""
    process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.PIPE if stdin is not None else None,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                               shell=isinstance(command, str), start_new_session=True)
    try:
        stdout, stderr = process.communicate(stdin, timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
        return None, stdout, stderr
    return process.returncode, stdout, stderr


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


def run_command(command, cwd=None, stdin=None, timeout=None):
    """Run a command as run_process does and return (exit code, stdout and stderr joined and stripped). A program that
    is not found exits COMMAND_NOT_FOUND_EXIT_CODE; a run past `timeout` seconds exits TIMEOUT_EXIT_CODE with a note
    after what it printed."""
    try:
        code, stdout, stderr = run_process(command, cwd, stdin=stdin, timeout=timeout)
    except FileNotFoundError:
        program = command if isinstance(command, str) else command[0]
        return COMMAND_NOT_FOUND_EXIT_CODE, f"{program}: command not found"

    output = (stdout + stderr).strip()
    if code is None:
        return TIMEOUT_EXIT_CODE, (output + f"\ntimed out after {timeout} seconds").strip()
    return code, output


def run_or_raise(argv, error_type, cwd=None, check=False, stdin=None, ok_codes=(0,), timeout=None):
    """Run argv and return the CompletedProcess, its output decoded as UTF-8 with no newline translation. Raise
    error_type when argv cannot start or runs past `timeout` seconds and, with check, when its exit code is not in
    ok_codes, naming the command and its stderr, or its stdout when stderr is empty."""
    stdin_bytes = None if stdin is None else stdin.encode()
    try:
        finished = subprocess.run(argv, cwd=cwd, input=stdin_bytes, capture_output=True, timeout=timeout)
    except OSError as error:
        raise error_type(f"cannot run {argv[0]}: {error}") from error
    except subprocess.TimeoutExpired as error:
        raise error_type(f"`{' '.join(argv)}` ran past {timeout} seconds") from error

    finished.stdout = finished.stdout.decode("utf-8", "replace")
    finished.stderr = finished.stderr.decode("utf-8", "replace")
    if check and finished.returncode not in ok_codes:
        detail = finished.stderr.strip() or finished.stdout.strip()
        raise error_type(f"`{' '.join(argv)}` failed: {detail}")
    return finished


def repo_root(cwd, timeout=None):
    """The top level of the git work tree that holds cwd, or None outside one."""
    top = git_output(cwd, "rev-parse", "--show-toplevel", timeout=timeout)
    if not top:
        return None
    return pathlib.Path(top)


def current_branch(cwd, timeout=None):
    """The checked-out branch name: "" on a detached HEAD, None when git fails."""
    return git_output(cwd, "branch", "--show-current", timeout=timeout)


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
        try:
            done = subprocess.run(argv, capture_output=True, text=True, errors="replace", timeout=timeout_seconds,
                                  **run_kwargs)
        except subprocess.TimeoutExpired:
            if attempt == attempts:
                raise
        else:
            if done.returncode not in retry_exit_codes or attempt == attempts:
                return done
        sleep(backoff_seconds * attempt)


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
    squashed_part = " ".join(str(part).split())
    return bool(squashed_part) and squashed_part in " ".join(str(text).split())


def has_whitespace(text):
    """True when `text` holds any whitespace character: a space, tab or newline."""
    return re.search(r"\s", str(text)) is not None


def words_of_arguments(arguments):
    """The words of command-line text. One argument that holds spaces is split at them (the text came quoted as a
    whole); several arguments are kept as they were given."""
    return arguments[0].split() if len(arguments) == 1 else list(arguments)


def strip_flag_values(command, flags):
    """`command` with every `flag value` and `flag=value` pair of the named flags replaced by one space. A flag
    matches as a whole word. Its value is the next word, or the next quoted text, unless that word starts with a dash:
    a flag followed by another flag, or by nothing, is left as it is."""
    if not flags:
        return command
    names = "|".join(re.escape(flag) for flag in sorted(flags, key=len, reverse=True))
    quoted_or_word = r"""(?:"[^"]*"|'[^']*'|\S+)"""
    pair = re.compile(rf"(?<!\S)(?:{names})(?:={quoted_or_word}?|\s+(?!-){quoted_or_word})")
    return pair.sub(" ", command)


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


def pre_tool_use_deny(reason):
    """Print the PreToolUse hook output that denies the tool call and shows `reason` to the model."""
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                             "permissionDecisionReason": reason}}))


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
        first_token = re.split(r"[\s,;|]", text.strip().strip("`'\""), maxsplit=1)[0]
        if FILE_NAME.match(first_token):
            candidates.insert(0, normalize_path(first_token))
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


def inside_git_work_tree(path, timeout_seconds=2):
    """True when path (a file or folder, which may not exist yet) lies inside a git work tree, False when it does
    not. A symlink is followed to its target. The inside of a .git folder and a bare repo are not a work tree.
    Asks `git rev-parse --is-inside-work-tree` from the nearest existing folder. When git cannot run, does not
    answer in time or exits with an error, looks for a .git entry in that folder or a parent instead."""
    folder = _nearest_existing_folder(path)
    answer = git_output(folder, "rev-parse", "--is-inside-work-tree", timeout=timeout_seconds)
    if answer is None:
        return _has_git_entry_above(folder)
    return answer.strip() == "true"


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


def write_text_atomically(path, text):
    """Write `text` to `path` so a reader sees the old file or the new one, never a half-written file."""
    path = pathlib.Path(path)
    temp_path = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")

    # A new file gets 0o666 less the umask, as write_text gives. The kernel applies the umask here, so it is never read.
    descriptor = os.open(temp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
    try:
        with os.fdopen(descriptor, "w") as temp_file:
            temp_file.write(text)
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


def is_executable_file_inside(root_directory, relative_path):
    """True when relative_path, taken from root_directory, names an executable file inside root_directory. A path that
    leaves root_directory (a `..` segment or a link out) is not one. root_directory is a pathlib.Path or text."""
    resolved_root = pathlib.Path(root_directory).resolve()
    candidate = (resolved_root / relative_path).resolve()
    if not candidate.is_relative_to(resolved_root):
        return False

    return candidate.is_file() and os.access(candidate, os.X_OK)
