#!/usr/bin/env python3
"""PostToolUse hook on Write|Edit: WARN on planning vocabulary in shipped source and on document citations that no
longer resolve. Never blocks: always exits 0, warnings go to stderr.

Markdown-like files (.md .markdown .rst .txt): every `dir/file.ext[:line]` citation is checked against the repo root
and the document's own directory. Source files: comment lines are scanned for planning vocabulary, any line for the
hard markers. Files outside a git work tree are skipped.
"""
import json
import os
import re
import subprocess
import sys

from hook_input import emit_stderr

DOC_SUFFIXES = (".md", ".markdown", ".rst", ".txt")
SOURCE_SUFFIXES = (".py", ".ts", ".tsx", ".js", ".mjs", ".cjs", ".go", ".rs", ".rb", ".sh", ".sql", ".yml", ".yaml",
                   ".scss", ".css", ".java", ".kt")
SKIPPED_PATH_PARTS = ("/.claude/", "/node_modules/", "/.venv/", "/dist/", "/build/")
SKIPPED_SUFFIXES = (".min.js", ".lock")

# Longest extension first: .jsonl must not match as .json, .tsv as .ts.
CITATION = re.compile(
    r"\b[A-Za-z0-9_][A-Za-z0-9_.-]*(/[A-Za-z0-9_.-]+)+"
    r"\.(markdown|jsonl|json|yaml|yml|tsx|tsv|toml|mjs|cjs|sql|sh|rs|py|md|ts|js|go)"
    r"(:[0-9]{1,6})?([^A-Za-z0-9]|$)")
TRAILING_PUNCTUATION = re.compile(r"[^A-Za-z0-9]$")

COMMENT_LINE = re.compile(r"^\s*(#|//|/\*|\*|--|\"\"\"|''')")
VOCABULARY = [re.compile(pattern, re.I) for pattern in (
    r"\bphases? [0-9]",
    r"\(D[0-9]{1,2}\)|\bper D[0-9]{1,2}\b|\bD[0-9]{1,2}:",
    r"\bAC[0-9]{1,2}\b",
    r"written by the (coder|architect|assistant)|per the (architect|plan)",
    r"an earlier version (said|had)",
)]
HARD_MARKERS = re.compile(r"docs/plans/|ACCEPTANCE-CONTRACT|PLAN-IMPACT")


def jq_path(value):
    if value is None or value is False:
        return ""
    if isinstance(value, str):
        return value.rstrip("\n")
    return json.dumps(value)


def read_lines(path):
    try:
        with open(path, "rb") as handle:
            return handle.read().decode("utf-8", "surrogateescape").split("\n")
    except OSError:
        return []


def repo_root(file_path):
    directory = os.path.dirname(file_path) or "."
    try:
        finished = subprocess.run(["git", "-C", directory, "rev-parse", "--show-toplevel"],
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except OSError:
        return ""
    if finished.returncode != 0:
        return ""
    return finished.stdout.decode("utf-8", "surrogateescape").rstrip("\n")


def citations_in(lines):
    cites = set()
    for line in lines:
        for found in CITATION.finditer(line):
            cites.add(TRAILING_PUNCTUATION.sub("", found.group(0)))
    return sorted(cites)


def newline_count(path):
    try:
        with open(path, "rb") as handle:
            return handle.read().count(b"\n")
    except OSError:
        return 0


def unresolved_citations(file_path, relative_path, root):
    document_dir = os.path.dirname(file_path) or "."
    proposes = ("/plans/" in relative_path or relative_path.endswith("/spec.md")
                or relative_path.endswith("-plan.md") or "/PREREG" in relative_path
                or "/plans-final/" in relative_path)
    missing = ""
    for cite in citations_in(read_lines(file_path)):
        if not cite:
            continue
        line = ""
        path = cite
        if ":" in cite:
            path, line = cite.rsplit(":", 1)
        if "<" in path or "*" in path or "N." in path or "{" in path:
            continue
        candidates = [root + "/" + path, document_dir + "/" + path]
        target = ""
        for candidate in candidates:
            if os.path.exists(candidate):
                target = candidate
                break
        if not target:
            # A path whose own directory is absent is probably not repo-relative.
            anchored = any(os.path.isdir(os.path.dirname(candidate) or ".") for candidate in candidates)
            if anchored and (not proposes or line):
                missing += "  %s — no such path\n" % cite
        elif line and os.path.isfile(target):
            count = newline_count(target)
            if int(line) > count:
                missing += "  %s — file has %d lines\n" % (cite, count)
    return missing


def planning_vocabulary_hits(file_path):
    lines = read_lines(file_path)
    hits = {}
    for number, line in enumerate(lines, 1):
        if not COMMENT_LINE.search(line):
            continue
        row = "%d:%s" % (number, line)
        if any(pattern.search(row) for pattern in VOCABULARY):
            hits[number] = line
    for number, line in enumerate(lines, 1):
        if HARD_MARKERS.search(line):
            hits[number] = line
    return ["%d:%s" % (number, hits[number]) for number in sorted(hits)]


def check(raw):
    payload = json.loads(raw)
    tool_input = payload.get("tool_input") if isinstance(payload, dict) else None
    if not isinstance(tool_input, dict):
        return
    file_path = jq_path(tool_input.get("file_path"))
    if not file_path or not os.path.isfile(file_path):
        return

    root = repo_root(file_path)
    if not root:
        return
    if any(part in file_path for part in SKIPPED_PATH_PARTS) or file_path.endswith(SKIPPED_SUFFIXES):
        return
    relative_path = file_path[len(root) + 1:] if file_path.startswith(root + "/") else file_path

    if file_path.endswith(DOC_SUFFIXES):
        missing = unresolved_citations(file_path, relative_path, root)
        if missing:
            emit_stderr("stale-citation-gate: %s cites paths that do not resolve — a rename, renumber or deletion "
                        "elsewhere falsified them:\n%s" % (relative_path, missing))
        return

    if not file_path.endswith(SOURCE_SUFFIXES):
        return
    hits = planning_vocabulary_hits(file_path)
    if hits:
        emit_stderr("stale-citation-gate: planning vocabulary in shipped source %s — keep the fact, cut the "
                    "reference (see skills/_shared/code-vocabulary.md):\n%s"
                    % (relative_path, "".join("  %s\n" % hit for hit in hits)))


def main():
    try:
        check(sys.stdin.buffer.read())
    except Exception:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
