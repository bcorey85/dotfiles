#!/usr/bin/env python3
"""PreToolUse hook on Bash: deny shell writes that bypass the Write/Edit hook pipeline.

  1. In-place editors (sed -i, perl -pi, awk -i inplace), any target except a file inside the session temp root
     (/tmp/claude-<uid>, symlinks and `..` resolved): those are throwaway, and a read-only agent has no Write/Edit.
  2. Redirection (>, >>) and tee onto a git-tracked file.
  3. Agent type `coder` (any coder variant, subagent or main session): a redirect or tee that creates a new file
     outside a temp dir, or whose target holds a `$` after `$TMPDIR` and `$HOME` are expanded, unless the command
     proves every value the variable can take (shell_variables: a bare assignment that surely ran before, or a `for`
     over literal words) and each resulting path is under a temp dir, symlinks resolved and a tracked file still
     denied; also any relative target after any `cd`, `pushd` or `popd`.
  4. An interpreter (python, pypy, node, tsx, ts-node, bun, deno, ruby, perl; also behind npx or pnpm exec) run whose
     inline code (`-c`, `-e`, `-p`, `--print`, `--eval`, `deno eval`) or untracked, not git-ignored script file opens
     a file for writing and names a git-tracked file (interpreter_writes holds the trace).
  5. Any agent: a relative target after a `cd`, `pushd` or `popd` whose folder is not a literal (`cd "$D"`, `popd`,
     `cd -`), because the gate cannot tell where the write lands.
Only a `>` outside quotes is a redirect (a `>` inside a double-quoted `$(...)` is code and is read as one), and the
body of a heredoc is not read as commands unless it feeds a shell interpreter (`bash <<EOF`); the `$(...)` and
backtick spans of an unquoted heredoc body are. A command that names a program running code the parser does not read
(a shell's `-c`, `eval`, `docker exec`, `ssh`; shell_command.CODE_RUNNERS) is also scanned as plain text for `>` and
tee targets, quotes ignored: those targets are checked only against git-tracked files.
A relative target resolves against the session cwd (`cwd` in the hook input) and, for rules 2 and 4, also against
each folder a literal `cd` or `pushd` in command position moved to before it, cumulatively; a tracked file under any
of them denies. A script (rule 4) run after such a cd that writes a relative path denies naming the last cd folder;
an absolute path in it resolves as written. A relative target after a `cd`, `pushd` or `popd` whose folder is not
a literal is denied (rule 5), and in a coder a relative target after any of them is denied (rule 3).
Every deny reads `[shell-write-gate] [<tag>] <message>`; shell_write_denial builds it and holds the tag list.
Escape for rules 1, 2, 4 and 5 in the main session: a trailing `#skip-shell-write-gate` comment. A subagent (agent_id in
the hook input) or a coder cannot use it. Fails closed on internal error and on input that does not parse; the
variable reader fails closed too: a variable it cannot prove is a deny.
"""
import json
import os
import re
import shlex
import sys
from collections import namedtuple

