#!/usr/bin/env python3
"""A coder dispatch obligates /review before a commit in the repo the coder changed.

  PostToolUse(Agent): a coder dispatch is recorded with the id of the agent it ran.
  PreToolUse(Bash):   `git commit` in a dirty repo is denied, with the reason telling the session to run /review and
                      commit after it converges; `review-gate-mark clean|dirty` records that state for every repo.
                      `clean` is denied unless this session's latest stored review-loop hand-back (handback.py) is
                      converged or deferred.

At commit time each recorded coder is scoped by its own transcript: the repos that hold the files its Edit, Write,
MultiEdit and NotebookEdit calls named. A repo is dirty when a coder edited it, or when a coder cannot be scoped (no
transcript, no edit on record, a file outside a repo) or a `dirty` mark stands, which dirties every repo. A coder's
Bash writes are not read, so a coder that also edits a file elsewhere leaves a repo it changed only through Bash
clean. A commit whose repo the gate cannot tell is judged against every repo.

A dirty commit that ships only notes is not denied. The commit passes when every path it can ship is a Markdown file
under the repo's top-level docs/ folder: the paths already staged (`git diff --cached`, run in the hook input's
cwd), every `git add` pathspec in the command, and every commit pathspec. Each pathspec must name one file
literally: a folder, `.`, a glob, `~`, `$` or a `:` magic pathspec is denied. It is denied when the command can
stage or pick more than that, or when the hook cannot tell which repo or files it uses:
  - `git add` with any option except `--`
  - `git commit` with an option other than the plain flags and message options it knows, so `-a`, `--all`, `-i`,
    `--include`, `--amend` and `-o`/`--only` with no pathspec are all denied
  - any command that is not git and not echo, printf, true, pwd or ls (so `cd`, `env`, `time`, a group, a function,
    a path to git, an assignment before a command), `git -C` or another git option before the subcommand, a git
    subcommand other than add, commit, status, diff, log, show or rev-parse
  - a word with `$` or a backtick, unless the whole word is a quoted-heredoc message `$(cat <<'X' ... X)`
  - a status, diff, log, show or rev-parse with a `--output` option, since it writes a file
  - an output redirection (`>`, `>>`, `&>`, `n>`) whose target is not /dev/null or a file-descriptor copy (`2>&1`),
    since it can rewrite a hook or the index; an input redirection is fine
  - no `git commit` in the command, or more than one
  - a command shlex cannot read, a missing cwd, a git error or timeout, an empty list of paths, a pathspec that
    names a folder
A command counts as a commit when, with line continuations removed, it matches `git commit` as text (not
`git commit-tree` or `git commit-graph`, which move no branch), or `git`, then
only global options (a known one that takes a value is followed by it, which may be quoted or a `$( )` or backtick
substitution), then `commit` appears in it, or when a simple command runs git (any word whose base name is `git`, so
`env git` or a path counts), with any global options, and then `commit`. A global option the hook does not know may
take a value, so `commit` anywhere after it counts. A command shlex cannot read counts when `git`, then only
option-like words with an optional value each, then `commit` appears in it.
The session stays dirty; a later commit that ships code is denied again.

A dirty repo still commits in four more cases, each checked against something a subagent cannot write:
  - the user's latest prompt in the main transcript starts with `[no-review]` (the user ordered this turn's commits
    without review; a task notification, a peer session's message, a compaction summary, a `!` shell echo and a tool
    result are not the user's prompt and are skipped)
  - the commit concludes a merge (the repo it commits in has a MERGE_HEAD)
  - the working tree of the repo it commits in is the tree a converged review covered (reviewed_tree.py), so work
    that converged in /code's review-loop, or in /review, commits after a later coder dispatch that edited nothing
  - the session's latest review-loop hand-back is current, converged or deferred, came after the coder work that
    made the repo dirty, and answers a review-loop dispatch of that repo (its `repo:` line, else the session cwd),
    however the run that launched the loop closed.
With no `cd`, `pushd` or `popd` in its text, the commit runs in the one repo `git -C <dir>` names (every -C joined),
relative to the hook input's cwd, else the cwd; `--git-dir` or `--work-tree` leaves it unknown. A command that
changes folder anywhere is judged against every candidate repo (candidate_repo_dirs): the cwd plus each folder a
word of the command names. Each candidate must be clean or earn one of the credits above. The gate never follows
the chain's shape. A target no word names (a `$`, a backtick, `eval`, `popd`, `cd -`) adds an unknown candidate.
An unknown repo is judged against every repo and gets no merge, reviewed-tree or hand-back credit.

State: ~/.claude/state/review-gate/<session>, one line per record: `clean` (a clean mark; earlier lines no longer
count), or a JSON event {"kind": "dispatch"|"dirty", "ts", "agent"}. A plain `dirty` line, from
before events carried a time, counts from the file's last change. Hook JSON in, one permissionDecision line out,
exit 0. On an internal error PreToolUse asks the user; PostToolUse stays silent.
"""
import contextlib
import json
import os
import posixpath
import re
import shlex
import sys
import time

_SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path[:0] = [_SCRIPT_DIR, os.path.join(os.path.dirname(_SCRIPT_DIR), "lib")]
import hook_input
import reviewed_tree
import script_utils
from hook_input import EMPTY_INPUT, JqError, jq_field, jq_get, prune_old_state_files
from shell_command import parse_simple_commands, redirection_writes_file, split_command_steps, split_simple_commands

CODERS = ("coder", "coder-deep", "backend-coder", "backend-coder-deep", "frontend-coder", "frontend-coder-deep")
# The tools that write a file, and the input key that names it.
EDITING_TOOLS = {"Edit": "file_path", "Write": "file_path", "MultiEdit": "file_path", "NotebookEdit": "notebook_path"}
AGENT_ID = re.compile(r"[A-Za-z0-9_-]+")
# A command that changes folder anywhere in its text. The gate never parses where the chain leads.
CHANGES_FOLDER = re.compile(r"(?<![\w./-])(?:cd|pushd|popd)(?![\w./-])")
# A folder change whose target no word of the command names.
UNKNOWN_TARGET = re.compile(r"[$`]|(?<![\w./-])(?:eval|source|popd)(?![\w./-])"
                            r"|(?<![\w./-])(?:cd|pushd)[ \t]+-(?![\w./-])|(?<![\w./-])pushd[ \t]*(?:$|[;&|)\n])"
                            r"|--git-dir|--work-tree|GIT_DIR|GIT_WORK_TREE",
                            re.MULTILINE)
BARE_CD = re.compile(r"(?<![\w./-])cd[ \t]*(?:$|[;&|)\n])", re.MULTILINE)
WORD_BREAK = re.compile(r"""[\s;&|()<>{}=`'"]+""")
# `(?!-)`: `git commit-tree` and `git commit-graph` write objects and move no branch.
COMMIT = re.compile(r"\bgit[ \t\r\f\v]+commit\b(?!-)")
LINE_CONTINUATION = re.compile(r"\\\r?\n")
# An option's value: a quoted string, a `$( )` or backtick substitution, or a plain word.
OPTION_VALUE = r"""(?:"[^"]*"|'[^']*'|\$\([^()]*\)|`[^`]*`|\S+)"""
# For a command shlex cannot read: git, then only option-like words with an optional value each, then commit.
UNREADABLE_GIT_THEN_COMMIT = re.compile(r"\bgit(?:[ \t]+-\S+(?:[ \t]+" + OPTION_VALUE + r")?)*[ \t]+commit\b(?!-)")
MARK = re.compile(r"review-gate-mark[ \t\n\r\f\v]+(clean|dirty)")
GIT_TIMEOUT_SECONDS = 3
NO_REVIEW_MARKER = "[no-review]"
DOCS_FOLDER = "docs/"
NOTES_SUFFIX = ".md"
# Characters a shell or git would expand in a pathspec, and a newline.
EXPANDING_CHARS = set("*?[]{}$`~\\\n")
READ_ONLY_GIT = ("status", "diff", "log", "show", "rev-parse")
READ_ONLY_PROGRAMS = ("echo", "printf", "true", "pwd", "ls")
# A message word `$(cat <<'X'` + body + `X` + `)` runs nothing: the body is quoted and ends at the first line X.
HEREDOC_MESSAGE = re.compile(r"\$\(cat <<'(?P<tag>[A-Za-z_]\w*)'\n(?:(?!(?P=tag)\n).*\n)*(?P=tag)\n\)")
GIT_GLOBAL_OPTIONS_WITH_VALUE = ("-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--super-prefix",
                                 "--config-env", "--attr-source")
