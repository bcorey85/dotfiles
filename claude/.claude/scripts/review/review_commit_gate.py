#!/usr/bin/env python3
"""A coder dispatch obligates /review before a commit.

  PostToolUse(Agent): a coder dispatch marks the session dirty.
  PreToolUse(Bash):   `git commit` while dirty is denied, with the reason telling the session to run /review and
                      commit after it converges; `review-gate-mark clean|dirty` records that state. `clean` is
                      denied unless this session's latest stored review-loop hand-back (handback.py) is converged
                      or deferred.

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
A command counts as a commit when, with line continuations removed, it matches `git commit` as text, or `git`, then
only global options (a known one that takes a value is followed by it, which may be quoted or a `$( )` or backtick
substitution), then `commit` appears in it, or when a simple command runs git (any word whose base name is `git`, so
`env git` or a path counts), with any global options, and then `commit`. A global option the hook does not know may
take a value, so `commit` anywhere after it counts. A command shlex cannot read counts when `git`, then only
option-like words with an optional value each, then `commit` appears in it.
The session stays dirty; a later commit that ships code is denied again.

State: ~/.claude/state/review-gate/<session>. Hook JSON in, one permissionDecision line out, exit 0. On an internal
error PreToolUse asks the user; PostToolUse stays silent.
"""
import json
import os
import posixpath
import re
import sys

_SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path[:0] = [_SCRIPT_DIR, os.path.join(os.path.dirname(_SCRIPT_DIR), "lib")]
import hook_input
import script_utils
from hook_input import EMPTY_INPUT, JqError, jq_field, prune_old_state_files
from shell_command import parse_simple_commands, redirection_writes_file, split_simple_commands

CODERS = ("coder", "coder-deep", "backend-coder", "backend-coder-deep", "frontend-coder", "frontend-coder-deep")
COMMIT = re.compile(r"\bgit[ \t\r\f\v]+commit\b")
LINE_CONTINUATION = re.compile(r"\\\r?\n")
# An option's value: a quoted string, a `$( )` or backtick substitution, or a plain word.
OPTION_VALUE = r"""(?:"[^"]*"|'[^']*'|\$\([^()]*\)|`[^`]*`|\S+)"""
# For a command shlex cannot read: git, then only option-like words with an optional value each, then commit.
UNREADABLE_GIT_THEN_COMMIT = re.compile(r"\bgit(?:[ \t]+-\S+(?:[ \t]+" + OPTION_VALUE + r")?)*[ \t]+commit\b")
MARK = re.compile(r"review-gate-mark[ \t\n\r\f\v]+(clean|dirty)")
GIT_TIMEOUT_SECONDS = 3
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
                             r"[ \t]+commit\b")
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


def on_post_tool_use(root, state_file):
    if jq_field(root, "tool_input", "subagent_type") in CODERS:
        with open(state_file, "w") as handle:
            handle.write("dirty\n")


def check_commit(command, root, state_file):
    """Deny a commit while the session is dirty, unless it ships only notes."""
    try:
        with open(state_file, "rb") as handle:
            current = handle.read().decode("utf-8", "replace").rstrip("\n")
    except OSError:
        return
    if current != "dirty":
        return
    if ships_only_notes(command, jq_field(root, "cwd")):
        return
    raise DenyError(
        "[review-commit-gate] Coder work from this session has no converged /review. Run /review on "
        "the coder work and commit after it converges. If the commit ships only Markdown files under "
        "the repo's top-level docs/ folder, run it as a plain `git commit` (with `git add` of single "
        "named files if needed) from the repo root in its own Bash call, with no `cd`, `env` or "
        "`git -C`, because the gate passes that form."
    )


def apply_mark(mark, session, state_file):
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
    with open(state_file, "w") as handle:
        handle.write(mark + "\n")


def on_pre_tool_use(root, session, state_file):
    """A commit command is checked and never also marks; any other command may mark."""
    command = jq_field(root, "tool_input", "command")
    if is_commit_command(command):
        check_commit(command, root, state_file)
        return
    marked = MARK.search(command)
    if marked:
        apply_mark(marked.group(1), session, state_file)


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
