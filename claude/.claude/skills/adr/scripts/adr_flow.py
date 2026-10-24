#!/usr/bin/env python3
"""Fixed steps of the /adr skill in one call each.

  adr_flow.py prep [<path-or-ticket>]
  adr_flow.py check <adr-path>
  adr_flow.py finish <adr-path> [--task-dir <absolute-task-dir>] [--draft-is-current] [--keep-task-dir]

prep: resolve the task dir, print the target path, the PR url or "(pending)",
the ticket url, the absolute task dir, each source path with its line count,
then the template. It never prints a source body: read the sources with Read.
A standalone `keep` word in the argument is a trigger: prep drops it before
resolving and adds --keep-task-dir to the finish command it prints.
check: required sections filled, no `[placeholder]`, header bullets, section
line caps. finish: check, then delete the task dir only when it is exactly one
slug under the repo docs/plans dir, holds only plan files, and has nothing
staged. It also refuses when the draft is committed and unchanged but not a
descendant of the task dir's last commit, when an ignored task dir file is
newer than a committed draft, or the task dir has uncommitted entries, and
when the draft is untracked or edited but a task dir file is newer than it.
--draft-is-current skips the commit-order and file-age checks only, never the
uncommitted-entries check. --keep-task-dir runs the draft checks only, skips
every task dir check and the delete, and prints the kept task dir path. Both
flags together are accepted; --keep-task-dir wins.

Env overrides (tests): ADR_RESOLVE_SCRIPT, ADR_TEMPLATE, ADR_GH.
Exit: 0 ok, 1 usage / not a repo / check failed, 2 refused delete.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

HOME = Path.home()
sys.path.insert(0, str(HOME / ".claude" / "scripts" / "lib"))
import script_utils

RESOLVE_SCRIPT = os.environ.get("ADR_RESOLVE_SCRIPT") or str(
    HOME / ".claude" / "scripts" / "tools" / "resolve-task-dir.sh"
)
TEMPLATE_PATH = os.environ.get("ADR_TEMPLATE") or str(HOME / ".claude" / "skills" / "_shared" / "adr-template.md")
GH_COMMAND = os.environ.get("ADR_GH") or "gh"

# Task-dir grammar, from every task dir under ~/dev: LED-0-telemetry-contract,
# unified-system, bulk-actions-0809, fuzzy-filter.
TASK_SLUG_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
# One ticket-key grammar (_shared/jira-ticket.md), case-sensitive, with an optional slug:
# LED-5, LED-5-yield-view, RES-2-queue-tui.
TICKET_KEY_PATTERN = re.compile(r"^([A-Z][A-Z0-9]+-[0-9]+)(?:-(.+))?$")
# Files /eng-spec writes into a task dir: 00-ticket, 01-questions, 01-leak-check, 02-research,
# 03-decisions, 04-exploration, 05-plan-review-r1, plan-review-round1, spec, acceptance-criteria,
# and the review shards (review-shard-A, review-shard-seam, spec-review-shard-a, plan-review-shard-b).
# Other names seen in plan dirs (plan.md, slices.md, 04-acceptance-criteria.md) are user notes: finish refuses them.
PLAN_FILE_PATTERN = re.compile(
    r"^(?:00-ticket|01-questions|01-leak-check|02-research|03-decisions|04-exploration|05-plan-review-r[0-9]+"
    r"|plan-review-round[0-9]+|spec|acceptance-criteria|(?:(?:spec|plan)-)?review-shard-[A-Za-z]+)\.md$"
)
SOURCE_FILES = ("spec.md", "03-decisions.md", "02-research.md")
DEFAULT_BRANCHES = ("main", "master")

SECTION_CAPS = {"Problem": 8, "Decision": 8, "Alternatives rejected": 12, "Assumptions": 6, "Watch out for": 10}
TLDR_SENTENCE_CAP = 3
REQUIRED_SECTIONS = ("TL;DR", "Problem", "Decision", "Alternatives rejected", "Assumptions", "Watch out for")
ASK_USER_SECTIONS = ("Alternatives rejected", "Assumptions")
REQUIRED_HEADER_FIELDS = ("Status", "Date", "Reversibility")
BRACKET_PATTERN = re.compile(r"\[([^\]]*)\](?:\(([^)]*)\))?")
CHECKBOX_MARKS = (" ", "x", "X")
LINK_TARGET_MARKS = ("://", "/", ".", "#")
TEMPLATE_TOKENS = ("ABC-XXX", "ABC-YYY", "repo#NNN")
# Placeholders the template puts inside inline code: matched against the raw line.
CODE_SAFE_TEMPLATE_TOKENS = ("[subsystem]",)
ALLOWED_EXTRA_SECTIONS = ("Addenda", "Related")
KNOWN_SECTIONS = REQUIRED_SECTIONS + ALLOWED_EXTRA_SECTIONS
ABBREVIATION_PATTERN = re.compile(r"\b(e\.g|i\.e)\.")
PENDING_PR = "(pending)"
NO_VALUE = "(none)"
SOURCES_HEADING = "sources (read with Read; bodies are not printed):"
NO_TASK_DIR_LINE = "no task dir to delete: finish takes no --task-dir"
INLINE_CODE_PATTERN = re.compile(r"`[^`]*`")
ISO_DATE_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}\b")

KEEP_WORD = "keep"
MODEL_STEPS_PREP = (
    "Model still does: read the sources above with Read, draft the ADR, ask the user when Alternatives "
    "rejected or Assumptions cannot be filled, Write the draft to the target path, then run "
    "`adr_flow.py finish <draft> [--task-dir <absolute task dir>]{keep_flag}`."
)
MODEL_STEPS_AMBIGUOUS = "Model still does: ask the user which candidate is the source, then rerun prep with it."
MODEL_STEPS_FINISH = (
    "Model still does: ask the user `Drafted to <path>. Adjust?`, apply their edits, "
    "then run `adr_flow.py check <path>`."
)


class RefusedError(Exception):
    pass


def run(command, cwd=None, timeout=30):
    try:
        return subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as error:
        return subprocess.CompletedProcess(command, 127, "", str(error))


def repo_root(start=None):
    toplevel = run(["git", "rev-parse", "--show-toplevel"], cwd=start)
    if toplevel.returncode != 0:
        return None
    return Path(toplevel.stdout.strip())


def current_branch(root):
    branch_listing = run(["git", "branch", "--show-current"], cwd=root)
    return branch_listing.stdout.strip()


def default_branches(root):
    names = set(DEFAULT_BRANCHES)
    origin_head = run(["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"], cwd=root)
    if origin_head.returncode == 0:
        names.add(origin_head.stdout.strip().removeprefix("origin/"))
    return names


def resolve_task_dir(root, argument):
    command = ["bash", RESOLVE_SCRIPT]
    if argument:
        command.append(argument)
    resolution = run(command, cwd=root)
    lines = [line for line in resolution.stdout.splitlines() if line.strip()]
    kinds = {0: "task-dir", 5: "legacy-plan", 3: "ambiguous", 4: "none"}
    kind = kinds.get(resolution.returncode)
    if kind is None:
        raise SystemExit(f"adr-flow: resolve-task-dir.sh exited {resolution.returncode}: {resolution.stderr.strip()}")
    return kind, lines, resolution.stderr.strip()


def split_key_slug(name):
    """Return (key, slug) when name is KEY or KEY-slug, else None. slug is "" when absent."""
    match = TICKET_KEY_PATTERN.match(name)
    if not match:
        return None
    return match.group(1), match.group(2) or ""


def argument_key(argument):
    """The key when the whole argument is a bare ticket key (any case), else None."""
    parts = split_key_slug(argument.upper())
    if parts and not parts[1]:
        return parts[0]
    return None


def ticket_key_for(argument, task_name, branch_name):
    """Key from, in order: the argument, the task dir name, the branch name."""
    from_argument = argument_key(argument)
    if from_argument:
        return from_argument
    for name in (task_name, branch_name):
        parts = split_key_slug(name)
        if parts:
            return parts[0]
    return None


def target_slug(key, task_name, branch):
    branch_name = branch.removeprefix("feature/")
    feature_slug = branch_name if branch.startswith("feature/") else ""
    if key:
        for name in (task_name, branch_name):
            parts = split_key_slug(name)
            if parts and parts[0] == key:
                return f"{key}-{parts[1]}" if parts[1] else key
        return key
    return feature_slug or task_name or None


def ticket_url(task_dir):
    ticket_file = Path(task_dir) / "00-ticket.md"
    if not ticket_file.is_file():
        return None
    for line in ticket_file.read_text(errors="replace").splitlines():
        match = re.search(r"\*\*URL:\*\*\s*(\S+)", line)
        if match:
            return match.group(1)
    return None


def detect_pr(root, branch):
    if not branch or branch in default_branches(root):
        return PENDING_PR
    view = run([GH_COMMAND, "pr", "view", "--json", "url", "-q", ".url"], cwd=root, timeout=20)
    view_url = view.stdout.strip()
    if view.returncode == 0 and view_url.startswith("http"):
        return view_url
    listing = run(
        [GH_COMMAND, "pr", "list", "--head", branch, "--state", "all", "--json", "url", "--limit", "1"],
        cwd=root,
        timeout=20,
    )
    if listing.returncode != 0:
        return PENDING_PR
    pull_requests = json.loads(listing.stdout or "[]")
    if pull_requests and str(pull_requests[0].get("url", "")).startswith("http"):
        return pull_requests[0]["url"]
    return PENDING_PR


def line_count(path):
    return len(path.read_text(errors="replace").splitlines())


def source_line(path):
    if not path.is_file():
        return f"- {path} (missing)"
    return f"- {path} ({line_count(path)} lines)"


def task_dir_problem(root, task_dir):
    """Why task_dir is not a deletable task dir (exactly one slug under the repo plans dir), or None."""
    plans_dir = root / "docs" / "plans"
    given = Path(os.path.abspath(task_dir))
    if given.parent != plans_dir:
        return f"{task_dir} is not exactly one slug under {plans_dir}"
    if not TASK_SLUG_PATTERN.match(given.name):
        return f"{given}: slug `{given.name}` does not match the task-dir grammar {TASK_SLUG_PATTERN.pattern}"
    return None


def report_header(root, branch, key):
    return ["# adr prep", f"repo: {root}", f"branch: {branch or '(detached)'}", f"ticket key: {key or NO_VALUE}"]


def split_keep_trigger(argument):
    """Return (argument without standalone `keep` words, whether one was there). `LED-7-keepalive` is no trigger."""
    words = argument.split()
    remaining = [word for word in words if word.lower() != KEEP_WORD]
    return " ".join(remaining), len(remaining) != len(words)


def prep(raw_argument):
    argument, keep_requested = split_keep_trigger(raw_argument)
    keep_flag = " --keep-task-dir" if keep_requested else ""
    root = repo_root()
    if root is None:
        print("adr-flow: not inside a git repository", file=sys.stderr)
        return 1

    names_existing_path = Path(argument).exists() or (root / argument).exists()
    if any(character.isspace() for character in argument) and not names_existing_path:
        print(
            f"adr-flow: prep takes one path or ticket key plus an optional keep; got: {raw_argument}",
            file=sys.stderr,
        )
        return 1

    branch = current_branch(root)
    kind, resolved_lines, resolve_error = resolve_task_dir(root, argument)
    task_path = root / resolved_lines[0] if kind in ("task-dir", "legacy-plan") else None
    task_problem = task_dir_problem(root, task_path) if kind == "task-dir" else None
    if task_problem:
        if Path(os.path.abspath(task_path)).parent != root / "docs" / "eng-specs":
            print(f"not a task dir: {task_problem}", file=sys.stderr)
            return 1
        kind = "old-style-dir"
    task_name = task_path.name.removesuffix(".md") if task_path else ""
    key = ticket_key_for(argument, task_name, branch.removeprefix("feature/"))
    report_lines = report_header(root, branch, key)

    if kind == "ambiguous":
        script_path = Path(__file__).resolve()
        report_lines.append("AMBIGUOUS: several matches, no target chosen. Candidates:")
        report_lines.extend(f"- {root / line}" for line in resolved_lines)
        if keep_requested:
            report_lines.append(f'rerun: python3 {script_path} prep "<one candidate path above> {KEEP_WORD}"')
        else:
            report_lines.append(f"rerun: python3 {script_path} prep <one candidate path above>")
        report_lines.append("")
        report_lines.append(MODEL_STEPS_AMBIGUOUS)
        print("\n".join(report_lines))
        return 0

    slug = target_slug(key, task_name, branch)

    if slug is None:
        report_lines.append("target: (no ticket key or feature/<slug> branch: ask the user for a name)")
    else:
        target = root / "docs" / "decisions" / f"{slug}.md"
        report_lines.append(f"target: {target}")
        if target.exists():
            report_lines.append(f"COLLISION: {target} already exists. Ask the user: pick another name or supersede it.")

    report_lines.append(f"date: {date.today().isoformat()}")
    report_lines.append(f"PR: {detect_pr(root, branch)}")

    if kind == "task-dir":
        url = ticket_url(task_path)
        report_lines.append(f"ticket url: {url or '(none recorded; use the key as plain text)'}")
        report_lines.append(f"task dir: {task_path} (pass exactly this to finish --task-dir)")
        report_lines.append(SOURCES_HEADING)
        report_lines.extend(source_line(task_path / name) for name in SOURCE_FILES)
    elif kind == "old-style-dir":
        report_lines.append(f"old-style plan dir: {task_path}")
        report_lines.append(NO_TASK_DIR_LINE)
        report_lines.append(SOURCES_HEADING)
        report_lines.extend(source_line(path) for path in sorted(task_path.rglob("*")) if path.is_file())
    elif kind == "legacy-plan":
        report_lines.append(f"legacy flat plan: {task_path}")
        report_lines.append(NO_TASK_DIR_LINE)
        report_lines.append(SOURCES_HEADING)
        report_lines.append(source_line(task_path))
    else:
        report_lines.append(f"no spec ({resolve_error}): use the conversation, the branch diff and the ticket")

    report_lines.append("\n## Template")
    template_file = Path(TEMPLATE_PATH)
    if template_file.is_file():
        report_lines.append(template_file.read_text().rstrip())
    else:
        report_lines.append(f"(template missing: {TEMPLATE_PATH})")

    report_lines.append("")
    report_lines.append(MODEL_STEPS_PREP.format(keep_flag=keep_flag))
    print("\n".join(report_lines))
    return 0


def parse_adr(text):
    """Split an ADR into (header_lines, sections, repeats, first_seen).

    Lines are (line number, text, is_fenced), blank lines dropped. Headings are level-2 and
    never taken from fenced code. HTML comments (the Addenda stub) are dropped. sections maps
    a heading to its lines; repeats lists (heading, first line, repeat line); first_seen maps
    a heading to its line number.
    """
    raw_lines = text.splitlines()
    fenced = script_utils.fenced_line_indexes(raw_lines)
    header_lines = []
    sections = {}
    first_seen = {}
    repeats = []
    current_lines = header_lines
    in_comment = False

    for index, raw_line in enumerate(raw_lines):
        number = index + 1
        is_fenced = index in fenced
        if is_fenced:
            line = raw_line
        else:
            line, in_comment = script_utils.visible_text(raw_line, in_comment)

        heading = None if is_fenced else re.match(r"^## (.+?)\s*$", line)
        if heading:
            name = heading.group(1)
            if name in sections:
                repeats.append((name, first_seen[name], number))
            else:
                sections[name] = []
                first_seen[name] = number
            current_lines = sections[name]
            continue

        if line.strip():
            current_lines.append((number, line, is_fenced))
    return header_lines, sections, repeats, first_seen


def sentence_count(lines):
    joined_text = " ".join(text for _, text, _ in lines)
    stripped_text = ABBREVIATION_PATTERN.sub(lambda match: match.group(1).replace(".", ""), joined_text.strip())
    sentences = [part for part in re.split(r"(?<=[.!?])\s+", stripped_text) if part]
    return len(sentences)


def is_placeholder_bracket(match):
    label, target = match.group(1), match.group(2)
    if target is None:
        return label not in CHECKBOX_MARKS
    return not any(mark in target for mark in LINK_TARGET_MARKS)


def has_placeholder(line):
    if any(token in line for token in CODE_SAFE_TEMPLATE_TOKENS):
        return True
    outside_code = INLINE_CODE_PATTERN.sub("", line)
    if any(token in outside_code for token in TEMPLATE_TOKENS):
        return True
    return any(is_placeholder_bracket(match) for match in BRACKET_PATTERN.finditer(outside_code))


def header_field_value(header_lines, field):
    pattern = re.compile(rf"^\s*[-*]\s+\*\*{field}(?::\*\*|\*\*:)\s*(\S.*)$")
    for _, text, is_fenced in header_lines:
        match = None if is_fenced else pattern.match(text)
        if match:
            return match.group(1)
    return None


def check_adr(adr_path):
    """Return (problems, notes) for one ADR file."""
    text = Path(adr_path).read_text(errors="replace")
    header_lines, sections, repeats, first_seen = parse_adr(text)
    problems = []
    notes = []

    for name, first_line, repeat_line in repeats:
        problems.append(f"{adr_path}:{repeat_line}: heading `## {name}` repeats line {first_line}")

    for name in sections:
        if name not in KNOWN_SECTIONS:
            allowed = ", ".join(f"`## {allowed_name}`" for allowed_name in KNOWN_SECTIONS)
            problems.append(
                f"{adr_path}:{first_seen[name]}: unknown section `## {name}`; allowed sections: {allowed}; "
                "use ### for a sub-heading"
            )

    for name in REQUIRED_SECTIONS:
        if name not in sections:
            problems.append(f"{adr_path}: missing section `## {name}`")

    for field in REQUIRED_HEADER_FIELDS:
        value = header_field_value(header_lines, field)
        if value is None:
            problems.append(f"{adr_path}: missing header bullet `- **{field}**: <value>`")
        elif field == "Date" and not ISO_DATE_PATTERN.match(value):
            problems.append(f"{adr_path}: header `Date` is `{value}`, expected YYYY-MM-DD")

    all_lines = header_lines + [entry for lines in sections.values() for entry in lines]
    for number, line, is_fenced in sorted(all_lines):
        if not is_fenced and has_placeholder(line):
            problems.append(f"{adr_path}:{number}: unfilled placeholder: {line.strip()}")

    for name in REQUIRED_SECTIONS:
        if name not in sections:
            continue
        filled_lines = [entry for entry in sections[name] if entry[2] or not has_placeholder(entry[1])]
        if filled_lines:
            continue
        suffix = "; ask the user, never invent" if name in ASK_USER_SECTIONS else ""
        problems.append(f"{adr_path}: `{name}` is empty or only placeholders{suffix}")

    if "TL;DR" in sections:
        tldr_sentences = sentence_count(sections["TL;DR"])
        if tldr_sentences > TLDR_SENTENCE_CAP:
            problems.append(f"{adr_path}: TL;DR has {tldr_sentences} sentences, cap {TLDR_SENTENCE_CAP}")

    for name, cap in SECTION_CAPS.items():
        if name in sections and len(sections[name]) > cap:
            problems.append(f"{adr_path}: `{name}` has {len(sections[name])} lines, cap {cap}")

    total = len(text.splitlines())
    if total > 80:
        notes.append(f"{total} lines; target 50-80 (past that is eng-arch material)")
    return problems, notes


def command_check(adr_path):
    if not Path(adr_path).is_file():
        print(f"adr-flow: no such file: {adr_path}", file=sys.stderr)
        return 1
    problems, notes = check_adr(adr_path)
    for problem in problems:
        print(f"FAIL {problem}")
    for note in notes:
        print(f"note: {note}")
    if problems:
        return 1
    print(f"check ok: {adr_path}")
    return 0


def git_status_entries(root, relative):
    """Return [(two-letter status, path)] for the task dir, renames and copies as the new path."""
    status_listing = run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all", "--ignored", "--", relative], cwd=root
    )
    if status_listing.returncode != 0:
        raise RefusedError(f"git status failed: {status_listing.stderr.strip()}")

    entries = []
    skip_next = False
    for field in status_listing.stdout.split("\0"):
        if skip_next:
            skip_next = False
            continue
        if field == "":
            continue
        if len(field) < 4 or field[2] != " ":
            raise RefusedError(f"git status gave an entry this script cannot read: {field!r}")
        status, path = field[:2], field[3:]
        if "R" in status or "C" in status:
            skip_next = True
        entries.append((status, path))
    return entries


def refuse_hidden_edits(root, relative):
    """Refuse when a tracked file in the task dir is skip-worktree or assume-unchanged: git status cannot see its
    edits."""
    tracked_listing = run(["git", "ls-files", "-v", "-z", "--", relative], cwd=root)
    if tracked_listing.returncode != 0:
        raise RefusedError(f"git ls-files failed: {tracked_listing.stderr.strip()}")
    hidden = []
    for entry in tracked_listing.stdout.split("\0"):
        if len(entry) < 3:
            continue
        flag, path = entry[0], entry[2:]
        if flag == "S" or flag.islower():
            hidden.append(path)
    if hidden:
        raise RefusedError(
            f"tracked files hidden from git status (skip-worktree or assume-unchanged): {', '.join(hidden[:5])}"
        )


def is_plan_file(name):
    return bool(PLAN_FILE_PATTERN.match(name))


def non_plan_entries(root, task_dir, status_entries):
    """Paths in the task dir (on disk or deleted from a tracked set) that are not top-level plan files."""
    relative = task_dir.relative_to(root).as_posix()
    offenders = []
    for path in sorted(task_dir.rglob("*")):
        if path.parent != task_dir or path.is_dir() or not is_plan_file(path.name):
            offenders.append(path.relative_to(root).as_posix())
    for _, path in status_entries:
        inside = path[len(relative) + 1:] if path.startswith(relative + "/") else path
        if "/" in inside or not is_plan_file(inside):
            offenders.append(path)
    return list(dict.fromkeys(offenders))


def refuse_other_ticket(adr_file, task_dir):
    adr_parts = split_key_slug(adr_file.stem)
    task_parts = split_key_slug(task_dir.name)
    if adr_parts and task_parts and adr_parts[0] != task_parts[0]:
        raise RefusedError(f"the draft is for {adr_parts[0]} but the task dir is for {task_parts[0]}")


def last_commit_of(root, path):
    """(hash, author time in ns) of the last commit that touched path, or None when no commit did.

    A rebase keeps the author time."""
    commit_listing = run(["git", "log", "-1", "--format=%H %at", "--", str(path)], cwd=root)
    fields = commit_listing.stdout.split()
    if commit_listing.returncode != 0 or len(fields) != 2:
        return None
    return fields[0], int(fields[1]) * 10**9


def committed_draft_refusal(adr_file):
    return RefusedError(
        f"{adr_file} is already committed and unchanged; write the new draft before deleting the task dir. "
        "If the user says the committed draft already holds the decision, rerun finish with --draft-is-current"
    )


def refuse_task_files_newer_than(task_files, cutoff_ns):
    """Refuse when a file in task_files changed after cutoff_ns: the draft may not hold it."""
    newer = sorted(path.name for path in task_files if path.is_file() and script_utils.last_change_ns(path) > cutoff_ns)
    if newer:
        raise RefusedError(
            f"task dir files are newer than the draft: {', '.join(newer[:10])}. "
            "Fold them into the draft, or rerun finish with --draft-is-current if the user says the draft holds them"
        )


def refuse_unproven_draft(root, adr_file, task_dir, status_entries, draft_is_current):
    """Refuse a delete when the draft may not hold the task dir's latest work.

    status_entries are the task dir's git status entries that validate_task_dir already read.
    Draft untracked or edited: refuse when a task dir file changed after the draft was written.
    Draft tracked and unchanged: refuse when the task dir has any uncommitted entry; then, unless
    draft_is_current, refuse when an ignored task dir file changed after the draft was written,
    and when the draft's last commit is not a descendant of the task dir's last commit (commit
    ancestry, not commit time; a task dir with no commit is refused too). A draft committed
    together with, or after, the task dir files is the new draft. draft_is_current skips the
    file-age and ancestry checks, never the uncommitted-changes check. The ignored-file age check
    uses the earlier of the draft's mtime and its last commit's author time: a rebase rewrites the
    draft's mtime and commit time but keeps the author time.
    """
    adr_path = adr_file.resolve()
    tracked = run(["git", "ls-files", "--error-unmatch", "--", str(adr_path)], cwd=root)
    changes = run(["git", "status", "--porcelain", "--", str(adr_path)], cwd=root)
    draft_mtime_ns = adr_path.stat().st_mtime_ns
    if tracked.returncode != 0 or changes.stdout.strip():
        if not draft_is_current:
            task_files = list(task_dir.rglob("*"))
            refuse_task_files_newer_than(task_files, draft_mtime_ns)
        return

    uncommitted = [path for status, path in status_entries if status != "!!"]
    if uncommitted:
        raise RefusedError(
            f"task dir has uncommitted changes: {', '.join(uncommitted[:10])}. "
            "Commit or discard them, then run finish again"
        )

    if draft_is_current:
        return
    ignored = [root / path for status, path in status_entries if status == "!!"]
    draft_commit = last_commit_of(root, adr_path)
    if draft_commit is None:
        raise committed_draft_refusal(adr_file)
    draft_hash, draft_author_ns = draft_commit
    refuse_task_files_newer_than(ignored, min(draft_mtime_ns, draft_author_ns))
    task_dir_commit = last_commit_of(root, task_dir)
    if task_dir_commit is not None:
        draft_follows_task_dir = run(["git", "merge-base", "--is-ancestor", task_dir_commit[0], draft_hash], cwd=root)
        if draft_follows_task_dir.returncode == 0:
            return
    raise committed_draft_refusal(adr_file)


def validate_task_dir(root, task_dir_argument):
    """Return (the Path to delete, its git status entries), or raise Refused."""
    plans_dir = root / "docs" / "plans"
    if not task_dir_argument:
        raise RefusedError("--task-dir is empty; pass the absolute task dir printed by prep, or omit the flag")
    if not os.path.isabs(task_dir_argument):
        raise RefusedError(f"--task-dir `{task_dir_argument}` is relative; pass the absolute task dir printed by prep")
    given = Path(os.path.abspath(task_dir_argument))

    problem = task_dir_problem(root, given)
    if problem:
        raise RefusedError(problem)
    if given.is_symlink():
        raise RefusedError(f"{given} is a symlink")
    for parent in (root / "docs", plans_dir):
        if parent.is_symlink():
            raise RefusedError(f"{parent} is a symlink")
    if not given.is_dir():
        raise RefusedError(f"{given} is not a directory")
    if os.path.realpath(given) != str(given) or os.path.realpath(root) != str(root):
        raise RefusedError(f"{given} does not resolve to itself")

    given_root = repo_root(given)
    if given_root != root:
        raise RefusedError(
            f"{given} belongs to the git repository at {given_root}, not {root}; git status cannot vouch for it"
        )

    relative = given.relative_to(root).as_posix()
    refuse_hidden_edits(root, relative)

    status_entries = git_status_entries(root, relative)
    staged_paths = [path for status, path in status_entries if status[0] not in " ?!"]
    if staged_paths:
        raise RefusedError(
            f"STOP: staged entries in the task dir: {', '.join(staged_paths[:10])}. "
            "The user must commit or unstage them, then run finish again. Nothing was unstaged."
        )

    offenders = non_plan_entries(root, given, status_entries)
    if offenders:
        raise RefusedError(f"the task dir holds files that are not plan files: {', '.join(offenders[:10])}")
    return given, status_entries


def kept_task_dir(root, argument):
    """The absolute path when argument names an existing task dir (absolute, a directory, one slug under plans), else
    None."""
    if not argument or not os.path.isabs(argument) or not os.path.isdir(argument):
        return None
    if task_dir_problem(root, argument) is not None:
        return None
    return Path(os.path.abspath(argument))


def finish(adr_path, task_dir_argument, draft_is_current, keep_task_dir):
    adr_file = Path(adr_path)
    if not adr_file.is_file():
        print(f"adr-flow: no such file: {adr_path}", file=sys.stderr)
        return 1

    root = repo_root(adr_file.resolve().parent)
    if root is None:
        print("adr-flow: the draft is not inside a git repository", file=sys.stderr)
        return 1

    problems, notes = check_adr(adr_path)
    for note in notes:
        print(f"note: {note}")
    if problems:
        for problem in problems:
            print(f"FAIL {problem}")
        print("Nothing deleted. Fix the draft, then run finish again.")
        return 1

    kept = kept_task_dir(root, task_dir_argument)
    draft_inside_task_dir = kept is not None and kept in adr_file.resolve().parents
    if keep_task_dir:
        if draft_inside_task_dir:
            print("FAIL the draft lives inside the task dir; move it to the prep target")
            return 1
        if kept is not None:
            print(f"task dir kept: {kept}")
        elif task_dir_argument is None:
            print("no task dir passed")
        elif task_dir_argument == "":
            print("no task dir kept: --task-dir is empty")
        else:
            print(f"no task dir kept: {task_dir_argument} is not a task dir")
    elif task_dir_argument is not None:
        if draft_inside_task_dir:
            print("REFUSED delete: the draft lives inside the task dir; move it to the prep target")
            print(f"The draft passed the checks and stays at {adr_path}. Task dir kept.")
            return 2
        try:
            task_dir, status_entries = validate_task_dir(root, task_dir_argument)
            refuse_other_ticket(adr_file, task_dir)
            refuse_unproven_draft(root, adr_file, task_dir, status_entries, draft_is_current)
        except RefusedError as refusal:
            outcome = "Task dir kept." if kept is not None else "Nothing was deleted."
            print(f"REFUSED delete: {refusal}")
            print(f"The draft passed the checks and stays at {adr_path}. {outcome}")
            if kept is not None:
                print("To finish without deleting the task dir, rerun finish with --keep-task-dir.")
            else:
                print("Pass the absolute task dir printed by prep, or omit --task-dir.")
            return 2
        shutil.rmtree(task_dir)
        print(f"deleted task dir: {task_dir.relative_to(root)}")
    else:
        print("no task dir deleted (none passed)")

    print(f"Drafted to {adr_path}. Adjust?")
    print(MODEL_STEPS_FINISH)
    return 0


def main(argv):
    if len(argv) < 2 or argv[1] not in ("prep", "check", "finish"):
        print(__doc__, file=sys.stderr)
        return 1

    verb, rest = argv[1], argv[2:]
    if verb == "prep":
        if len(rest) > 1:
            print("adr-flow: prep takes one optional argument; quote it", file=sys.stderr)
            return 1
        return prep(rest[0] if rest else "")

    if verb == "check":
        if len(rest) != 1:
            print("usage: adr_flow.py check <adr-path>", file=sys.stderr)
            return 1
        return command_check(rest[0])

    task_dir_argument = None
    if "--task-dir" in rest:
        position = rest.index("--task-dir")
        if position + 1 >= len(rest):
            print("adr-flow: --task-dir needs a value", file=sys.stderr)
            return 1
        task_dir_argument = rest[position + 1]
        rest = rest[:position] + rest[position + 2:]
    draft_is_current = "--draft-is-current" in rest
    keep_task_dir = "--keep-task-dir" in rest
    rest = [argument for argument in rest if argument not in ("--draft-is-current", "--keep-task-dir")]
    if len(rest) != 1:
        print(
            "usage: adr_flow.py finish <adr-path> [--task-dir <absolute-task-dir>] "
            "[--draft-is-current] [--keep-task-dir]",
            file=sys.stderr,
        )
        return 1
    return finish(rest[0], task_dir_argument, draft_is_current, keep_task_dir)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