GIT_GLOBAL_FLAGS = ("-p", "--paginate", "-P", "--no-pager", "--bare", "--no-replace-objects", "--literal-pathspecs",
                    "--glob-pathspecs", "--noglob-pathspecs", "--icase-pathspecs", "--no-optional-locks",
                    "--no-lazy-fetch", "--no-advice")
# Run on the text, so a command shlex reads wrongly or not at all still counts: git, then only git's global options
# (a known option that takes a value is followed by it; any other option-like word stands alone), then commit.
GIT_VALUE_OPTIONS = "|".join(re.escape(option) for option in GIT_GLOBAL_OPTIONS_WITH_VALUE)
GIT_THEN_COMMIT = re.compile(r"\bgit(?:[ \t]+(?:(?:" + GIT_VALUE_OPTIONS + r")[ \t]+" + OPTION_VALUE + r"|-\S+))*"
                             r"[ \t]+commit\b(?!-)")
COMMIT_FLAGS = {"-q", "-v", "-s", "-n", "-e", "-o", "--quiet", "--verbose", "--signoff", "--no-verify", "--edit",
                "--no-edit", "--allow-empty", "--allow-empty-message", "--no-gpg-sign", "--no-post-rewrite",
                "--only", "--status", "--no-status"}
COMMIT_ONLY_FLAGS = {"-o", "--only"}
COMMIT_VALUE_OPTIONS = {"--message", "--file", "--author", "--date", "--trailer", "--template", "--cleanup",
                        "--reuse-message", "--reedit-message"}
COMMIT_VALUE_LETTERS = "mFCct"


class DenyError(Exception):
    pass


def short_flags(word):
    """For one bundle of short `git commit` options such as `-qm`: (it holds -o, the next word is the value of its
    last letter), or None when a letter before the first value letter is not a known flag."""
    letters = word[1:]
    only_given = False
    for position, letter in enumerate(letters):
        if letter in COMMIT_VALUE_LETTERS:
            return only_given, position == len(letters) - 1
        if "-" + letter not in COMMIT_FLAGS:
            return None
        only_given = only_given or "-" + letter in COMMIT_ONLY_FLAGS
    return only_given, False


def commit_pathspecs(args):
    """The pathspecs in the words after `git commit`, or None when a word is an option other than a plain flag or a
    message-style option with its value. `--` ends the options."""
    pathspecs = []
    only_given = False
    options_ended = False
    index = 0
    while index < len(args):
        word = args[index]
        index += 1
        if options_ended or not word.startswith("-") or word == "-":
            pathspecs.append(word)
            continue
        if word == "--":
            options_ended = True
            continue
        if word.startswith("--"):
            name, has_value, _ = word.partition("=")
            if name in COMMIT_VALUE_OPTIONS:
                index += 0 if has_value else 1
                continue
            if name not in COMMIT_FLAGS or has_value:
                return None
            only_given = only_given or name in COMMIT_ONLY_FLAGS
            continue
        flags = short_flags(word)
        if flags is None:
            return None
        bundle_only, value_follows = flags
        only_given = only_given or bundle_only
        index += 1 if value_follows else 0
    if only_given and not pathspecs:
        return None
    return pathspecs


def add_pathspecs(args):
    """The pathspecs after `git add`, or None when there is an option other than `--` or no pathspec."""
    pathspecs = []
    options_ended = False
    for word in args:
        if not options_ended and word == "--":
            options_ended = True
            continue
        if not options_ended and word.startswith("-"):
            return None
        pathspecs.append(word)
    return pathspecs or None


