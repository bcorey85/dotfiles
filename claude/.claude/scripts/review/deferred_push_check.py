#!/usr/bin/env python3
"""PreToolUse hook on Bash: before `git push` or `gh pr create`, list the branch's deferred bug and correctness
findings.

A finding counts when review deferred it (actioned "deferred"), its class is bug or correctness, it was logged on this
repo and branch, the code around its line has not changed since the finding, and no fixed row at the same session,
file and line came from a later round (a later date, and a different iter when both rows have one). A row with no
session never matches. The hook adds the list to the model's context. It never denies, and it runs in the main session
and in subagents.

The code is unchanged when `git log -L` over the lines line-5..line+5 shows no commit after the base. The base is the
finding's own head commit when it was logged on committed code; for a finding on uncommitted code it is the first
commit at or after the finding's date that touches the file. A finding whose code was never committed, or whose lines
git cannot follow, is left out.

Heredoc bodies, quoted strings and comments are ignored. Any error, a missing findings file or a non-git cwd exits 0
with no output. CLAUDE_SKIP_HOOKS turns the hook off.
"""
import json
import os
import pathlib
import subprocess
import sys

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent / "lib"))
import script_utils
import shell_command
from shell_statements import statements

DEFAULT_FINDINGS_FILE = pathlib.Path.home() / ".claude" / "review-findings.jsonl"
LISTED_CLASSES = {"bug", "correctness"}
MAX_FINDINGS = 20
WINDOW = 5
GIT_TIMEOUT_SECONDS = 10
DESC_LIMIT = 160
FALSY_DIRTY = {"", "0", "false", "False"}

CLOSING_LINE = ("Before this push opens a PR, fix each one with /fix, or name it in your report as carried with its "
                "reason. This check never blocks.")


def is_trigger(command):
    for words in statements(command):
        if words[0] == "git" and shell_command.git_subcommand(words) == "push":
            return True
        if words[:3] == ["gh", "pr", "create"]:
            return True
    return False


def run_git(cwd, *args):
    # Returns (exit code, stdout); stderr is dropped.
    finished = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=GIT_TIMEOUT_SECONDS)
    return finished.returncode, finished.stdout


def read_rows(path):
    rows = []
    for text in pathlib.Path(path).read_text().splitlines():
        try:
            row = json.loads(text)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def is_listed_row(row, repo, branch):
    line = row.get("line")
    return (row.get("kind") == "finding" and row.get("actioned") == "deferred"
            and row.get("class") in LISTED_CLASSES and row.get("repo") == repo and row.get("branch") == branch
            and isinstance(row.get("file"), str) and bool(row["file"])
            and isinstance(line, int) and not isinstance(line, bool) and line >= 1)


def row_date(row):
    return str(row.get("date") or "")


def place(row):
    # The session, normalized file and line a finding row points at; None when the row has no usable place.
    line = row.get("line")
    file = row.get("file")
    if not isinstance(file, str) or not file or not isinstance(line, int) or isinstance(line, bool):
        return None
    session = row.get("session")
    if not session:
        return None
    return (session, os.path.normpath(file), line)


def review_iter(row):
    value = row.get("iter")
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def is_later_round(fixed_round, deferred_row):
    # fixed_round is an (iter, date) pair. The fix needs a strictly later date and, when both rows carry an iter, a
    # different one, so a different finding fixed in the same pass does not count. A later review run restarts its
    # iter at 1, so a smaller iter with a later date still counts.
    fixed_iter, fixed_date = fixed_round
    deferred_iter = review_iter(deferred_row)
    if fixed_iter is not None and fixed_iter == deferred_iter:
        return False

    deferred_date = row_date(deferred_row)
    return bool(deferred_date and fixed_date and fixed_date > deferred_date)


