#!/usr/bin/env python3
"""A coder dispatch obligates /review before a commit.

  PostToolUse(Agent): a coder dispatch marks the session dirty.
  PreToolUse(Bash):   `git commit` while dirty asks the user to confirm; `review-gate-mark clean|dirty` records
                      that state. `clean` is denied unless this session's latest stored review-loop hand-back
                      (handback.py) is converged or deferred.

State: ~/.claude/state/review-gate/<session>. Hook JSON in, one permissionDecision line out, exit 0. On an internal
error PreToolUse asks; PostToolUse stays silent.
"""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hook_input
from hook_input import JqError, jq_get, jq_str, truthy

CODERS = ("coder", "coder-deep", "backend-coder", "backend-coder-deep", "frontend-coder", "frontend-coder-deep")
COMMIT = re.compile(r"\bgit[ \t\r\f\v]+commit\b")
MARK = re.compile(r"review-gate-mark[ \t\n\r\f\v]+(clean|dirty)")


class Ask(Exception):
    pass


class Deny(Exception):
    pass


EMPTY = object()


def field(root, *keys, **options):
    """jq -r '.a.b // default'. Only a missing, null or false value takes the default; an empty string stays empty."""
    if root is EMPTY:
        return ""
    value = jq_get(root, *keys)
    if "default" in options and not truthy(value):
        return options["default"]
    return jq_str(value)


def emit_ask(reason):
    hook_input.emit_decision("ask", reason)


def prune_old(state_dir):
    """find state_dir -type f -mtime +2 -delete"""
    now = time.time()
    for current, _dirs, files in os.walk(state_dir):
        for name in files:
            path = os.path.join(current, name)
            try:
                info = os.lstat(path)
                if os.path.isfile(path) and not os.path.islink(path) and int((now - info.st_mtime) / 86400) > 2:
                    os.unlink(path)
            except OSError:
                pass


def run(raw, state):
    if raw.strip() == "":
        root = EMPTY
    else:
        try:
            root = json.loads(raw)
        except ValueError:
            raise JqError(2)
    event = field(root, "hook_event_name")
    state["event"] = event
    session = field(root, "session_id", default="unknown")

    state_dir = os.environ["HOME"] + "/.claude/state/review-gate"
    try:
        os.makedirs(state_dir, exist_ok=True)
    except OSError:
        report_mkdir_failure(state_dir)
        raise JqError(1)
    state_file = state_dir + "/" + session
    prune_old(state_dir)

    if event == "PostToolUse":
        if field(root, "tool_input", "subagent_type") in CODERS:
            with open(state_file, "w") as handle:
                handle.write("dirty\n")
    elif event == "PreToolUse":
        command = field(root, "tool_input", "command")
        if COMMIT.search(command):
            try:
                with open(state_file, "rb") as handle:
                    current = handle.read().decode("utf-8", "replace").rstrip("\n")
            except OSError:
                return
            if current != "dirty":
                return
            raise Ask("[review-commit-gate] Coder work from this session has no converged /review. Allow to "
                      "commit anyway, or deny and run /review.")
        marked = MARK.search(command)
        if marked:
            reason = None
            if marked.group(1) == "clean":
                # Imported here, not at load: a missing module is an internal error on a `clean` mark only, and the
                # commit check and the dirty mark keep working.
                import handback
                reason = handback.false_clean_reason(session)
            if reason:
                raise Deny("[review-commit-gate] Gate not marked clean: %s. Only a converged or deferred review "
                           "hand-back from this session allows clean." % reason)
            with open(state_file, "w") as handle:
                handle.write(marked.group(1) + "\n")


def report_mkdir_failure(state_dir):
    """`mkdir -p` names the first path component it cannot create; GNU quotes it with curly quotes in UTF-8 locales."""
    # Python itself sets LC_CTYPE=C.UTF-8 at start-up when the locale is C (PEP 538); that value says nothing.
    ctype = os.environ.get("LC_CTYPE", "")
    ctype = "" if ctype == "C.UTF-8" else ctype
    locale = os.environ.get("LC_ALL") or ctype or os.environ.get("LANG") or ""
    left, right = ("\u2018", "\u2019") if "utf-8" in locale.lower().replace("utf8", "utf-8") else ("'", "'")
    walked = ""
    for piece in state_dir.split("/"):
        walked = walked + "/" + piece if walked or state_dir.startswith("/") else piece
        walked = walked.replace("//", "/")
        if not piece:
            continue
        if os.path.lexists(walked):
            if os.path.isdir(walked):
                continue
            reason = "File exists" if walked == state_dir else "Not a directory"
            hook_input.emit_stderr("mkdir: cannot create directory %s%s%s: %s\n" % (left, walked, right, reason))
            return
        try:
            os.mkdir(walked)
        except OSError as error:
            hook_input.emit_stderr("mkdir: cannot create directory %s%s%s: %s\n"
                                   % (left, walked, right, os.strerror(error.errno or 0)))
            return


def main():
    if os.environ.get("CLAUDE_SKIP_HOOKS"):
        return 0
    state = {"event": ""}
    rc = None
    try:
        run(sys.stdin.buffer.read().decode("utf-8", "replace"), state)
    except Ask as asked:
        emit_ask(str(asked))
    except Deny as denied:
        hook_input.emit_decision("deny", str(denied))
    except JqError as error:
        rc = error.rc
    except Exception:
        rc = 1
    if rc is None:
        return 0
    if state["event"] == "PostToolUse":
        return rc
    emit_ask("[review-commit-gate] internal error (exit %d). Allow to run the command anyway." % rc)
    return 0


if __name__ == "__main__":
    hook_input.run_gate(main)