def runs_substitution(word):
    """True when a word holds `$` or a backtick, other than a whole quoted-heredoc message."""
    if "$" not in word and "`" not in word:
        return False
    return HEREDOC_MESSAGE.fullmatch(word) is None


def is_known_git_global_option(option):
    name, has_value, _ = option.partition("=")
    return option in GIT_GLOBAL_FLAGS or (bool(has_value) and name in GIT_GLOBAL_OPTIONS_WITH_VALUE)


def runs_git_commit(words):
    """True when the simple command runs git, with any global options, then `commit`. Git is any word whose base
    name is `git`, so `env`, `command`, `time`, `!`, a path or an earlier `git` argument before it do not hide it. An
    option git is not known to have before the subcommand may take a value, so it counts when `commit` comes anywhere
    after it."""
    git_indexes = [index for index, word in enumerate(words) if posixpath.basename(word) == "git"]
    return any(commit_follows_git(words, git_index) for git_index in git_indexes)


def commit_follows_git(words, git_index):
    index = git_index + 1
    unknown_option = False
    while index < len(words) and words[index].startswith("-"):
        option = words[index]
        if option in GIT_GLOBAL_OPTIONS_WITH_VALUE:
            index += 2
            continue
        unknown_option = unknown_option or not is_known_git_global_option(option)
        index += 1
    if index < len(words) and words[index] == "commit":
        return True
    return unknown_option and "commit" in words[index:]


def is_commit_command(command):
    """True when the command commits. On the text with line continuations removed, `git commit` or `git`, then only
    global options (a known one that takes a value is followed by it, which may be quoted or a substitution), then
    `commit` counts, whether or not shlex can read the command. A git simple command with global options before
    `commit` counts too. A command shlex cannot read also counts when `git`, then only option-like words with an
    optional value each, then `commit` appears in it."""
    joined = LINE_CONTINUATION.sub("", command)
    if COMMIT.search(joined) or GIT_THEN_COMMIT.search(joined):
        return True
    try:
        simple_commands = split_simple_commands(joined)
    except ValueError:
        return UNREADABLE_GIT_THEN_COMMIT.search(joined) is not None
    return any(runs_git_commit(words) for words in simple_commands)


PATHSPEC_READERS = {"commit": commit_pathspecs, "add": add_pathspecs}


def simple_command_is_safe(words, redirections):
    """True when one simple command writes no file and runs nothing this reading cannot follow: an empty command, a
    read-only program, or git add, git commit or a read-only git subcommand, with no `$` or backtick word other than
    a quoted-heredoc message."""
    if any(redirection_writes_file(operator, target) for operator, target in redirections):
        return False
    if any(runs_substitution(word) for word in words):
        return False
    if not words:
        return True
    if words[0] != "git":
        return words[0] in READ_ONLY_PROGRAMS
    if len(words) < 2:
        return False
    # A git option before the subcommand (-C, -c, --git-dir) lands here as the subcommand and is refused.
    subcommand, args = words[1], words[2:]
    if subcommand in PATHSPEC_READERS:
        return True
    # `--output` makes a read-only subcommand write a file, such as a hook.
    return subcommand in READ_ONLY_GIT and not any(word.startswith("--output") for word in args)


def command_pathspecs(command):
    """(add pathspecs, commit pathspecs) of a command that holds exactly one `git commit` and nothing that changes
    the repo, the directory or the index in a way this reading cannot follow; None for any other command."""
    try:
        simple_commands = parse_simple_commands(command)
    except ValueError:
        return None
    if not all(simple_command_is_safe(words, redirections) for words, redirections in simple_commands):
        return None

    git_calls = [words[1:] for words, _ in simple_commands if words[:1] == ["git"] and words[1] in PATHSPEC_READERS]
    subcommands = [subcommand for subcommand, *_ in git_calls]
    if subcommands.count("commit") != 1:
        return None

    pathspecs = {"add": [], "commit": []}
    for subcommand, *args in git_calls:
        found = PATHSPEC_READERS[subcommand](args)
        if found is None:
            return None
        pathspecs[subcommand] += found
    return pathspecs["add"], pathspecs["commit"]


