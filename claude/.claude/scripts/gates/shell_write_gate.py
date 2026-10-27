#!/usr/bin/env python3
"""PreToolUse hook on Bash: deny shell writes that bypass the Write/Edit hook pipeline.

  1. In-place editors (sed -i, perl -pi, awk -i inplace), any target.
  2. Redirection (>, >>) and tee onto a git-tracked file.
  3. Agent type `coder` (any coder variant, subagent or main session): a redirect or tee that creates a new file
     outside a temp dir, or whose target still holds a `$` after `$TMPDIR` and `$HOME` are expanded.
Only a `>` outside quotes is a redirect (a `>` inside a double-quoted `$(...)` is code and is read as one), and the
body of a heredoc is not read as commands unless it feeds a shell interpreter (`bash <<EOF`); the `$(...)` and
backtick spans of an unquoted heredoc body are. A command that names a program running code the parser does not read
(a shell's `-c`, `eval`, `docker exec`, `ssh`; shell_command.CODE_RUNNERS) is also scanned as plain text for `>` and
tee targets, quotes ignored: those targets are checked only against git-tracked files.
A relative target resolves against the session cwd (`cwd` in the hook input); `cd` is not followed. The one
exception is rule 3: once a `cd`, `pushd` or `popd` has run in command position before a relative target, rule 3 is
skipped for that target, because the gate cannot know the directory. Rule 2 still checks it against the session cwd.
Escape for rules 1-2 in the main session: a trailing `#skip-shell-write-gate` comment. A subagent (agent_id in the
hook input) or a coder cannot use it. Fails closed on internal error.
"""
import json
import os
import re
import shlex
import subprocess
import sys