def fixed_rounds_by_place(rows, repo, branch):
    # Maps each place to the (iter, date) pairs of its fixed rows, so a later round's fix hides an earlier deferral.
    fixed = {}
    for row in rows:
        if (row.get("kind") != "finding" or row.get("actioned") != "fixed" or row.get("repo") != repo
                or row.get("branch") != branch):
            continue
        where = place(row)
        if where is None:
            continue
        fixed.setdefault(where, []).append((review_iter(row), row_date(row)))
    return fixed


def branch_findings(rows, repo, branch):
    # Newest first, one row per finding, at most MAX_FINDINGS. A finding fixed later at the same place is left out.
    chosen = []
    seen = set()
    fixed_rounds_of_place = fixed_rounds_by_place(rows, repo, branch)
    for row in sorted((row for row in rows if is_listed_row(row, repo, branch)),
                      key=row_date, reverse=True):
        fixed_rounds = fixed_rounds_of_place.get(place(row), [])
        if any(is_later_round(fixed_round, row) for fixed_round in fixed_rounds):
            continue
        key = row.get("finding_id") or (row["file"], row["line"], row.get("gate"))
        if key in seen:
            continue
        seen.add(key)
        chosen.append(row)
    return chosen[:MAX_FINDINGS]


def is_dirty(row):
    dirty = row.get("dirty")
    return not (dirty is None or dirty is False or dirty == 0 or dirty in FALSY_DIRTY)


def base_commit(cwd, row):
    head = row.get("head")
    if not is_dirty(row) and isinstance(head, str) and head:
        code, _ = run_git(cwd, "cat-file", "-e", head + "^{commit}")
        if code == 0:
            return head
    date = row.get("date")
    if not isinstance(date, str) or not date:
        return None
    code, out = run_git(cwd, "rev-list", "--reverse", "--since=" + date, "HEAD", "--", row["file"])
    landed = out.split()
    if code != 0 or not landed:
        return None
    return landed[0]


def code_unchanged(cwd, row):
    base = base_commit(cwd, row)
    if base is None:
        return False
    code, tip = run_git(cwd, "rev-parse", "HEAD")
    if code == 0 and tip.strip() == base:
        # git log -L refuses an empty range, and nothing came after the base
        return True
    line = row["line"]
    span = f"{base}..HEAD"
    window_range = f"{max(1, line - WINDOW)},{line + WINDOW}:{row['file']}"
    code, out = run_git(cwd, "log", "--format=%H", "-L", window_range, span)
    if code != 0:
        # git refuses a range past the end of the file; retry the one line before giving up
        line_range = f"{line},{line}:{row['file']}"
        code, out = run_git(cwd, "log", "--format=%H", "-L", line_range, span)
        if code != 0:
            return False
    return not out.strip()


def finding_line(row):
    desc = " ".join(str(row.get("desc") or "").split())[:DESC_LIMIT]
    return f"- {row['file']}:{row['line']} [{row.get('gate')}, {row.get('class')}] {desc}".rstrip()


def context_text(rows):
    header = (f"{len(rows)} deferred bug or correctness findings on this branch: "
              "their code has not changed since review.")
    return "\n".join([header, *map(finding_line, rows), CLOSING_LINE])


def main():
    try:
        if os.environ.get("CLAUDE_SKIP_HOOKS"):
            sys.exit(0)
        payload = json.loads(sys.stdin.read())
        command = (payload.get("tool_input") or {}).get("command")
        if not isinstance(command, str) or not is_trigger(command):
            sys.exit(0)
        cwd = payload.get("cwd") or os.getcwd()
        branch = script_utils.current_branch(cwd, timeout=GIT_TIMEOUT_SECONDS)
        if not branch:
            sys.exit(0)
        findings_file = os.environ.get("REVIEW_FINDINGS_FILE") or DEFAULT_FINDINGS_FILE
        candidates = branch_findings(read_rows(findings_file), script_utils.repo_name(cwd), branch)
        unchanged = [row for row in candidates if code_unchanged(cwd, row)]
        if unchanged:
            sys.stdout.write(json.dumps({"hookSpecificOutput": {
                "hookEventName": "PreToolUse", "additionalContext": context_text(unchanged)}}))
    except Exception:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