def is_notes_path(path):
    return path.startswith(DOCS_FOLDER) and path.endswith(NOTES_SUFFIX)


def repo_path(pathspec, prefix):
    """The repo-root-relative path a literal pathspec names from the directory `prefix` below the root, or None."""
    if pathspec.startswith((":", "/")) or pathspec.endswith("/") or EXPANDING_CHARS & set(pathspec):
        return None
    return posixpath.normpath(prefix + pathspec)


def ships_only_notes(command, cwd):
    """True when every path the commit can ship is a Markdown file under the repo's top-level docs/ folder."""
    found = command_pathspecs(command)
    if found is None or not cwd:
        return False
    add_paths, commit_paths = found

    staged_output = script_utils.git_output(cwd, "diff", "--cached", "--name-only", "--no-renames", "--no-relative",
                                            "-z", timeout=GIT_TIMEOUT_SECONDS)
    prefix = script_utils.git_output(cwd, "rev-parse", "--show-prefix", timeout=GIT_TIMEOUT_SECONDS)
    if staged_output is None or prefix is None:
        return False

    shipped_paths = [path for path in staged_output.split("\0") if path]
    for pathspec in add_paths + commit_paths:
        if os.path.isdir(os.path.join(cwd, pathspec)):
            return False
        shipped_paths.append(repo_path(pathspec, prefix) or "")
    return bool(shipped_paths) and all(is_notes_path(path) for path in shipped_paths)


def read_event(raw):
    """The hook event JSON; empty input reads as the empty event."""
    if raw.strip() == "":
        return EMPTY_INPUT
    try:
        return json.loads(raw)
    except ValueError:
        raise JqError(2) from None


def open_state_dir():
    """The gate's state folder, made when missing, with stale session files pruned."""
    state_dir = os.environ["HOME"] + "/.claude/state/review-gate"
    try:
        os.makedirs(state_dir, exist_ok=True)
    except OSError as error:
        hook_input.emit_stderr(f"review-commit-gate: cannot create {state_dir}: {error.strerror}\n")
        raise JqError(1) from None
    prune_old_state_files(state_dir)
    return state_dir


def gate_events(state_file):
    """The state events after the last clean mark, oldest first. A plain `dirty` line, and a line the gate cannot
    read, become a dirty event at the file's last change."""
    try:
        with open(state_file, "rb") as handle:
            lines = handle.read().decode("utf-8", "replace").splitlines()
        changed_at = os.path.getmtime(state_file)
    except OSError:
        return []

    events = []
    for line in lines:
        if line == "clean":
            events = []
            continue
        try:
            event = json.loads(line)
        except ValueError:
            event = None
        if not isinstance(event, dict) or not isinstance(event.get("ts"), (int, float)):
            event = {"kind": "dirty", "ts": changed_at}
        events.append(event)
    return events


def subagent_transcript(transcript_path, agent_id):
    """The transcript of the session's subagent agent_id: Claude Code keeps every subagent's, nested ones too, in
    `<session transcript without .jsonl>/subagents/agent-<id>.jsonl`. None without a transcript or an id."""
    if not transcript_path or not isinstance(agent_id, str) or not AGENT_ID.fullmatch(agent_id):
        return None
    return os.path.join(os.path.splitext(transcript_path)[0], "subagents", f"agent-{agent_id}.jsonl")


