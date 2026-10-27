#!/usr/bin/env python3
"""PreToolUse hook on Bash: before `git push` or `gh pr create`, list the branch's deferred bug and correctness
findings.

A finding counts when review deferred it (actioned "deferred"), its class is bug or correctness, it was logged on this
repo and branch, it is on a file the branch changes, and the code around its line has not changed since the finding.
The hook adds the list to the model's context. It never denies, and it runs in the main session and in subagents.

The code is unchanged when `git log -L` over the lines line-5..line+5 shows no commit after the base. The base is the
finding's own head commit when it was logged on committed code; for a finding on uncommitted code it is the first
commit at or after the finding's date that touches the file. A finding whose code was never committed, or whose lines
git cannot follow, is left out.

The findings are the ledger's v_review_finding rows. The ledger keeps a file as a keyed hash and stores no description,
so the hook maps each row's path_key back to a file by keying the files the branch changes (committed since it left
the default branch, plus uncommitted), drops a row that matches none, and lists `file:line (class)` only.

Heredoc bodies, quoted strings and comments are ignored. Any error, a missing, busy or unreadable ledger or a
non-git cwd exits 0 with no output. The hook runs one `ledger query --max-time 2` (killed after 5 s) with no cache
refresh and no retry; the `ledger repo` and `ledger key` calls each have their own timeout. CLAUDE_SKIP_HOOKS turns
the hook off.
"""
import json
import os
import pathlib
import subprocess
import sys

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent / "lib"))
import script_utils
from shell_statements import statements

LISTED_CLASSES = {"bug", "correctness"}
MAX_FINDINGS = 20
WINDOW = 5
GIT_TIMEOUT_SECONDS = 10
LEDGER_QUERY_MAX_SECONDS = 2
LEDGER_CALL_SECONDS = 5
BRANCH_BASE = SCRIPT_DIR.parent / "tools" / "branch-base"
DEFAULT_BRANCH_REFS = ("origin/main", "origin/master", "main", "master")
GIT_OPTIONS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}
FALSY_DIRTY = {"", "0", "false", "False"}

CLOSING_LINE = ("Before this push opens a PR, fix each one with /fix, or name it in your report as carried with its "
                "reason. This check never blocks.")


def git_subcommand(words):
    # Returns the git subcommand, skipping global options such as `-C dir`; None when words are not a git call.
    if not words or words[0] != "git":
        return None, []
    index = 1
    while index < len(words) and words[index].startswith("-"):
        index += 2 if words[index] in GIT_OPTIONS_WITH_VALUE else 1
    if index >= len(words):
        return None, []
    return words[index], words[index + 1:]


def is_trigger(command):
    for words in statements(command):
        subcommand, _ = git_subcommand(words)
        if subcommand == "push":
            return True
        if words[:3] == ["gh", "pr", "create"]:
            return True
    return False


def run_git(cwd, *args):
    # Returns (exit code, stdout); stderr is dropped.
    finished = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=GIT_TIMEOUT_SECONDS)
    return finished.returncode, finished.stdout


def branch_base_ref(cwd):
    # The base ref tools/branch-base picks (on the default branch itself, its upstream); None when it finds none.
    try:
        finished = subprocess.run([str(BRANCH_BASE)], cwd=cwd, capture_output=True, text=True,
                                  timeout=GIT_TIMEOUT_SECONDS)
    except (OSError, subprocess.SubprocessError):
        return None
    words = finished.stdout.split()
    if finished.returncode != 0 or not words:
        return None
    return words[0]


def branch_changed_files(cwd):
    # The files the branch changes: committed since it left the default branch, plus uncommitted ones.
    names = set()
    base_ref = branch_base_ref(cwd)
    candidate_refs = DEFAULT_BRANCH_REFS if base_ref is None else (base_ref, *DEFAULT_BRANCH_REFS)
    for ref in candidate_refs:
        code, out = run_git(cwd, "diff", "--name-only", ref + "...HEAD")
        if code == 0:
            names.update(out.splitlines())
            break
    code, out = run_git(cwd, "diff", "--name-only", "HEAD")
    if code == 0:
        names.update(out.splitlines())
    return sorted(name for name in names if name)


def finding_query(repo, branch_key):
    quoted_repo = repo.replace("'", "''")
    quoted_branch_key = branch_key.replace("'", "''")
    classes = ", ".join(f"'{name}'" for name in sorted(LISTED_CLASSES))
    return ("SELECT finding_id, gate, class, path_key, line, head, dirty, found_ts AS date "
            f"FROM v_review_finding WHERE actioned = 'deferred' AND class IN ({classes}) "
            f"AND repo = '{quoted_repo}' AND branch_key = '{quoted_branch_key}'")


def ledger_findings(cwd, repo, branch):
    # The branch's deferred bug and correctness rows, each with the `file` its path_key maps back to.
    branch_key = script_utils.ledger_keys("branch", [branch], timeout_seconds=LEDGER_CALL_SECONDS)[0]
    if not branch_key:
        return []
    files = branch_changed_files(cwd)
    path_keys = script_utils.ledger_keys("path", files, cwd=cwd, timeout_seconds=LEDGER_CALL_SECONDS)
    file_by_path_key = {path_key: name for name, path_key in zip(files, path_keys, strict=True) if path_key}
    rows = []
    # One query with no cache refresh and no retry: a push is never held up for a busy ledger.
    for row in script_utils.query_ledger_rows_once(finding_query(repo, branch_key), LEDGER_QUERY_MAX_SECONDS,
                                                   LEDGER_CALL_SECONDS):
        row["file"] = file_by_path_key.get(row.get("path_key"))
        row["line"] = int(row["line"]) if (row.get("line") or "").isdigit() else None
        rows.append(row)
    return rows


def is_listed_row(row):
    return bool(row["file"]) and row["line"] is not None and row["line"] >= 1


def branch_findings(rows):
    # Newest first, one row per finding, at most MAX_FINDINGS.
    chosen = []
    seen = set()
    for row in sorted((row for row in rows if is_listed_row(row)),
                      key=lambda row: str(row.get("date") or ""), reverse=True):
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
    return f"- {row['file']}:{row['line']} ({row.get('class')})"


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

        candidates = branch_findings(ledger_findings(cwd, script_utils.repo_name(cwd), branch))
        unchanged = [row for row in candidates if code_unchanged(cwd, row)]
        if unchanged:
            sys.stdout.write(json.dumps({"hookSpecificOutput": {
                "hookEventName": "PreToolUse", "additionalContext": context_text(unchanged)}}))
    except Exception:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
