#!/usr/bin/env python3
"""PreToolUse hook on Bash: deny shell writes that bypass the Write/Edit hook pipeline.

  0. Test ownership (any agent_type): every path a command writes, moves, copies or deletes goes through
     test-ownership-gate.sh beside this file, when that file exists. Not escapable.
  1. In-place editors (sed -i, perl -pi, awk -i inplace), any target.
  2. Redirection (>, >>) and tee onto a git-tracked file.
Escape for rules 1-2: a trailing `#skip-shell-write-gate` comment. Fails closed on internal error.
"""
import json
import os
import re
import subprocess
import sys

sys.path[:0] = [os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib")]
import hook_input
from hook_input import JqError, jq_get, jq_str, split_segments
from hook_input import bash_basename as shell_basename
from hook_input import bash_dirname as shell_dirname

SP =" \t\n\r\f\v"
SPC = r"[ \t\r\f\v]"
TARGET = r"[^ \t\r\f\v|&;<>()]+"
REDIRECT = re.compile(r">>?" + SPC + "*" + TARGET)
REDIRECT_PREFIX = re.compile(r"^>>?" + SPC + "*")
TEE = re.compile(r"(^|" + SPC + r")tee(" + SPC + r"+-[a-zA-Z-]+)*" + SPC + "+" + TARGET)
TEE_PREFIX = re.compile(r"^" + SPC + r"*tee(" + SPC + r"+-[a-zA-Z-]+)*" + SPC + "+")
CMD_WRAPPER = re.compile(r"(time|env|[^\W\d]\w*=.*)")
GIT_SUBCOMMANDS = re.compile(r"(rm|mv|checkout|restore|apply)")
SED_INPLACE = re.compile(r"(^|" + SPC + r")(-[a-zA-Z]*i|--in-place(" + SPC + r"|=|$))")
PERL_I = re.compile(r"(^|" + SPC + r")-[a-zA-Z]*i")
PERL_PN = re.compile(r"(^|" + SPC + r")-[a-zA-Z]*[pn]")
AWK_INPLACE = re.compile(r"(^|" + SPC + r")-i" + SPC + "*inplace")
PRECHECK = re.compile(r"(-[a-zA-Z]*i|inplace|>|tee)")
ESCAPE_HINT = (" If this deny is wrong (a > inside a quoted string or heredoc, an unrecognized wrapper), re-run the "
               "command with a trailing #skip-shell-write-gate comment — it disarms this gate for that one command.")


class DenyError(Exception):
    pass


def words_of(text):
    return [w for w in re.split("[ \t\n]+", text) if w]


def trim(text):
    return text.strip(SP)


def strip_target_quotes(text):
    if text.endswith('"'):
        text = text[:-1]
    if text.startswith('"'):
        text = text[1:]
    if text.endswith("'"):
        text = text[:-1]
    if text.startswith("'"):
        text = text[1:]
    return text


def is_inplace(program, segment):
    if program in ("sed", "gsed"):
        return bool(SED_INPLACE.search(segment))
    if program == "perl":
        return bool(PERL_I.search(segment)) and bool(PERL_PN.search(segment))
    if program in ("awk", "gawk"):
        return bool(AWK_INPLACE.search(segment))
    return False


def cmd_word_index(words):
    index = 0
    while index < len(words) and CMD_WRAPPER.fullmatch(words[index]):
        index += 1
    return index


def find_editor_word(segment):
    words = words_of(segment)
    command_index = cmd_word_index(words)
    invoked = False
    for index, word in enumerate(words):
        base = word.rsplit("/", 1)[-1]
        if base in ("sed", "gsed", "perl", "awk", "gawk"):
            if index == command_index or invoked:
                return base
        elif base in ("xargs", "-exec", "-execdir", "sh", "bash", "zsh", "-c", "sudo", "nice", "timeout",
                      "parallel"):
            invoked = True
    return None


def resolve_target(raw, cwd):
    path = strip_target_quotes(trim(raw))
    if not path or path.startswith("-") or path.startswith("&") or path.startswith("/dev/"):
        return None
    if path.startswith("~"):
        path = os.environ["HOME"] + path[1:]
    if not path.startswith("/"):
        path = cwd + "/" + path
    return path


def redirect_targets(command):
    redirects = []
    tees = []
    for line in command.split("\n"):
        for found in REDIRECT.finditer(line):
            redirects.append(REDIRECT_PREFIX.sub("", found.group(0)))
        for found in TEE.finditer(line):
            tees.append(TEE_PREFIX.sub("", found.group(0)))
    return redirects + tees


def check_ownership(raw, cwd, agent, ownership_gate):
    path = resolve_target(raw, cwd)
    if path is None:
        return
    for target in (path, path[:-1] + "/" if path.endswith("/") else path + "/"):
        payload = json.dumps({"agent_type": agent, "tool_input": {"file_path": target}},
                             ensure_ascii=False, separators=(",", ":"))
        finished = subprocess.run(["bash", ownership_gate], input=payload.encode("utf-8"),
                                  stdout=subprocess.PIPE)
        if finished.returncode != 0:
            raise JqError(finished.returncode)
        out = finished.stdout.decode("utf-8", "replace").rstrip("\n")
        if out:
            try:
                reason = jq_get(json.loads(out), "hookSpecificOutput", "permissionDecisionReason")
            except ValueError:
                raise JqError(2) from None
            text = "null" if reason is None else (reason if isinstance(reason, str) else json.dumps(reason))
            raise DenyError("[shell-write-gate] " + text.rstrip("\n"))


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
    cwd = jq_str(jq_get(payload, "cwd")) or os.getcwd()
    if not command:
        return

    segments = split_segments(command)
    targets = redirect_targets(command)
    ownership_gate = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test-ownership-gate.sh")

    if agent and os.path.isfile(ownership_gate):
        for target in targets:
            check_ownership(target, cwd, agent, ownership_gate)

        for segment in segments:
            words = words_of(segment)
            if not words:
                continue
            index = cmd_word_index(words)
            word = words[index].rsplit("/", 1)[-1] if index < len(words) else ""
            editor_word = find_editor_word(segment)
            if word in ("sed", "gsed", "perl", "awk", "gawk"):
                if not is_inplace(word, segment):
                    continue
            elif word in ("rm", "unlink", "mv", "cp", "install", "truncate", "touch", "ln", "dd", "patch"):
                pass
            elif word == "git":
                sub = words[index + 1] if index + 1 < len(words) else ""
                if not GIT_SUBCOMMANDS.fullmatch(sub):
                    continue
                index += 1
            else:
                if not (editor_word and is_inplace(editor_word, segment)):
                    continue
            for arg in words[index + 1:]:
                if word == "dd" and arg.startswith("of="):
                    arg = arg[3:]
                check_ownership(arg, cwd, agent, ownership_gate)

    if "#skip-shell-write-gate" in command:
        return
    if not PRECHECK.search(command):
        return

    for segment in segments:
        segment = trim(segment)
        if not segment:
            continue
        word = find_editor_word(segment)
        if word is None or not is_inplace(word, segment):
            continue
        target = re.split("[" + SP + "]", segment)[-1]
        if (not target or target.startswith("-") or "'" in target or '"' in target or target == word):
            target = segment
        raise DenyError("[shell-write-gate] in-place editing of " + target + " bypasses the Write/Edit hook pipeline. "
                   "Use the Write or Edit tool." + ESCAPE_HINT)

    for raw_target in targets:
        path = resolve_target(raw_target, cwd)
        if path is None:
            continue
        if os.path.islink(path):
            resolved = os.path.realpath(path)
            if resolved and os.path.exists(shell_dirname(resolved)):
                path = resolved
        if is_git_tracked(path):
            raise DenyError("[shell-write-gate] " + path + " is git-tracked. Shell writes bypass the Write/Edit hook "
                       "pipeline (comment/prose/budget gates). Use the Write or Edit tool." + ESCAPE_HINT)


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