sys.path[:0] = [os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib")]
import hook_input
import script_utils
import shell_command
from code_text import SP, SPC, trim
from hook_input import (
    JqError,
    claude_temp_root,
    expand_env_names,
    is_under_session_temp_root,
    is_under_temp_dir,
    jq_get,
    jq_str,
)
from inplace_edit import file_operands, find_editor_word, has_unseen_files, is_inplace
from interpreter_writes import interpreter_written_target
from shell_statements import strip_comments, strip_heredocs
from shell_variables import ShellVariables
from shell_write_denial import (
    CODER_NEW_FILE,
    CODER_REL_TARGET_CD,
    CODER_UNRESOLVED_VAR,
    CODER_VAR_OUTSIDE_TEMP,
    DIRECTORY_CHANGE_HINT,
    INPLACE_EDIT,
    INPUT_PARSE_FAIL,
    INTERNAL_ERROR,
    REL_TARGET_UNREAD_CD,
    RESTORE_HINT,
    SCRIPT_WRITE,
    SCRIPT_WRITE_REL_CD,
    TRACKED_TARGET,
    DenyError,
    deny_text,
    tagged_message,
)
from shell_write_paths import is_git_tracked, is_stream_or_device, resolve_target

TARGET = r"[^ \t\r\f\v|&;<>()]+"
REDIRECT = re.compile(r">[>|&]?" + SPC + "*" + TARGET)
REDIRECT_PREFIX = re.compile(r"^>[>|&]?" + SPC + "*")
TEE = re.compile(r"(^|" + SPC + r")tee(" + SPC + r"+-[a-zA-Z-]+)*" + SPC + "+" + TARGET)
TEE_PREFIX = re.compile(r"^" + SPC + r"*tee(" + SPC + r"+-[a-zA-Z-]+)*" + SPC + "+")
PRECHECK = re.compile(r"(-[a-zA-Z]*i|inplace|>|tee)")
DIRECTORY_COMMANDS = ("cd", "pushd", "popd")
DIRECTORY_COMMAND_TEXT = re.compile(r"(^|[\s;&|(){`])(cd|pushd|popd)(\s|$|[;&|)])")
# The variables a redirect or tee target takes from the environment.
ENV_NAMES = ("TMPDIR", "HOME")

# The request of one hook event: the command, the session cwd, whether the agent is barred from the skip comment
# (a subagent or a coder), whether it is a coder, and the ShellVariables of the whole command (None until run builds
# it, and for a request that is no coder's).
HookRequest = namedtuple("HookRequest", "command cwd cannot_skip coder variables", defaults=(None,))
# A redirect or tee target: its word, the folders step_folders gives its step (the session cwd first), whether an
# earlier step moved to a folder that is not a literal, and the index of its step in the top-level command (None for
# text inside a `$(...)` span, whose values the reader does not prove).
WrittenTarget = namedtuple("WrittenTarget", "raw folders unread_change step")


def written_targets(core):
    """Raw target of each redirect and tee a step's command text writes. A `>` inside quotes is no redirect."""
    try:
        commands = shell_command.parse_piped_commands(core)
    except ValueError:
        return regex_written_targets(core, skip_quoted=True)
    targets = []
    for words, redirections, _piped in commands:
        targets += [target for operator, target in redirections
                    if shell_command.redirection_writes_file(operator, target)]
        words = shell_command.command_after_wrappers(words, peel_containers=False)
        if words and os.path.basename(words[0]) == "tee":
            targets += [arg for arg in words[1:] if not arg.startswith("-")]
    return targets


def regex_written_targets(core, skip_quoted):
    """written_targets for text the parser cannot read: the regexes, skipping matches inside quotes when skip_quoted."""
    def matches(pattern):
        return shell_command.unquoted_matches(pattern, core) if skip_quoted else list(pattern.finditer(core))

    targets = []
    for found in matches(REDIRECT):
        operator = REDIRECT_PREFIX.match(found.group(0)).group(0).rstrip(SP)
        target = REDIRECT_PREFIX.sub("", found.group(0))
        if shell_command.redirection_writes_file(operator, target):
            targets.append(target)
    targets += [TEE_PREFIX.sub("", found.group(0)) for found in matches(TEE)]
    return targets


def simple_command_texts(step):
    """The text of each simple command in a step, so a command inside a `( )` group or `$( )` is judged on its own.
    A step the parser cannot read is one text: the step without the `(` groups around it."""
    try:
        commands = shell_command.parse_simple_commands(step)
    except ValueError:
        core = trim(shell_command.step_parts(step)[0])
        return [core] if core else []
    texts = []
    for words, _redirections in commands:
        while words and words[0] in shell_command.GROUP_WORDS:
            words = words[1:]
        if words:
            texts.append(shlex.join(words))
    return texts


def directory_changes(step):
    """The folder word of each `cd`, `pushd` or `popd` the step runs, in order, once keywords (`then`, `do`, `!`) and
    wrappers (`command`, `builtin`) are dropped; None for a folder that is not a literal. A step the parser cannot
    read gives one None when the word stands in command position by a text match."""
    try:
        commands = shell_command.parse_piped_commands(step)
    except ValueError:
        return [None] if DIRECTORY_COMMAND_TEXT.search(step) else []
    folders = []
    for words, _redirections, _piped in commands:
        words = shell_command.command_after_wrappers(words)
        if words and words[0] in DIRECTORY_COMMANDS:
            expanded_words = [expand_env_names(word, ENV_NAMES) for word in words]
            folders.append(shell_command.cd_folder(expanded_words))
    return folders


def step_folders(code, cwd):
    """(step, folders, unread_change) for every step of the command text, in order. folders holds the session cwd,
    then each folder an earlier step, or the step itself, moved to with a literal `cd` or `pushd`, each resolved
    against the one before. unread_change is True once one moved to a folder that is not a literal."""
    steps = []
    folders = [cwd]
    unread_change = False
    for _operator, step in shell_command.split_command_steps(code):
        folders, unread_in_step = folders_after_step(folders, step)
        unread_change = unread_change or unread_in_step
        steps.append((step, folders, unread_change))
    return steps


def folders_after_step(folders, step):
    """folders extended by each literal folder the step moves to, and whether it moved to a folder that is not a
    literal."""
    unread_change = False
    for folder in directory_changes(step):
        if folder is None:
            unread_change = True
            continue
        folder_path = os.path.join(folders[-1], os.path.expanduser(folder))
        folders = [*folders, os.path.normpath(folder_path)]
    return folders, unread_change


def step_targets(code, cwd, in_span):
    """A WrittenTarget for every redirect and tee target of the command text, in order. in_span is True for the
    text of a `$(...)` or backtick span."""
    targets = []
    for index, (step, folders, unread_change) in enumerate(step_folders(code, cwd)):
        step_index = None if in_span else index
        for raw in written_targets(step):
            targets.append(WrittenTarget(raw, folders, unread_change, step_index))
    return targets


def code_texts(code):
    """The command text and the text of each `$(...)` and backtick span in it, at any depth: the shell runs the
    spans, also inside double quotes."""
    texts = [code]
    for text in texts:
        texts += shell_command.substitution_spans(text)
    return texts


def text_segments(text, cwd):
    """(simple command text, folders) for each simple command of the text, with the folders step_folders gives its
    step."""
    segments = []
    for step, folders, _unread in step_folders(text, cwd):
        for segment in simple_command_texts(step):
            segments.append((segment, folders))
    return segments


def read_request(raw):
    """The HookRequest in the hook input text, or None for a call with no command. Input that does not parse is a
    deny (fail closed)."""
    try:
        payload = json.loads(raw)
        command = jq_str(jq_get(payload, "tool_input", "command"))
    except (ValueError, JqError):
        raise DenyError(tagged_message(INPUT_PARSE_FAIL, "hook input did not parse — failing closed. "
                                                         "Report this to the user.")) from None
    agent = jq_str(jq_get(payload, "agent_type"))
    agent_id = jq_str(jq_get(payload, "agent_id"))
    coder = bool(script_utils.CODERS.match(agent))
    cwd = jq_str(jq_get(payload, "cwd")) or os.getcwd()
    if not command:
        return None
    return HookRequest(command, cwd, bool(agent_id) or coder, coder)


def run(raw):
    if raw.strip() == "":
        return
    request = read_request(raw)
    if request is None:
        return

    command = request.command
    code = strip_comments(strip_heredocs(command))
    texts = code_texts(code)
    request = request._replace(variables=ShellVariables(code) if request.coder else None)
    segment_folders = []
    targets = []
    text_targets = []
    for position, text in enumerate(texts):
        segment_folders += text_segments(text, request.cwd)
        targets += step_targets(text, request.cwd, in_span=position > 0)
        if shell_command.names_code_runner(text):
            text_targets += regex_written_targets(text, skip_quoted=False)

    if "#skip-shell-write-gate" in command and not request.cannot_skip:
        return

    written_paths = {resolve_target(target.raw, request.cwd) for target in targets} - {None}
    for segment, folders in segment_folders:
        check_script_writes(segment, folders, written_paths, request)

    if not PRECHECK.search(command):
        return

    for segment, folders in segment_folders:
        check_in_place_edit(segment, folders, request.cannot_skip)

    try:
        check_redirect_targets(targets, text_targets, request)
    except DenyError as denial:
        if not any(reads_file_from_revision(text) for text in texts):
            raise
        raise DenyError(f"{denial} {RESTORE_HINT}") from None


def check_redirect_targets(targets, text_targets, request):
    """Check each redirect and tee target: step_targets rows, then the targets of text read only by regex."""
    for target in targets:
        check_written_target(target, request)
    text_request = request._replace(coder=False, variables=None)
    for raw_target in text_targets:
        check_written_target(WrittenTarget(raw_target, [request.cwd], False, None), text_request)


def check_script_writes(segment, folders, written_paths, request):
    """Deny an interpreter step whose code writes a git-tracked file."""
    written = interpreter_written_target(segment, folders, written_paths, request.command)
    if written is None:
        return

    raw_target, target = written
    cannot_skip = request.cannot_skip
    if len(folders) > 1 and not shell_command.path_word_is_absolute(raw_target):
        raise DenyError(deny_text(SCRIPT_WRITE_REL_CD,
                                  "a script run after a cd to " + folders[-1] + " writes the relative path "
                                  + raw_target + ", which is git-tracked under the session cwd or a cd folder. "
                                  + DIRECTORY_CHANGE_HINT,
                                  cannot_skip))
    raise DenyError(deny_text(SCRIPT_WRITE,
                              "a script that writes " + target + " bypasses the Write/Edit hook pipeline. "
                              "Keep any scratch script in the scratchpad, never in the repo tree.",
                              cannot_skip))


def check_in_place_edit(segment, folders, cannot_skip):
    """Deny an in-place editor step unless every file it names is under the session temp root."""
    editor = find_editor_word(segment)
    if editor is None or not is_inplace(editor, segment):
        return
    operands = file_operands(segment, editor)
    resolved = [resolve_target(operand, folders[-1]) for operand in operands]
    all_scratch = all(path is not None and is_under_session_temp_root(path) for path in resolved)
    if operands and not has_unseen_files(operands) and all_scratch:
        return
    if operands:
        subject = "in-place editing of " + ", ".join(operands) + " bypasses the Write/Edit hook pipeline."
    else:
        subject = (f"in-place editing by {editor} found no file operand it can read, so the file it edits is "
                   "unknown, and it bypasses the Write/Edit hook pipeline.")
    # An agent with no Write or Edit can follow this; a tracked file gets no copy route.
    if not any(path is not None and is_git_tracked(path) for path in resolved):
        subject += f" An in-place edit of a scratch file under {claude_temp_root()} passes."
    raise DenyError(deny_text(INPLACE_EDIT, subject, cannot_skip))


def reads_file_from_revision(text):
    """True when a command in the text prints a file from a revision: `git show <rev>:<path>` or `git cat-file`.
    Text the parser cannot read is False, so the deny keeps its plain wording."""
    try:
        commands = shell_command.split_simple_commands(text)
    except ValueError:
        return False
    for words in commands:
        words = shell_command.command_after_wrappers(words)
        if not words or not shell_command.is_git_word(words[0]):
            continue
        _options, index = shell_command.git_options(words)
        subcommand = shell_command.git_subcommand(words)
        if subcommand == "cat-file":
            return True
        if subcommand == "show" and any(":" in word for word in words[index + 1:] if not word.startswith("-")):
            return True
    return False


def check_tracked_target(raw_target, folder, cannot_skip, after_directory_change):
    path = resolve_target(raw_target, folder)
    if path is None:
        return
    if os.path.islink(path):
        resolved = os.path.realpath(path)
        if resolved and os.path.exists(hook_input.bash_dirname(resolved)):
            path = resolved
    if not is_git_tracked(path):
        return

    subject = (path + " is git-tracked. Shell writes bypass the Write/Edit hook pipeline "
               "(comment/prose/budget gates).")
    if after_directory_change:
        subject += " " + DIRECTORY_CHANGE_HINT
    raise DenyError(deny_text(TRACKED_TARGET, subject, cannot_skip))


def env_expanded(target, request):
    """The target with `$TMPDIR` and `$HOME` replaced from the environment, except a name the command may set."""
    variables = request.variables
    assigned = variables.assigned_names if variables else frozenset()
    names = [name for name in ENV_NAMES if name not in assigned]
    return expand_env_names(target.raw, names)


def check_written_target(target, request):
    """Check one redirect or tee target. A coder's target that holds a variable is checked once for each value the
    command proves the variable can take, and each value must lie under a temp dir."""
    literals = proven_literals(target, request)
    if literals is None:
        check_literal_target(target, request)
        deny_option_like_new_file(env_expanded(target, request), target.folders[0], request)
        return
    for literal in literals:
        check_literal_target(target._replace(raw=literal), request)
        deny_option_like_new_file(literal, target.folders[0], request)
        check_under_temp(target, literal, request)


def proven_literals(target, request):
    """The literal texts a coder's target with a variable expands to, or None for a target with no variable left (or
    a request that is no coder's) and for one whose variable is not proven, which check_literal_target denies. A
    target inside a `$(...)` span has no step, so none of its variables is proven."""
    if not request.coder or request.variables is None or target.step is None:
        return None
    expanded = env_expanded(target, request)
    if "$" not in expanded:
        return None
    return request.variables.literal_values(expanded, target.step)


def check_under_temp(target, literal, request):
    """Deny a proven value that leaves every temp dir once resolved. is_under_temp_dir follows symlinks before it
    collapses `..`, so no text collapse of `..` may come first."""
    path = resolve_target(literal, target.folders[0])
    # No path: a stream, a /dev file, an empty word, or an option-like value that deny_option_like_new_file decides.
    if path is None or is_under_temp_dir(path):
        return
    raise DenyError(deny_text(CODER_VAR_OUTSIDE_TEMP,
                              f"{target.raw} expands to {path}, outside every temp dir, so this redirect or tee may "
                              "create a new file there. Write to an explicit path.", request.cannot_skip))


def deny_option_like_new_file(expanded, cwd, request):
    """Deny a coder's option-like target (`-foo`): resolve_target gives it no path, yet the shell creates a file of
    that name in the cwd. A stream (`&1`) or a /dev file is no file."""
    if not request.coder or resolve_target(expanded, cwd) is not None:
        return
    word = trim(expanded)
    if not word or is_stream_or_device(word):
        return
    raise DenyError(deny_text(CODER_NEW_FILE, cwd + "/" + word + " would be a new file created from the shell, "
                              "outside a temp dir. A new file bypasses the Write/Edit hook pipeline.", True))


def check_literal_target(target, request):
    """Deny a write to a git-tracked file, a relative target after a folder change the gate cannot read, and for a
    coder a relative target after any folder change or a new file outside a temp dir. folders holds the session cwd
    first, then each folder a literal `cd` or `pushd` moved to before the write."""
    cannot_skip = request.cannot_skip
    folders = target.folders
    raw_target = target.raw
    cwd = folders[0]
    expanded = env_expanded(target, request)
    relative = not shell_command.path_word_is_absolute(expanded)
    after_directory_change = relative and (target.unread_change or len(folders) > 1)

    for folder in folders if relative else [cwd]:
        check_tracked_target(expanded, folder, cannot_skip, after_directory_change)

    coder_path = resolve_target(expanded, cwd) if request.coder else None
    if coder_path is not None and "$" in coder_path:
        raise DenyError(deny_text(CODER_UNRESOLVED_VAR, raw_target + " is a redirect or tee target this gate cannot "
                                  "resolve, so it may create a new file outside a temp dir. Write to an explicit "
                                  "path.", True))
    if relative:
        if target.unread_change:
            raise DenyError(deny_text(REL_TARGET_UNREAD_CD, raw_target + " is a relative write target after a cd to "
                                      "a folder this gate cannot read. " + DIRECTORY_CHANGE_HINT, cannot_skip))
        if request.coder and after_directory_change:
            raise DenyError(deny_text(CODER_REL_TARGET_CD, raw_target + " is a relative write target after a cd. "
                                      + DIRECTORY_CHANGE_HINT, True))
    if coder_path is None:
        return
    if not os.path.exists(coder_path) and not is_under_temp_dir(coder_path):
        raise DenyError(deny_text(CODER_NEW_FILE, coder_path + " would be a new file created from the shell, outside "
                                  "a temp dir. A new file bypasses the Write/Edit hook pipeline.", True))


def main():
    if os.environ.get("CLAUDE_SKIP_HOOKS"):
        return 0
    internal = None
    try:
        run(sys.stdin.buffer.read().decode("utf-8", "replace"))
    except DenyError as denied:
        hook_input.emit_decision("deny", str(denied))
    except JqError as error:
        internal = error.rc
    except Exception:
        internal = 1
    if internal is not None:
        hook_input.emit_decision("deny", tagged_message(INTERNAL_ERROR, f"internal error (exit {internal}) — failing "
                                                                         "closed. Report this to the user."))
    return 0


if __name__ == "__main__":
    hook_input.run_gate(main)