sys.path[:0] = [os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib")]
import hook_input
import script_utils
import shell_command
from hook_input import JqError, expand_env_names, is_under_temp_dir, jq_get, jq_str
from hook_input import bash_basename as shell_basename
from hook_input import bash_dirname as shell_dirname
from shell_statements import SKIP_WORDS, strip_comments, strip_heredocs

SP =" \t\n\r\f\v"
SPC = r"[ \t\r\f\v]"
TARGET = r"[^ \t\r\f\v|&;<>()]+"
REDIRECT = re.compile(r">[>|&]?" + SPC + "*" + TARGET)
REDIRECT_PREFIX = re.compile(r"^>[>|&]?" + SPC + "*")
TEE = re.compile(r"(^|" + SPC + r")tee(" + SPC + r"+-[a-zA-Z-]+)*" + SPC + "+" + TARGET)
TEE_PREFIX = re.compile(r"^" + SPC + r"*tee(" + SPC + r"+-[a-zA-Z-]+)*" + SPC + "+")
GIT_SUBCOMMANDS = re.compile(r"(rm|mv|checkout|restore|apply)")
SED_INPLACE = re.compile(r"(^|" + SPC + r")(-[a-zA-Z]*i|--in-place(" + SPC + r"|=|$))")
PERL_I = re.compile(r"(^|" + SPC + r")-[a-zA-Z]*i")
PERL_PN = re.compile(r"(^|" + SPC + r")-[a-zA-Z]*[pn]")
AWK_INPLACE = re.compile(r"(^|" + SPC + r")-i" + SPC + "*inplace")
PRECHECK = re.compile(r"(-[a-zA-Z]*i|inplace|>|tee)")
DIRECTORY_COMMANDS = ("cd", "pushd", "popd")
DIRECTORY_COMMAND_TEXT = re.compile(r"(^|[\s;&|(){`])(cd|pushd|popd)(\s|$|[;&|)])")
ESCAPE_HINT = (" If this deny is wrong (for example a command wrapper this gate does not recognize), re-run the "
               "command with a trailing #skip-shell-write-gate comment — it disarms this gate for that one command.")


class DenyError(Exception):
    pass


def words_of(text):
    return [w for w in re.split("[ \t\n]+", text) if w]


def trim(text):
    return text.strip(SP)


def is_inplace(program, segment):
    if program in ("sed", "gsed"):
        return bool(SED_INPLACE.search(segment))
    if program == "perl":
        return bool(PERL_I.search(segment)) and bool(PERL_PN.search(segment))
    if program in ("awk", "gawk"):
        return bool(AWK_INPLACE.search(segment))
    return False


def find_editor_word(segment):
    # The in-place editor a step runs: its command word once the wrappers are dropped, or an editor named after an
    # invoker (`xargs sed -i`, `find -exec sed -i`, `sh -c`).
    # A docker, podman, kubectl or ssh call runs its editor elsewhere: its wrapper words are not peeled.
    command_words = shell_command.command_after_wrappers(words_of(segment), peel_containers=False)
    invoked = False
    for index, word in enumerate(command_words):
        base = word.rsplit("/", 1)[-1]
        if base in ("sed", "gsed", "perl", "awk", "gawk"):
            if index == 0 or invoked:
                return base
        elif base in ("xargs", "-exec", "-execdir", "sh", "bash", "zsh", "-c", "parallel"):
            invoked = True
    return None


def resolve_target(raw, cwd):
    path = shell_command.path_word(trim(raw))
    if not path or path.startswith("-") or path.startswith("&") or path.startswith("/dev/"):
        return None
    if not path.startswith("/"):
        path = cwd + "/" + path
    return path


def path_word_is_absolute(raw):
    return shell_command.path_word(trim(raw)).startswith("/")


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


def deny_text(subject, cannot_skip):
    if cannot_skip:
        return (f"[shell-write-gate] {subject} Use the Edit tool for an in-place change, or the Write tool for a new "
                "file. This agent has no way to skip this gate.")
    return f"[shell-write-gate] {subject} Use the Write or Edit tool." + ESCAPE_HINT


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


def runs_directory_change(step):
    """True when a command of the step is `cd`, `pushd` or `popd`, once keywords (`then`, `do`, `!`) and wrappers
    (`command`, `builtin`) are dropped. A step the parser cannot read counts when the word stands in command
    position by a text match."""
    try:
        commands = shell_command.parse_piped_commands(step)
    except ValueError:
        return bool(DIRECTORY_COMMAND_TEXT.search(step))
    for words, _redirections, _piped in commands:
        while words and words[0] in SKIP_WORDS:
            words = words[1:]
        words = shell_command.command_after_wrappers(words)
        if words and words[0] in DIRECTORY_COMMANDS:
            return True
    return False


def step_targets(code):
    """(raw target, after_directory_change) for every redirect and tee target of the command text, in order.
    after_directory_change is True once an earlier step, or the step itself, runs a `cd`, `pushd` or `popd`."""
    targets = []
    after_directory_change = False
    for _operator, step in shell_command.split_command_steps(code):
        after_directory_change = after_directory_change or runs_directory_change(step)
        targets += [(raw, after_directory_change) for raw in written_targets(step)]
    return targets


def code_texts(code):
    """The command text and the text of each `$(...)` and backtick span in it, at any depth: the shell runs the
    spans, also inside double quotes."""
    texts = [code]
    for text in texts:
        texts += shell_command.substitution_spans(text)
    return texts


def is_git_tracked(path):
    try:
        finished = subprocess.run(["git", "-C", shell_dirname(path), "ls-files", "--error-unmatch", "--",
                                   shell_basename(path)],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        return False
    return finished.returncode == 0


def run(raw):
    if raw.strip() == "":
        return
    try:
        payload = json.loads(raw)
        command = jq_str(jq_get(payload, "tool_input", "command"))
    except (ValueError, JqError):
        raise DenyError(
            "[shell-write-gate] hook input did not parse — failing closed. Report this to the user."
        ) from None
    agent = jq_str(jq_get(payload, "agent_type"))
    subagent = bool(jq_str(jq_get(payload, "agent_id")))
    coder = bool(script_utils.CODERS.match(agent))
    cwd = jq_str(jq_get(payload, "cwd")) or os.getcwd()
    if not command:
        return

    code = strip_comments(strip_heredocs(command))
    texts = code_texts(code)
    segments = [segment for text in texts
                for _operator, step in shell_command.split_command_steps(text)
                for segment in simple_command_texts(step)]
    targets = [target for text in texts for target in step_targets(text)]
    text_targets = [target for text in texts if shell_command.names_code_runner(text)
                    for target in regex_written_targets(text, skip_quoted=False)]

    cannot_skip = subagent or coder
    if "#skip-shell-write-gate" in command and not cannot_skip:
        return
    if not PRECHECK.search(command):
        return

    for segment in segments:
        word = find_editor_word(segment)
        if word is None or not is_inplace(word, segment):
            continue
        target = in_place_target(segment, word)
        raise DenyError(deny_text("in-place editing of " + target + " bypasses the Write/Edit hook pipeline.",
                                  cannot_skip))

    for raw_target, after_directory_change in targets:
        check_written_target(raw_target, cwd, cannot_skip, coder, after_directory_change)

    for raw_target in text_targets:
        check_written_target(raw_target, cwd, cannot_skip, False, False)


def in_place_target(segment, editor):
    """The file an in-place editor step names: its last word once redirections are dropped, or the whole segment
    when that word is an option or the editor itself."""
    try:
        commands = [words for words, _redirections in shell_command.parse_simple_commands(segment) if words]
    except ValueError:
        commands = [words_of(segment)]
    words = commands[-1] if commands else []
    target = words[-1] if words else ""
    if not target or target.startswith("-") or target == editor:
        return segment
    return target


def check_written_target(raw_target, cwd, cannot_skip, coder, after_directory_change):
    path = resolve_target(raw_target, cwd)
    if path is None:
        return
    if os.path.islink(path):
        resolved = os.path.realpath(path)
        if resolved and os.path.exists(shell_dirname(resolved)):
            path = resolved
    if is_git_tracked(path):
        raise DenyError(deny_text(path + " is git-tracked. Shell writes bypass the Write/Edit hook pipeline "
                                  "(comment/prose/budget gates).", cannot_skip))
    if not coder:
        return
    expanded = expand_env_names(raw_target, ("TMPDIR", "HOME"))
    coder_path = resolve_target(expanded, cwd)
    if coder_path is None:
        return
    relative = not path_word_is_absolute(expanded)
    if after_directory_change and relative and "$" not in coder_path:
        return
    if "$" in coder_path:
        raise DenyError(deny_text(raw_target + " is a redirect or tee target this gate cannot resolve, so it may "
                                  "create a new file outside a temp dir. Write to an explicit path.", True))
    if not os.path.exists(coder_path) and not is_under_temp_dir(coder_path):
        raise DenyError(deny_text(coder_path + " would be a new file created from the shell, outside a temp dir. "
                                  "A new file bypasses the Write/Edit hook pipeline.", True))


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
        hook_input.emit_decision("deny", f"[shell-write-gate] internal error (exit {internal}) — failing closed. "
                                         "Report this to the user.")
    return 0


if __name__ == "__main__":
    hook_input.run_gate(main)