def edited_files(agent_transcript):
    """The files an agent's Edit, Write, MultiEdit and NotebookEdit calls named in its transcript, or None when the
    transcript cannot be read."""
    edited = set()
    try:
        with open(agent_transcript, encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                content = (record.get("message") or {}).get("content") if isinstance(record, dict) else None
                if not isinstance(content, list):
                    continue
                for block in content:
                    if not isinstance(block, dict) or block.get("type") != "tool_use":
                        continue
                    path_key = EDITING_TOOLS.get(block.get("name"))
                    path = (block.get("input") or {}).get(path_key) if path_key else None
                    if isinstance(path, str) and path:
                        edited.add(path)
    except OSError:
        return None
    return edited


def file_repo(file_path, repo_tops):
    """The top of the git work tree that holds file_path, or None. repo_tops caches the answer per folder."""
    # A Write can make a new folder, so the nearest folder that exists is the one git is asked about.
    folder = os.path.dirname(file_path)
    while folder and not os.path.isdir(folder):
        parent = os.path.dirname(folder)
        folder = "" if parent == folder else parent
    if folder not in repo_tops:
        top = script_utils.repo_root(folder, timeout=GIT_TIMEOUT_SECONDS) if folder else None
        repo_tops[folder] = str(top) if top else None
    return repo_tops[folder]


def coder_repos(transcript_path, agent_id, repo_tops):
    """(the repo tops a coder agent edited files in, the last change to its transcript), or (None, 0) when the
    gate cannot scope it: no transcript, no edit on record (it wrote through Bash only), or a file outside a repo
    git can name."""
    agent_transcript = subagent_transcript(transcript_path, agent_id)
    edited = edited_files(agent_transcript) if agent_transcript else None
    if not edited:
        return None, 0
    repos = {file_repo(path, repo_tops) for path in edited}
    if None in repos:
        return None, 0
    return repos, os.path.getmtime(agent_transcript)


def dirty_since(events, repo_top, transcript_path):
    """When the repo at repo_top became dirty: the latest dirty mark, or coder dispatch whose agent edited it or
    cannot be scoped. A coder counts from its dispatch or its transcript's last change, whichever is later, since a
    background coder edits after its dispatch is recorded. With repo_top None, every repo counts. None when the repo
    is clean."""
    repo_tops = {}
    dirty_times = []
    for event in events:
        if event.get("kind") != "dispatch":
            dirty_times.append(event["ts"])
            continue
        repos, worked_until = coder_repos(transcript_path, event.get("agent"), repo_tops)
        if repos is None or repo_top is None or repo_top in repos:
            dirty_times.append(max(event["ts"], worked_until))
    return max(dirty_times, default=None)


def on_post_tool_use(root, state_file):
    """Record a coder dispatch with the id of the agent it ran."""
    if jq_field(root, "tool_input", "subagent_type") not in CODERS:
        return
    tool_response = jq_get(root, "tool_response")
    agent_id = tool_response.get("agentId") if isinstance(tool_response, dict) else None
    script_utils.append_jsonl(state_file, {"kind": "dispatch", "ts": time.time(), "agent": agent_id or None})


# Records a user prompt never is: a peer session's message (old form) and Claude Code's own shell and command echoes.
NOT_TYPED_PREFIXES = ("<bash-input>", "<bash-stdout>", "<bash-stderr>", "<local-command-", "<cross-session-message",
                      "Another Claude session sent a message")


def prompt_text(record):
    """The text of a transcript record when it is a prompt the user typed in the main session, else None. A tool
    result, a meta record (command expansions, reminders), a subagent record, a record with an origin other than
    the human (a peer message, a task notification), a compaction summary and a shell or command echo are not the
    user's words."""
    if record.get("type") != "user" or record.get("isMeta") or record.get("isSidechain"):
        return None
    origin = record.get("origin")
    if record.get("isCompactSummary") or (isinstance(origin, dict) and origin.get("kind") != "human"):
        return None
    content = (record.get("message") or {}).get("content")
    if isinstance(content, list) and all(isinstance(block, dict) and block.get("type") == "text"
                                         for block in content):
        content = "".join(str(block.get("text", "")) for block in content)
    if not isinstance(content, str) or content.lstrip().startswith(NOT_TYPED_PREFIXES):
        return None
    return content


def user_ordered_no_review(root):
    """True when the user's latest prompt in the main transcript starts with the no-review marker. Records that are
    not the user's prompt are skipped, so a message that arrives later does not end the order."""
    transcript_path = jq_field(root, "transcript_path")
    if not transcript_path:
        return False
    latest_prompt = None
    try:
        with open(transcript_path, encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                text = prompt_text(record) if isinstance(record, dict) else None
                if text is not None and text.strip():
                    latest_prompt = text
    except OSError:
        return False
    return latest_prompt is not None and latest_prompt.lstrip().startswith(NO_REVIEW_MARKER)


def candidate_repo_dirs(command, cwd):
    """The directories a commit in the command may run in; None stands for one the gate cannot name. A command with
    no `cd`, `pushd` or `popd` anywhere in its text commits in the one directory commit_repo_dir reads. Otherwise
    every candidate counts, whatever the shape of the chain: the cwd, each word of the command (quoted words split
    on spaces) that names a directory read from the cwd or from another candidate, and HOME for a bare `cd`. A `$`,
    a backtick, `eval`, `source`, `popd`, `cd -`, a bare `pushd`, a git dir or work-tree option or variable adds
    None."""
    if not CHANGES_FOLDER.search(command):
        return [commit_repo_dir(command, cwd)]

    candidates = [os.path.normpath(cwd)] if cwd else [None]
    if UNKNOWN_TARGET.search(command) or not cwd:
        candidates.append(None)
    if BARE_CD.search(command):
        candidates.append(os.path.expanduser("~"))

    words = set(WORD_BREAK.split(command))
    with contextlib.suppress(ValueError):
        words.update(shlex.split(command))
    words.discard("")
    found_new = True
    while found_new:
        found_new = False
        for base in [candidate for candidate in candidates if candidate]:
            for word in words:
                path = os.path.normpath(os.path.join(base, os.path.expanduser(word)))
                if path not in candidates and os.path.isdir(path):
                    candidates.append(path)
                    found_new = True

    # A folder outside every work tree holds no repo to commit in.
    return [candidate for candidate in candidates
            if candidate is None or script_utils.repo_root(candidate, timeout=GIT_TIMEOUT_SECONDS)]


def commit_repo_dir(command, cwd):
    """The directory a `git commit` in the command runs in: the cwd, moved by each `git -C <dir>` before the
    subcommand. None when the command cannot be read, holds no commit, or uses an option that moves the repo
    (--git-dir, --work-tree) the gate does not follow."""
    if not cwd:
        return None
    for _, step in split_command_steps(LINE_CONTINUATION.sub("", command)):
        try:
            simple_commands = split_simple_commands(step)
        except ValueError:
            return None
        for words in simple_commands:
            committed_in = commit_dir(words, cwd)
            if committed_in is not None:
                return committed_in or None
    return None


def commit_dir(words, directory):
    """The directory a simple command `git [-C <dir>]... commit` commits in, from `directory`; "" when it is a git
    command whose options the gate does not follow; None for any other command."""
    if posixpath.basename(words[0]) != "git":
        return None
    index = 1
    while index < len(words) and words[index].startswith("-"):
        option = words[index]
        if option == "-C" and index + 1 < len(words):
            directory = os.path.join(directory, words[index + 1])
            index += 2
        elif is_known_git_global_option(option) and not option.startswith(("--git-dir", "--work-tree")):
            index += 1
        else:
            return ""
    if index < len(words) and words[index] == "commit":
        return os.path.normpath(directory)
    return None


def concludes_merge(repo_dir):
    """True when the repo has a merge in progress, so the commit is the merge commit."""
    merge_head = script_utils.git_output(repo_dir, "rev-parse", "-q", "--verify", "MERGE_HEAD",
                                         timeout=GIT_TIMEOUT_SECONDS)
    return bool(merge_head)


def review_handed_back_since(session, dirty_at, repo_top):
    """True when the session's latest review-loop hand-back is current, converged or deferred, was stored after
    `dirty_at`, and answers a dispatch that reviewed repo_top."""
    if repo_top is None:
        return False
    try:
        import handback
    except ImportError:
        return False
    if handback.false_clean_reason(session) is not None:
        return False
    seen = handback.latest(session)
    if seen["dispatch"].get("repo") != repo_top:
        return False
    handed_back_at = seen["handback"].get("ts")
    return isinstance(handed_back_at, (int, float)) and handed_back_at > dirty_at


def holds_unreviewed_work(repo_dir, events, session, transcript_path):
    """True when a commit in repo_dir would ship coder work that no merge, reviewed tree or converged hand-back
    covers. A repo_dir of None, or one outside a work tree, is judged against every repo."""
    repo_top = script_utils.repo_root(repo_dir, timeout=GIT_TIMEOUT_SECONDS) if repo_dir else None
    repo_top = str(repo_top) if repo_top else None
    dirty_at = dirty_since(events, repo_top, transcript_path)
    if dirty_at is None:
        return False

    if repo_dir and (concludes_merge(repo_dir) or reviewed_tree.is_reviewed(session, repo_dir)):
        return False
    return not review_handed_back_since(session, dirty_at, repo_top)


def check_commit(command, root, state_file, session):
    """Deny a commit when any directory it may run in holds unreviewed coder work, unless the user ordered it
    without review or it ships only notes."""
    events = gate_events(state_file)
    if not events:
        return
    if user_ordered_no_review(root):
        return

    cwd = jq_field(root, "cwd")
    transcript_path = jq_field(root, "transcript_path")
    dirty_dirs = [repo_dir for repo_dir in candidate_repo_dirs(command, cwd)
                  if holds_unreviewed_work(repo_dir, events, session, transcript_path)]
    if not dirty_dirs:
        return
    if ships_only_notes(command, cwd):
        return
    raise DenyError(
        "[review-commit-gate] Coder work from this session has no converged /review. Do not stop or ask "
        "the user: invoke the /review skill now on the coder work, then commit after it converges. If the "
        "commit ships only Markdown files under the repo's top-level docs/ folder, run it as a plain "
        "`git commit` (with `git add` of single named files if needed) from the repo root in its own "
        "Bash call, with no `cd`, `env` or `git -C`, because the gate passes that form."
    )


def apply_mark(mark, session, state_file, cwd):
    """Record `review-gate-mark clean|dirty`. `clean` is denied without a converged or deferred hand-back."""
    if mark == "clean":
        # Imported here, not at load: a missing module is an internal error on a `clean` mark only, and the
        # commit check and the dirty mark keep working.
        import handback
        reason = handback.false_clean_reason(session)
        if reason:
            raise DenyError(
                f"[review-commit-gate] Gate not marked clean: {reason}. Only a converged or deferred review "
                "hand-back from this session allows clean."
            )
    # A mark stands for every repo, so it replaces the events before it.
    line = mark if mark == "clean" else json.dumps({"kind": "dirty", "ts": time.time()})
    with open(state_file, "w") as handle:
        handle.write(line + "\n")
    if mark == "clean" and cwd:
        reviewed_tree.record_reviewed(session, cwd)


def on_pre_tool_use(root, session, state_file):
    """A commit command is checked and never also marks; any other command may mark."""
    command = jq_field(root, "tool_input", "command")
    if is_commit_command(command):
        check_commit(command, root, state_file, session)
        return
    marked = MARK.search(command)
    if marked:
        apply_mark(marked.group(1), session, state_file, jq_field(root, "cwd"))


def run(raw, state):
    root = read_event(raw)
    event = jq_field(root, "hook_event_name")
    state["event"] = event
    session = jq_field(root, "session_id", default="unknown")

    state_file = open_state_dir() + "/" + session
    if event == "PostToolUse":
        on_post_tool_use(root, state_file)
    elif event == "PreToolUse":
        on_pre_tool_use(root, session, state_file)


def main():
    if os.environ.get("CLAUDE_SKIP_HOOKS"):
        return 0
    state = {"event": ""}
    rc = None
    try:
        run(sys.stdin.buffer.read().decode("utf-8", "replace"), state)
    except DenyError as denied:
        hook_input.emit_decision("deny", str(denied))
    except JqError as error:
        rc = error.rc
    except Exception:
        rc = 1
    if rc is None:
        return 0
    if state["event"] == "PostToolUse":
        return rc
    hook_input.emit_decision("ask",
                             f"[review-commit-gate] internal error (exit {rc}). Allow to run the command anyway.")
    return 0


if __name__ == "__main__":
    hook_input.run_gate(main)
