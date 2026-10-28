#!/usr/bin/env python3
"""The scripted review loop: the walking between steps is code, the judgment inside each step is a model call.

    review_loop_script.py <repo> --state-dir <dir> --session <id> --run-id <id> --agent-id <id> --prompt-file <path>

The prompt file is the review prompt of a review-first dispatch: header lines (mode, caller, lane, plan, phase, an
optional `structure-pass: skip`), a blank line, then the handoff block. The script walks review-loop.md's fixed graph:
scope, first-round reviewers (code, plus smell and test reviewers on a large diff), disposition routing, one fix coder,
re-review by every reviewer that filed a fix and owns a changed file (the smell reviewer only past the size bar), the
two-round cap, the full-check execution gate, the class-closure check, telemetry rows, and the hand-back packet.
The full check runs through full_check.py: none in a repo whose CLAUDE.md holds `Full suite: CI`, where the coder
calls run the changed files' tests, none in a repo where no check is found, and a check past CHECK_TIMEOUT_SECONDS is
killed with its process group, and a check whose step stops on a missing path is a check-command error. A check
that fails on a missing module the repo declares as a dependency is an environment gap. None is a failure: the
packet's `full_check` says `not run (CI)`, `not run (no check found; ...)`, `not run (timeout)`,
`not run (check-command error: ...)` or `not run (environment gap: ...)`. An exit 0 with no runner summary is no
failure either: it says `unverified (exit 0, no runner summary)`. A failed check's blocker holds the failing step's
lines.

Model steps are `claude -p` calls in auto permission mode, each with CLAUDE_FORMAT_HOOK_OFF=1 in its environment: the
reviewers (agents code-reviewer, smell-reviewer, test-reviewer), the fix coder (agent coder) and the class-closure
judgment (Sonnet). When the repo CLAUDE.md names no `Quality check` line, a Haiku check-finder call names the full
check; when it names none, the review runs with no full check. A Sonnet disposition call runs
only when a reviewer's output has no Fix/Ask/Nit sections the parser can read. Every call is logged to
<state dir>/loop-script/<agent id>/calls.jsonl with its session id, role, wall time and token counts.

On finish, or on any uncaught error, the script validates its packet with handback.load, then appends the rows the
review-loop agent leaves: the run event of a hand-back, the hand-back store row, the stop row, and, when the telemetry
switch is on, one agent-usage row. Exit 0 on a normal finish; exit 1 when the run crashed or the packet failed
validation (a critical-blocker packet and the rows are still written). A SIGTERM (abort, review-again, start
--restart) kills every running claude call and exits 143 with no packet and no rows.

Not covered: the second-order caller supplement, the critical-blocker judgment (a reviewer routes it as an ask), and
the fix-first mode.
"""

import argparse
import contextlib
import difflib
import hashlib
import json
import os
import pathlib
import re
import signal
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPT_DIR.parent / folder) for folder in (".", "review", "code", "lib", "telemetry")]
import code_step_core
import full_check
import handback
import plan_format
import review_loop_gate
import reviewed_tree
import script_utils
from worktree_snapshot import CHANGE_KINDS

SKILLS = SCRIPT_DIR.parent.parent / "skills" / "review"
ROUND_BUDGET = 2
REFILE_SIMILARITY = 0.8
LARGE_ADDED_LINES = 40
SPLIT_FILES = 5
SPLIT_LINES = 300
DIFF_CONTEXT = 12
CALL_TIMEOUT_SECONDS = 1800
CHECK_TIMEOUT_SECONDS = 900
LOG_TIMEOUT_SECONDS = 60
TOKEN_FIELDS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
UNLOCATED = "unlocated"
NO_CLOSURE = "n/a - fixed[] empty"
TERMINAL_PANE_ENV = ("HERDR_ENV", "HERDR_PANE_ID", "HERDR_SOCKET_PATH", "TUIOS_SOCKET")
CHILD_ENV = {**{name: value for name, value in os.environ.items() if name not in TERMINAL_PANE_ENV},
             "CLAUDE_FORMAT_HOOK_OFF": "1"}

FENCE = (
    'Fix only the issues listed below. Do not refactor surrounding code. Do not "improve" things you '
    "notice along the way. Do not rename, restructure, or add abstractions that aren't required by the "
    'fix itself. A focused 5-line fix is the right output, not a 50-line cleanup PR.\n'
    '\n'
    'After fixing each issue, check all callers and consumers of the changed code. If a fix changes a '
    'method signature, return type, or behavioral contract, update every caller in the same pass. Do not '
    'leave callers out of sync.\n'
    '\n'
    'If a listed issue turns out to be a false positive on inspection, skip it and report why. Do not '
    '"fix" issues that aren\'t actually broken just because the reviewer flagged them.'
)

SMALL_ITEMS = (
    "Small items follow the issues. They are the reviewer's optional notes, not findings. Apply a small "
    'item only when it names wrong behavior, or a false statement in a doc or a comment, and one '
    'correction is clear. Skip every other small item, and report each skip with its reason. A small '
    'item never widens the change: no rename, no restructure, no new abstraction.'
)

CLOSURE_RULES = (
    'For each finding in fixed[], ask whether it is class-shaped: one member of an enumerable set of '
    'ways the same mistake can occur. Two shapes qualify:\n'
    '- Enumerable exit/branch space: the fix touched one of N exits, cases, or branches, and the other '
    'N-1 were never re-read. Close it by re-enumerating them and stating where each one lands.\n'
    '- Proxy predicate: the fix removed a cheap check standing in for the property actually needed. '
    'Close it by naming the other members that proxy was covering for.\n'
    'Work from the fix diff; read a file only to see a member the diff does not show. If a fixed finding '
    'is class-shaped and the class is NOT closed (some member still has the defect), list those members '
    'as open findings, each with file and line and the one correction. You may not edit files.'
)

CHECK_FINDER = (
    'Repo root: {repo}\n\n'
    'Name the one shell command, run from the repo root, that runs this repo\'s full quality check: the lint, type '
    'check and test steps its CI gate runs. Read CLAUDE.md, AGENTS.md, the README, the Makefile, package.json, '
    'pyproject.toml and the files under .github/workflows to find it. Chain steps with && when no single target '
    'runs them all. A workflow\'s or job\'s defaults.run.working-directory holds for every run step that sets no '
    'working-directory of its own: write each such step as (cd <dir> && <step>), so no step\'s directory carries '
    'into the next. A step for a package in a subfolder is written the same way. Leave a JS step out when the repo '
    'has no package.json. Name only commands those files name. Run nothing.\n\n'
    'End your reply with one JSON object: {{"command": "<shell command>"}}, or {{"command": null, "reason": '
    '"<what is missing>"}} when the files name no check.'
)

# A reviewer ask that says the fix would change the approved plan. An ask may open with its file:line and its
# bracketed tags, in either order.
PLAN_CHANGE_MARK = re.compile(r"(?:(?:`?[\w./-]+\.\w+:\d+`?|\[[\w-]+\])[\s—\N{EN DASH}:-]*)*plan[-_ ]?impact", re.I)
PLAN_CHANGE_YES = re.compile(r"plan[-_ ]?impact:\s*yes\s*$", re.I | re.M)
# The marker before the one edit an accepted ask makes: `... — the question — change: the edit`.
ASK_CHANGE_MARK = re.compile(r"\bchange:", re.I)
FINDING_CLASS_TAG = re.compile(r"\[(" + "|".join(map(re.escape, handback.CLASSES)) + r")\]", re.I)
CLASS_TAG_RULE = ("Tag each Fix, Ask and Nit item with its class in brackets, right after its file:line, or first when "
                  "it names none. One of: " + " ".join(f"[{name}]" for name in handback.CLASSES) + ".")
ASSESSMENT_LINE = re.compile(r"\W*overall assessment\b", re.I)

CALLS = []
CALLS_LOCK = threading.Lock()
FIX_DIFFS = []
# Process-group leaders of the claude calls now running: each call starts its own session, so the group kill that
# stops this script does not reach them.
LIVE_CHILDREN = set()


def now():
    return time.time()


def token_total(payload):
    usage = payload.get("usage") if isinstance(payload, dict) else None
    if not isinstance(usage, dict):
        return 0
    return sum(usage.get(field) or 0 for field in TOKEN_FIELDS)


def claude_call(role, prompt, repo, out, agent=None, model=None, tools=None):
    """One `claude -p` model step. Returns the result text. A call that fails or prints no JSON reply raises. The
    prompt goes on stdin: a round-two prompt holds the fix diff and can pass the 128 KB limit of one argument."""
    command = ["claude", "-p", "--output-format", "json", "--permission-mode", "auto"]
    if agent:
        command += ["--agent", agent]
    if model:
        command += ["--model", model]
    if tools:
        command += ["--tools", tools]

    started = now()
    child_pids = []

    def child_started(pid):
        child_pids.append(pid)
        LIVE_CHILDREN.add(pid)

    try:
        return_code, stdout, stderr = script_utils.run_process(command, repo, stdin=prompt,
                                                               timeout=CALL_TIMEOUT_SECONDS, env=CHILD_ENV,
                                                               on_start=child_started)
    finally:
        LIVE_CHILDREN.difference_update(child_pids)
    wall = round(now() - started, 1)

    with CALLS_LOCK:
        sequence = len(CALLS) + 1
        CALLS.append(None)
    raw = out / f"call-{sequence:02d}-{role}.json"
    raw.write_text(stdout)
    errors = out / f"call-{sequence:02d}-{role}.err"
    errors.write_text(stderr)

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        payload = None
    replied = isinstance(payload, dict)
    text = (payload.get("result") or "") if replied else ""
    session = (payload.get("session_id") or "") if replied else ""
    tokens = token_total(payload)

    record = {"n": sequence, "role": role, "agent": agent, "model": model, "session": session, "wall": wall,
              "rc": return_code, "tokens": tokens}
    with CALLS_LOCK:
        CALLS[sequence - 1] = record
        with (out / "calls.jsonl").open("a") as handle:
            handle.write(json.dumps(record) + "\n")

    if return_code != 0 or not replied:
        said = f" saying \"{script_utils.one_line(text)}\"" if text.strip() else ""
        raise RuntimeError(f"the {role} call failed (exit {return_code}){said}; reply {raw}, stderr {errors}")
    return text


def git_lines(repo, *args):
    output = script_utils.git_output(repo, *args)
    if output is None:
        raise RuntimeError(f"`git {' '.join(args)}` failed in {repo}")
    return output.splitlines()


def scope(repo):
    """{path: [added, status]} for the working tree against HEAD, untracked files included."""
    files = {}
    for line in git_lines(repo, "status", "--porcelain", "--untracked-files=all"):
        status, path = line[:2].strip(), line[3:]
        files[path] = [0, "??" if status == "??" else status[0]]
    for line in git_lines(repo, "diff", "--numstat", "HEAD"):
        added, _deleted, path = line.split("\t")
        if path in files and added != "-":
            files[path][0] = int(added)
    for path, entry in files.items():
        if entry[1] == "??":
            entry[0] = len((pathlib.Path(repo) / path).read_bytes().splitlines())
    return files


def is_test(path):
    return ".test." in path or ".spec." in path or path.startswith("tests/")


def counts_toward_size(path):
    """Whether a changed file's added lines count toward the source-size bar: not a test, a lockfile or a doc."""
    return not is_test(path) and not path.endswith(("package-lock.json", ".md"))


def first_round_plan(files, structure_pass_skipped=False):
    """Which reviewers go out in the first round, and who owns which files."""
    source = [path for path in files if not is_test(path)]
    tests = [path for path in files if is_test(path)]
    added = sum(files[path][0] for path in files if counts_toward_size(path))
    new_source = any(files[path][1] in ("??", "A") for path in source)
    large = bool(source) and (added >= LARGE_ADDED_LINES or new_source)

    dispatches = []
    if large and tests:
        dispatches.append(("code-reviewer", source))
        dispatches.append(("test-reviewer", tests))
    else:
        dispatches.append(("code-reviewer", list(files)))
    if large and not structure_pass_skipped:
        dispatches.append(("smell-reviewer", list(files)))
    changed_lines = sum(entry[0] for entry in files.values())
    if len(files) > SPLIT_FILES and changed_lines >= SPLIT_LINES and len(source) > 1:
        half = len(source) // 2
        dispatches[0] = ("code-reviewer", source[:half])
        dispatches.insert(1, ("code-reviewer", source[half:]))
    return dispatches


def second_round_plan(round_fix, changed, skipped_findings, coder_diffs):
    """Which reviewers go out in round two, and who owns which files."""
    smell_runs = added_source_lines(coder_diffs) >= LARGE_ADDED_LINES
    dispatches = []
    for agent, fixes in round_fix:
        if not fixes:
            continue
        skipped_paths = [finding_file(fix)[0] for fix in fixes if any(fix in item for item in skipped_findings)]
        owned = [path for path in dict.fromkeys(changed + skipped_paths)
                 if path and is_test(path) == (agent == "test-reviewer")]
        if agent == "smell-reviewer" and not smell_runs:
            continue
        if not owned:
            continue
        dispatches.append((agent, owned))
    return dispatches


def review_scope_lines(repo, owned, prior_issues, open_asks):
    lines = [f"Repo root: {repo}", "Review scope (this round):", "  owned files:"]
    for path in owned:
        lines.append(f"    - {path}")
    if prior_issues:
        lines.append("  prior issues:")
    for item in prior_issues:
        lines.append(f"    - issue: {json.dumps(item['issue'])}")
        lines.append(f"      status: {item['status']}")
        lines.append(f"      file: {item['file']}")
        if item.get("reason"):
            lines.append(f"      reason: {json.dumps(item['reason'])}")
    if open_asks:
        lines.append("  open asks (do not re-raise):")
    for ask in open_asks:
        lines.append(f"    - {json.dumps(ask)}")
    return lines


def reviewer_prompt(repo, agent, owned, prior_issues, fix_diff_path="", open_asks=(), brief=""):
    # The fix diff goes in a file the reviewer reads: inlined, a large diff runs the call past its prompt limit.
    lines = review_scope_lines(repo, owned, prior_issues, open_asks)
    lines.append("Your scope is the owned files listed under Review scope (this round).")
    lines.append(CLASS_TAG_RULE)
    if fix_diff_path:
        lines.append("Round-one fix diff (what the coder changed since the first review; read it, and review only "
                     "the owned files under Review scope (this round)): " + fix_diff_path)
    if agent == "test-reviewer":
        lines.append("Source under test: the diff's non-test files.")
    if agent == "smell-reviewer":
        lines.append("Bound: the round-one fix diff." if fix_diff_path else "Bound: the diff under first review.")
    if brief:
        lines.append(brief)
    return "\n".join(lines)


def section(text, name):
    match = re.search(rf"^#+\s*{name}\s*$(.*?)(?=^#+\s|\Z)", text, re.S | re.M | re.I)
    return match.group(1).strip() if match else None


def review_section_findings(block):
    if not block:
        return []
    found = []
    for line in block.splitlines():
        stripped = re.sub(r"^\s*(?:[-*]+|\d+[.)])\s+", "", line).strip()
        if not stripped:
            continue
        if re.fullmatch(r"\[?(none|n/a|omitted|empty)[^\]]*\]?\.?", stripped, re.I):
            continue
        if ASSESSMENT_LINE.match(stripped):
            continue
        found.append(stripped)
    return found


TAGGED_BULLET = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+`?(fix|ask|nit)`?\s*:\s*(.+)$", re.I)


def parse_tagged_bullets(text):
    """Reviewers that tag each bullet with its disposition (the test reviewer) instead of using Fix/Ask/Nit sections."""
    found = {"fix": [], "ask": [], "nit": []}
    for line in text.splitlines():
        match = TAGGED_BULLET.match(line)
        if match:
            found[match.group(1).lower()].append(match.group(2).strip())
    if not any(found.values()):
        return None
    return {**found, "assessment": ""}


def parse_review(text):
    fix, ask, nit = section(text, "Fix"), section(text, "Ask"), section(text, "Nit")
    if fix is None and ask is None and nit is None:
        return parse_tagged_bullets(text)
    assessment = re.search(r"Overall Assessment\W*\s*:?\W*\s*([A-Z][A-Z ]+[A-Z])", text)
    return {"fix": review_section_findings(fix), "ask": review_section_findings(ask),
            "nit": review_section_findings(nit),
            "assessment": assessment.group(1).strip() if assessment else ""}


def last_json_object(reply, keys):
    """The last JSON object in a reply that holds any of `keys`, or None. Decodes from each "{" back to front, because
    prose before the object can hold braces of its own ("{CUBE}")."""
    decoder = json.JSONDecoder()
    brace_positions = [match.start() for match in re.finditer(r"\{", reply)]
    for position in reversed(brace_positions):
        try:
            parsed, _ = decoder.raw_decode(reply, position)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and any(key in parsed for key in keys):
            return parsed
    return None


def disposition_call(text, repo, out):
    prompt = (
        "Below is a code reviewer's output. Copy each finding into one of three lists without changing its words: "
        "fix, ask, nit "
        "(the reviewer's own section decides; do not re-label). Reply with one JSON object only: "
        '{"fix": [..], "ask": [..], "nit": [..]}.\n\n' + text
    )
    reply = claude_call("disposition", prompt, repo, out, model="sonnet")
    parsed = last_json_object(reply, ("fix", "ask", "nit"))
    if parsed is None:
        raise ValueError(f'the disposition reply holds no {{"fix": [..], "ask": [..], "nit": [..]}} object: {reply!r}')
    return {"fix": parsed.get("fix", []), "ask": parsed.get("ask", []), "nit": parsed.get("nit", []), "assessment": ""}


CODE_TOKEN = re.compile(r"`([^`]+)`")


def identifiers(finding):
    """Backticked names in a finding that are neither a file path nor a file:line pointer."""
    names = set()
    for token in CODE_TOKEN.findall(finding):
        if "/" in token or re.search(r":\d", token) or (re.search(r"\.\w{1,4}$", token) and "(" not in token):
            continue
        names.add(token)
    return names


def merge_findings(findings):
    """One list for the coder: a finding that names the same file and a shared identifier as an earlier one is
    folded into it."""
    merged = []
    for finding in findings:
        path = finding_file(finding)[0]
        names = identifiers(finding)
        home = next((index for index, kept in enumerate(merged)
                     if finding_file(kept)[0] == path and names & identifiers(kept) and path), None)
        if home is None:
            merged.append(finding)
        else:
            merged[home] += f" Also reported: {finding}"
    return merged


FINDING_FILE = re.compile(r"([\w./-]+\.\w+):(\d+)")


def finding_file(line):
    match = FINDING_FILE.search(line)
    return (match.group(1), int(match.group(2))) if match else ("", 0)


def finding_class(line):
    """The class the reviewer tagged the finding with, which the tag rule puts right after the file:line; `other` when
    it tagged none."""
    located = FINDING_FILE.search(line)
    match = FINDING_CLASS_TAG.search(line, located.end() if located else 0) or FINDING_CLASS_TAG.search(line)
    return match.group(1).lower() if match else "other"


def finding_title(line):
    """The finding's text with its file:line and bracketed tags taken out, lowercased, punctuation folded to spaces.
    A refile keeps it when the coder's edit moves the line."""
    title = re.sub(r"`?" + FINDING_FILE.pattern + r"`?", " ", line)
    title = re.sub(r"\[[\w-]+\]", " ", title)
    return re.sub(r"\W+", " ", title).strip().lower()


def coder_prompt(repo, findings, small_items, files, gate_env=()):
    body = [f"Repo root: {repo}", "", FENCE, "", "## Issues", ""]
    body += [f"{index}. {finding}" for index, finding in enumerate(findings, 1)]
    body += ["", "For each issue you skip, write one line in your report in the form `SKIPPED <n>: <reason>`, "
                 "where n is the issue number above."]
    if small_items:
        body += ["", "## Small items", "", SMALL_ITEMS, ""] + [f"- {item}" for item in small_items]
    body += ["", "Files in scope: " + ", ".join(files)]
    gate_env_text = plan_format.gate_env_text(list(gate_env))
    if gate_env_text:
        body += ["", gate_env_text]
    return "\n".join(body)


def check_command_for(repo, out):
    """The repo's full check: a CLAUDE.md `Quality check: \\`<command>\\`` line, else what a haiku call reads from the
    repo's docs, task runners and CI config. None when CI runs the repo's full suite or the finder names no check:
    full_check.run then runs nothing."""
    if full_check.full_suite_runs_in_ci(repo):
        return None

    claude_md = pathlib.Path(repo) / "CLAUDE.md"
    text = claude_md.read_text() if claude_md.is_file() else ""
    match = re.search(r"^\s*[-*]?\s*Quality check:\s*`([^`]+)`", text, re.I | re.M)
    if match:
        return match.group(1)

    reply = claude_call("check-finder", CHECK_FINDER.format(repo=repo), repo, out, model="haiku",
                        tools="Read,Glob,Grep")
    parsed = last_json_object(reply, ("command", "reason"))
    if parsed is not None:
        command = parsed.get("command")
        if isinstance(command, str) and command.strip():
            return command.strip()
        print(f"review-loop-script: no full check found in {repo}: "
              f"{parsed.get('reason') or 'the check finder named none'}", file=sys.stderr)
        return None
    raise ValueError(f'the check-finder reply holds no {{"command": ..}} object: {reply!r}')


def run_full_check(repo, out, check_command, gate_env=()):
    """(the full_check result, the log's last lines with the failing tests above them, the run's details: runner
    summaries and the files the check changed or created). A SIGTERM kills the check's process group with the claude
    calls."""
    assignments = script_utils.environment_from_assignments(gate_env)
    check_pids = []

    def check_started(pid):
        check_pids.append(pid)
        LIVE_CHILDREN.add(pid)

    try:
        return full_check.run(repo, check_command, out / "full-check.log", CHECK_TIMEOUT_SECONDS,
                              env={**os.environ, **assignments}, on_start=check_started)
    finally:
        LIVE_CHILDREN.difference_update(check_pids)


def file_texts(repo):
    texts = {}
    for path in scope(repo):
        target = pathlib.Path(repo) / path
        if target.is_file():
            texts[path] = target.read_text(errors="replace")
    return texts


def added_source_lines(diffs):
    """Lines the given unified diffs add to non-test source files."""
    total, source = 0, False
    for diff in diffs:
        for line in diff.splitlines():
            if line.startswith("+++ b/"):
                source = counts_toward_size(line[6:])
            elif line.startswith("+") and source:
                total += 1
    return total


class CoderCallError(RuntimeError):
    """A coder call that failed after it may have edited the tree. `changed` lists the paths whose text differs."""

    def __init__(self, message, changed):
        super().__init__(message)
        self.changed = changed


def changed_paths(before, after):
    """The sorted paths whose text differs between two file_texts snapshots; a missing path reads as empty text."""
    return sorted(path for path in set(before) | set(after) if before.get(path, "") != after.get(path, ""))


def coder_call(role, prompt, repo, out):
    """The fix coder. Returns (report, diffs, changed): the diffs of what it changed feed the round-two brief, and
    the global FIX_DIFFS feeds the class-closure check; changed lists the paths whose text differs. A failed call
    raises CoderCallError naming the files it changed before it died."""
    before = file_texts(repo)
    try:
        report = claude_call(role, prompt, repo, out, agent="coder")
    except RuntimeError as error:
        after = file_texts(repo)
        changed = changed_paths(before, after)
        if not changed:
            raise
        message = (f"{error}; it changed {', '.join(changed)} before it died, so the tree holds a partial fix "
                   "that may fail its checks")
        raise CoderCallError(message, changed) from error

    after = file_texts(repo)
    start = len(FIX_DIFFS)
    paths = sorted(set(before) | set(after))
    for path in paths:
        old_lines = before.get(path, "").splitlines()
        new_lines = after.get(path, "").splitlines()
        difference = list(difflib.unified_diff(old_lines, new_lines, f"a/{path}", f"b/{path}", n=DIFF_CONTEXT,
                                               lineterm=""))
        if difference:
            FIX_DIFFS.append("\n".join(difference))
    changed = changed_paths(before, after)
    return report, FIX_DIFFS[start:], changed


def closure_check(repo, out, fixed):
    if not fixed:
        return {"receipt": NO_CLOSURE, "open": []}
    prompt = (
        f"Repo root: {repo}\n\n{CLOSURE_RULES}\n\nfixed[]:\n" + "\n".join(f"- {item}" for item in fixed)
        + "\n\nThe fix diff (what the coder changed, with surrounding context):\n" + "\n\n".join(FIX_DIFFS)
        + '\n\nEnd your reply with one JSON object: {"receipt": "<the enumeration, or none plus each fixed finding '
        'and why it fits neither shape>", '
        '"open": ["<file:line - defect - correction>", ...]}. "open" is empty when every class is closed.'
    )
    reply = claude_call("class-closure", prompt, repo, out, model="sonnet", tools="Read,Grep")
    parsed = last_json_object(reply, ("open",))
    if parsed is not None:
        parsed_open = parsed.get("open")
        open_findings = ([item for item in parsed_open if isinstance(item, str) and item.strip()]
                         if isinstance(parsed_open, list) else [])
        return {"receipt": str(parsed.get("receipt", "")), "open": open_findings}
    raise ValueError(f'the class-closure reply holds no {{"receipt": .., "open": [..]}} object: {reply!r}')


def skipped_issues(report, issue_count):
    """Issue number -> the coder's `SKIPPED <n>: <reason>` line, for numbers that name a listed issue."""
    skips = {}
    for line in report.splitlines():
        match = re.match(r"\s*[-*]?\s*`?SKIPPED (\d+):", line)
        if match and 1 <= int(match.group(1)) <= issue_count:
            skips.setdefault(int(match.group(1)), line.strip())
    return skips


# ---------- prompt file ----------

def read_prompt(path):
    """({header key: value}, handoff block) of the review prompt file. The header ends at the first blank line."""
    header_text, _separator, handoff = pathlib.Path(path).read_text().partition("\n\n")
    header = {}
    for line in header_text.splitlines():
        key, separator, value = line.partition(":")
        if separator:
            header[key.strip()] = value.strip()
    if not header.get("lane"):
        raise ValueError(f"the prompt file {path} has no lane line")
    return header, handoff.strip()


def reviewer_brief(header, handoff):
    lines = [f"{key}: {header[key]}" for key in ("plan", "phase") if header.get(key)]
    lines += ["Handoff:", handoff]
    return "\n".join(lines)


# ---------- telemetry ----------

def log_call(repo, command):
    """(exit code, output) of a skill logger; a logger that cannot run is (1, "")."""
    try:
        code, output = script_utils.run_command(command, repo, timeout=LOG_TIMEOUT_SECONDS)
    except OSError as error:
        key = f"{pathlib.Path(command[0]).name} {command[1]}"
        print(f"review-loop-script: {key} could not run: {error}", file=sys.stderr)
        return 1, ""

    if code != 0:
        key = f"{pathlib.Path(command[0]).name} {command[1]}"
        print(f"review-loop-script: {key} exited {code}: {output}", file=sys.stderr)
    return code, output


def stable_finding_id(session, lane, scope_fields, gate, spot):
    """The ledger id of one finding. The same reviewer filing the same finding again, in a later round or a rerun of
    this review, gets the same id, so its row supersedes the earlier one instead of adding a second. The spot is the
    file and the finding's title plus a `#n` ordinal among same-title findings in that file; the line is left out, so a
    finding whose line moved keeps its id."""
    key = "\0".join([session, lane, *scope_fields, gate, spot])
    return hashlib.sha256(key.encode()).hexdigest()[:handback.FINDING_ID_HEX_LEN]


def new_spot(path, title, entries):
    """The spot of a new finding: the file and title with the lowest `#n` ordinal no entry holds. A refile rewrites an
    earlier entry's title but keeps its spot, so the ordinal is checked against spots, not titles."""
    taken = {entry["spot"] for entry in entries}
    number = 1
    while f"{path}\0{title}#{number}" in taken:
        number += 1
    return f"{path}\0{title}#{number}"


def telemetry(repo, session, lane, scope_fields, iter_count, tallies, run_rows):
    """Writes the metrics row, and each run and finding row. Returns ({ask text: finding_id}, ask_rows): the id that
    log-review-finding printed for each ask row, and the {file, line, finding_id} entries the stop row carries."""
    log_call(repo, [str(SKILLS / "log-review-metrics"), f"lane={lane}", f"iter={iter_count}", f"fix={tallies['fix']}",
                    f"ask={tallies['ask']}", f"nit={tallies['nit']}", f"blocker={tallies['blocker']}",
                    f"fixed={tallies['fixed']}", f"skipped_fp={tallies['skipped_fp']}", "test_intent_ran=0",
                    "culled=0", "comment_noise=0", f"smells={tallies['smells']}", f"result={tallies['result']}"])
    logger = str(SKILLS / "log-review-finding")
    ask_ids, ask_rows = {}, []
    for row in run_rows:
        log_call(repo, [logger, "kind=run", f"lane={lane}", *scope_fields, f"iter={row['iter']}",
                        f"gate={row['gate']}", f"n_findings={len(row['findings'])}", f"diff_loc={row['loc']}",
                        f"result={row['result']}"])
        for finding in row["findings"]:
            path, line = finding_file(finding["text"])
            location = [f"file={path}", f"line={line}"] if path else [f"file={UNLOCATED}"]
            finding_id = stable_finding_id(session, lane, scope_fields, row["gate"], finding["spot"])
            command = [logger, "kind=finding", f"finding_id={finding_id}", f"lane={lane}", *scope_fields,
                       f"iter={row['iter']}", f"gate={row['gate']}", f"disposition={finding['disposition']}",
                       f"class={finding_class(finding['text'])}", *location, f"actioned={finding['actioned']}"]
            if finding["disposition"] == "fix":
                command.append(f"source={finding['source']}")
            code, output = log_call(repo, command)
            printed_ids = handback.PRINTED_FINDING_ID.findall(output)
            if finding["disposition"] == "ask" and code == 0 and printed_ids:
                ask_ids.setdefault(finding["text"], printed_ids[0])
                ask_rows.append({"file": path or UNLOCATED, "line": line, "finding_id": printed_ids[0]})
    return ask_ids, ask_rows


# ---------- the loop ----------

def tally_review(tallies, findings, assessment):
    """Adds one review's new findings ({disposition: [texts]}) to the metrics tallies, so a finding refiled in a later
    round counts once."""
    tallies["fix"] += len(findings["fix"])
    tallies["ask"] += len(findings["ask"])
    tallies["nit"] += len(findings["nit"])
    tallies["blocker"] += sum("[blocker]" in item.lower() for item in findings["fix"])
    every_finding = findings["fix"] + findings["ask"] + findings["nit"]
    tallies["smells"] += sum(finding_class(item) == "smell" for item in every_finding)
    if assessment == "NEEDS CHANGES":
        tallies["result"] = "NEEDS CHANGES"
    elif assessment and tallies["result"] == "PASS":
        tallies["result"] = assessment


def prior_issue_entries(round_findings, skips):
    """The round's findings as the next reviewers' prior issues: fixed, or skipped with the coder's reason."""
    entries = []
    for number, item in enumerate(round_findings, 1):
        entry = {"issue": item, "status": "skipped" if number in skips else "fixed",
                 "file": finding_file(item)[0] or "unknown"}
        if number in skips:
            entry["reason"] = skips[number]
        entries.append(entry)
    return entries


class LoopRun:
    """The state one review loop builds up round by round. `progress` holds what a crash still reports: iter, fixed
    and files_touched, updated in place as the loop goes."""

    def __init__(self, repo, out, brief, gate_env, progress):
        self.repo, self.out, self.brief, self.gate_env = repo, out, brief, gate_env
        self.progress = progress
        self.fixed, self.files_touched = progress["fixed"], progress["files_touched"]
        self.iter_count = 0
        self.skipped_fp, self.remaining, self.asks, self.nits, self.run_rows = [], [], [], [], []
        self.ask_gates = {}
        self.tallies = {"fix": 0, "ask": 0, "nit": 0, "blocker": 0, "fixed": 0, "skipped_fp": 0, "smells": 0,
                        "result": "PASS"}
        self.prior_issues = []
        self.status = "converged"
        self.class_closure = NO_CLOSURE
        self.full_check = ""
        self.full_check_command = ""
        self.check_details = {"summaries": [], **{kind: [] for kind in CHANGE_KINDS}}
        self.round_two_fix_diff_path = ""
        self.files = {}
        self.dispatches = []
        self.filed = {}  # {(reviewer, file): [finding entries]}, so a refiled finding updates its first row
        self.round_claimed = set()  # ids of the entries this round filed or refiled, so no two reports share one
        self.round_fixes = []  # the fix entries this round's reviewers filed, for fix_round to mark
        self.check_fixed = 0  # findings the full check and the class closure fixed, which file no finding row
        self.last_pass = ""

    def next_round(self):
        self.iter_count += 1
        self.progress["iter"] = self.iter_count

    def stop(self, status, remaining):
        self.status = status
        self.remaining = remaining

    def review_one(self, dispatch):
        agent, owned = dispatch
        prompt = reviewer_prompt(self.repo, agent, owned, self.prior_issues, self.round_two_fix_diff_path,
                                 tuple(self.asks), self.brief)
        text = claude_call(f"review{self.iter_count}-{agent}", prompt, self.repo, self.out, agent=agent)
        return parse_review(text) or disposition_call(text, self.repo, self.out)

    def earlier_filing(self, entries, finding):
        """The entry from an earlier round that this finding refiles: not yet claimed this round, with the same
        disposition and a near title. None when it is new."""
        return next((entry for entry in entries if id(entry) not in self.round_claimed
                     and entry["disposition"] == finding["disposition"]
                     and script_utils.text_similarity(entry["title"], finding["title"]) >= REFILE_SIMILARITY), None)

    def filing_row(self, agent, owned, parsed, fixes, design):
        """The run row of one review. A fix starts `actioned: none`; fix_round sets it once the coder returns. A
        finding this reviewer filed in an earlier round, in the same file with the same disposition and the same or
        near title, updates that round's entry and stays off this row, wherever its line moved."""
        reported = [{"text": item, "disposition": "fix", "actioned": "none", "source": "round"} for item in fixes]
        reported += [{"text": item, "disposition": "ask", "actioned": "ask", "source": ""}
                     for item in parsed["ask"] + design]
        reported += [{"text": item, "disposition": "nit", "actioned": "none", "source": ""} for item in parsed["nit"]]

        findings = []
        for finding in reported:
            path = finding_file(finding["text"])[0] or UNLOCATED
            finding["title"] = finding_title(finding["text"])
            entries = self.filed.setdefault((agent, path), [])
            earlier = self.earlier_filing(entries, finding)
            if earlier:
                finding["spot"] = earlier["spot"]
                if finding["disposition"] == "ask":
                    finding["text"] = earlier["text"]
                earlier.update(finding)
                finding = earlier
            else:
                finding["spot"] = new_spot(path, finding["title"], entries)
                entries.append(finding)
                findings.append(finding)
            self.round_claimed.add(id(finding))
            if finding["disposition"] == "fix":
                self.round_fixes.append(finding)

        loc = sum(self.files[path][0] for path in owned if path in self.files)
        return {"iter": self.iter_count, "gate": agent, "loc": loc, "result": parsed["assessment"] or "PASS",
                "findings": findings}

    def review_round(self):
        """Runs the round's reviewers in parallel and sorts their findings. Returns (round_fix, round_nits). A
        plan-change ask stops the loop and leaves the reviews after it unread."""
        with ThreadPoolExecutor(max_workers=len(self.dispatches)) as pool:
            reviews = list(pool.map(self.review_one, self.dispatches))
        self.last_pass = "reviewer"

        self.round_claimed, self.round_fixes = set(), []
        round_fix, round_nits = [], []
        for (agent, owned), parsed in zip(self.dispatches, reviews, strict=True):
            design = [item for item in parsed["fix"] if "[design-decision]" in item.lower()]
            fixes = [item for item in parsed["fix"] if item not in design]

            plan_changes = [item for item in parsed["ask"] if PLAN_CHANGE_MARK.match(item)]
            if plan_changes:
                tally_review(self.tallies, {"fix": fixes, "ask": parsed["ask"] + design, "nit": parsed["nit"]},
                             parsed["assessment"])
                self.stop("plan-change", plan_changes)
                break

            row = self.filing_row(agent, owned, parsed, fixes, design)
            new_findings = {disposition: [finding["text"] for finding in row["findings"]
                                          if finding["disposition"] == disposition]
                            for disposition in ("fix", "ask", "nit")}
            tally_review(self.tallies, new_findings, parsed["assessment"])
            self.asks += new_findings["ask"]
            self.ask_gates.update(dict.fromkeys(new_findings["ask"], agent))
            round_nits += parsed["nit"]
            round_fix.append((agent, fixes))
            self.run_rows.append(row)
        return round_fix, round_nits

    def repair(self, call_name, findings, nits=()):
        """One coder pass on the findings. Returns (report, diffs, changed files)."""
        before = scope(self.repo)
        prompt = coder_prompt(self.repo, findings, list(nits), list(before), self.gate_env)
        self.last_pass = "coder"
        try:
            return coder_call(call_name, prompt, self.repo, self.out)
        except CoderCallError as error:
            self.files_touched.update(error.changed)
            raise

    def fix_round(self, round_fix, round_nits):
        """The coder pass on the round's merged fixes, and the plan for the next round. Returns False when the loop
        ends here."""
        round_findings = merge_findings([item for _agent, fixes in round_fix for item in fixes])
        if not round_findings:
            self.nits += round_nits
            return False

        report, coder_diffs, changed = self.repair(f"coder{self.iter_count}", round_findings, round_nits)
        if PLAN_CHANGE_YES.search(report.strip()):
            self.stop("plan-change", [report.strip()])
            return False

        skips = skipped_issues(report, len(round_findings))
        self.skipped_fp += [{"item": round_findings[number - 1], "reason": line}
                            for number, line in sorted(skips.items())]
        skipped_findings = [round_findings[number - 1] for number in sorted(skips)]
        for finding in self.round_fixes:
            skipped = any(finding["text"] in item for item in skipped_findings)
            finding["actioned"] = "skipped_fp" if skipped else "fixed"
        self.fixed += [item for item in round_findings if item not in skipped_findings]
        self.files_touched.update(changed)
        self.prior_issues = prior_issue_entries(round_findings, skips)

        self.files = scope(self.repo)
        if self.iter_count < ROUND_BUDGET:
            fix_diff_file = self.out / f"round{self.iter_count}-fix.diff"
            fix_diff_file.write_text("\n\n".join(coder_diffs))
            self.round_two_fix_diff_path = str(fix_diff_file)
            self.dispatches = second_round_plan(round_fix, changed, skipped_findings, coder_diffs)
        return not (changed and all(path.endswith(".md") for path in changed))

    def full_check_pass(self, check_command):
        """The full check, with one coder repair when it fails outside a spec file. A check that did not run, in CI
        or past its time limit, and one that exited 0 with no runner summary, is no failure and gets no repair; one the
        environment could not run stops as `setup-fault`."""
        tail = self.run_check(check_command)
        if full_check.is_setup_fault_result(self.full_check):
            self.stop_on_setup_fault(check_command, tail)
            return

        if not full_check.is_failure(self.full_check):
            return

        gate_findings = [f"full check failed (`{check_command}`), failing lines:\n{tail}"]
        if re.search(r"\.spec\.", tail):
            self.stop("critical-blocker", gate_findings)
            return

        _report, _diffs, gate_changed = self.repair("coder-gate", gate_findings)
        self.fixed += gate_findings
        self.check_fixed += len(gate_findings)
        self.files_touched.update(gate_changed)
        self.recheck_full_check(check_command, "full check still failing after one repair")

    def run_check(self, check_command):
        """Run the full check, keep its result, command and details for the packet. Returns the log's tail.
        The changed, rewrote_edited and created paths add up across runs; the summaries are the latest run's. The
        check leaves the files it rewrote or created in place, and a repair measures its changes as the text
        difference around its own call, so a changed or created file reaches files_touched only when the repair coder
        edits it itself. A rewrote_edited file holds coder work and always counts as touched."""
        self.full_check_command = check_command or ""
        self.full_check, tail, details = run_full_check(self.repo, self.out, check_command, self.gate_env)
        check_wrote = set(self.check_details["changed"]) | set(self.check_details["created"])
        details["rewrote_edited"] = [path for path in details["rewrote_edited"]
                                     if path not in check_wrote or path in self.files_touched]
        for key in CHANGE_KINDS:
            details[key] = sorted(set(self.check_details[key]) | set(details[key]))
        details["rewrote_edited"] = sorted(set(details["rewrote_edited"])
                                           | ((set(details["changed"]) | set(details["created"])) & self.files_touched))
        for key in ("changed", "created"):
            details[key] = [path for path in details[key] if path not in details["rewrote_edited"]]
        self.check_details = details
        return tail

    def recheck_full_check(self, check_command, failure_heading):
        """The full check after a coder repair: a setup fault stops as `setup-fault`, any other failure as
        `critical-blocker`."""
        tail = self.run_check(check_command)
        if full_check.is_setup_fault_result(self.full_check):
            self.stop_on_setup_fault(check_command, tail)
        elif full_check.is_failure(self.full_check):
            self.stop("critical-blocker", [f"{failure_heading}:\n{tail}"])

    def stop_on_setup_fault(self, check_command, tail):
        """The full check could not run here, which no coder repair changes: stop for the user."""
        self.stop("setup-fault", [f"the full check could not run in this environment (`{check_command}`), full "
                                  f"log {self.out / 'full-check.log'}, last lines:\n{tail}"])

    def class_closure_pass(self, check_command):
        """The class-closure judgment on the fixes, and one coder pass with a full check on any class left open."""
        closure = closure_check(self.repo, self.out, self.fixed)
        self.class_closure = closure["receipt"]
        if not closure["open"]:
            return

        _report, _diffs, class_changed = self.repair("coder-class", closure["open"])
        self.fixed += closure["open"]
        self.check_fixed += len(closure["open"])
        self.files_touched.update(class_changed)
        self.next_round()
        self.recheck_full_check(check_command, "full check failing after the class repair")

    def outcome(self, ask_ids, ask_rows):
        return {
            "status": self.status,
            "iter": self.iter_count,
            "fixed": self.fixed,
            "skipped_fp": self.skipped_fp,
            "blockers": self.remaining if self.status in handback.BLOCKER_STATUSES else [],
            "plan_change": self.remaining if self.status == "plan-change" else [],
            "asks": self.asks,
            "ask_gates": self.ask_gates,
            "ask_ids": ask_ids,
            "ask_rows": ask_rows,
            "class_closure": self.class_closure,
            "full_check": self.full_check,
            "full_check_command": self.full_check_command,
            "full_check_summaries": self.check_details["summaries"],
            "check_changed": self.check_details["changed"],
            "check_rewrote_edited": self.check_details["rewrote_edited"],
            "check_created": self.check_details["created"],
            "files_touched": sorted(self.files_touched | set(self.check_details["rewrote_edited"])),
            "nits": self.nits,
            "unreviewed_fix": self.last_pass == "coder",
        }


def run_loop(repo, out, session, header, handoff, progress):
    """Walks the graph. Returns the outcome mapping. `progress` holds what a crash still reports: iter, fixed and
    files_touched, updated in place as the loop goes."""
    lane = header["lane"]
    structure_pass_skipped = header.get("structure-pass") == "skip"
    brief = reviewer_brief(header, handoff)
    gate_env = plan_format.gate_env_words_in(handoff)
    scope_fields = ["scope=phase"] + ([f"phase={header['phase']}"] if header.get("phase") else [])
    loop = LoopRun(repo, out, brief, gate_env, progress)

    log_call(repo, [str(SKILLS / "review-scope"), "caller=code"])
    check_command = check_command_for(repo, out)

    loop.files = scope(repo)
    loop.dispatches = first_round_plan(loop.files, structure_pass_skipped)
    while loop.iter_count < ROUND_BUDGET and loop.dispatches:
        loop.next_round()
        round_fix, round_nits = loop.review_round()
        if loop.status == "plan-change":
            break
        if not loop.fix_round(round_fix, round_nits):
            break

    if loop.status == "converged":
        loop.full_check_pass(check_command)
    if loop.status == "converged":
        loop.class_closure_pass(check_command)

    every_actioned = [finding["actioned"] for row in loop.run_rows for finding in row["findings"]]
    loop.tallies["fixed"] = every_actioned.count("fixed") + loop.check_fixed
    loop.tallies["skipped_fp"] = every_actioned.count("skipped_fp")
    ask_ids, ask_rows = telemetry(repo, session, lane, scope_fields, loop.iter_count, loop.tallies, loop.run_rows)
    return loop.outcome(ask_ids, ask_rows)


# ---------- hand-back packet ----------

def located(text):
    """The packet's file_line for a finding text: the `path:line` the driver parses, or UNLOCATED."""
    path, line = finding_file(text)
    return f"{path}:{line}" if path else UNLOCATED


def finding_entry(text):
    return {"finding": text, "file_line": located(text)}


def ask_entry(text, gate, finding_id):
    # The text before the last `change:` marker is the question; the text after it is the edit an accepted answer
    # makes. An ask with no marker carries its own recommended edit, so its whole text is both.
    question, change = text, text
    change_marks = list(ASK_CHANGE_MARK.finditer(text))
    if change_marks:
        last_mark = change_marks[-1]
        question = text[:last_mark.start()].rstrip(" —-")
        change = text[last_mark.end():].strip()

    entry = {"question": question, "file_line": located(text), "change": change, "gate": gate,
             "class": finding_class(text)}
    if finding_id:
        entry["finding_id"] = finding_id
    return entry


def packet_message(outcome):
    """The outcome in the packet grammar handback.py reads: one `key: value` line per field, list fields as JSON."""
    status = "plan-impact" if outcome["status"] == "plan-change" else outcome["status"]
    asks = [ask_entry(text, outcome["ask_gates"].get(text, handback.DEFAULT_GATE), outcome["ask_ids"].get(text))
            for text in outcome["asks"]]
    fields = {
        "status": status,
        "iter": outcome["iter"],
        "fixed": [finding_entry(text) for text in outcome["fixed"]],
        "skipped_fp": [{"item": entry["item"], "reason": entry["reason"], "file_line": located(entry["item"])}
                       for entry in outcome["skipped_fp"]],
        "blockers": outcome["blockers"],
        "findings_remaining": [],
        "ask": asks,
        "class_closure": script_utils.one_line(outcome["class_closure"], limit=None),
        "files_touched": outcome["files_touched"],
        "nit": [finding_entry(text) for text in outcome["nits"]],
    }
    if outcome["full_check"]:
        fields["full_check"] = outcome["full_check"]
        if outcome["full_check_command"]:
            fields["full_check_command"] = script_utils.one_line(outcome["full_check_command"], limit=None)
        summary = full_check.summary_text(outcome["full_check"], outcome["full_check_summaries"])
        if summary is not None:
            fields["full_check_summary"] = script_utils.one_line(summary, limit=None)
    if outcome["check_changed"]:
        fields["check_changed"] = outcome["check_changed"]
    if outcome["check_rewrote_edited"]:
        fields["check_rewrote_edited"] = outcome["check_rewrote_edited"]
    if outcome["check_created"]:
        fields["check_created"] = outcome["check_created"]
    if outcome.get("tool_fault"):
        fields["tool_fault"] = outcome["tool_fault"]
    if outcome["plan_change"]:
        fields["plan_impact"] = script_utils.one_line("; ".join(outcome["plan_change"]), limit=None)
    lines = []
    for key, value in fields.items():
        lines.append(f"{key}: {value if isinstance(value, str | int) else json.dumps(value)}")
    return "\n".join(lines)


def crash_outcome(progress, reason):
    # A crash is a tool fault, not a finding: tool_fault tells code_step to offer review-again.
    fixed = [item for item in progress["fixed"] if isinstance(item, str) and item.strip()]
    return {"status": "critical-blocker", "iter": progress["iter"], "fixed": fixed,
            "skipped_fp": [], "blockers": [reason], "plan_change": [], "asks": [],
            "ask_gates": {}, "ask_ids": {}, "ask_rows": [], "class_closure": "none - the run ended in an error",
            "full_check": "", "full_check_command": "", "full_check_summaries": [], "check_changed": [],
            "check_rewrote_edited": [], "check_created": [],
            "files_touched": sorted(progress["files_touched"]), "nits": [],
            "unreviewed_fix": False, "tool_fault": reason}


# ---------- hand-back rows ----------

def report_write_failure(what, error):
    print(f"review-loop-script: {what} not written, {type(error).__name__}: {error}", file=sys.stderr)


def write_handback_rows(repo, args, message, status, ask_rows, unreviewed_fix):
    # The driver's skipped re-reviews are its benched routes, so a clean row never sets no_reviewer;
    # a coder pass after the last reviewer round sets unreviewed_fix.
    try:
        code_step_core.log_event(repo, args.run_id, "handback", args.session, agent_id=args.agent_id,
                                 agent_type=handback.REVIEW_LOOP, message=message)
    except Exception as error:
        report_write_failure("run event", error)
    try:
        handback.record(args.session, "handback", agent_id=args.agent_id, status=status, problems=[], message=message,
                        no_reviewer=False, unreviewed_fix=unreviewed_fix and status in handback.CLEAN_STATUSES)
    except Exception as error:
        report_write_failure("hand-back row", error)
    review_loop_gate.record_stop({"session_id": args.session, "agent_id": args.agent_id}, 0, ask_rows)

    # The /code run that launched this loop can end before the loop hands back, and then nothing marks the gate. So
    # the loop records the tree it ended clean on itself, under the same rule as `review-gate-mark clean`.
    try:
        if handback.false_clean_reason(args.session) is None:
            reviewed_tree.record_reviewed(args.session, repo)
    except Exception as error:
        report_write_failure("reviewed tree", error)


def write_usage_row(repo, started):
    if not script_utils.telemetry_switch_on():
        return
    usage_file = os.environ.get("AGENT_USAGE_FILE") or pathlib.Path.home() / ".claude" / "agent-usage.jsonl"
    finished_calls = [call for call in CALLS if call]
    row = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "repo": pathlib.Path(repo).name,
        "agent": handback.REVIEW_LOOP,
        "model": "script",
        "desc": "scripted review loop",
        "tokens": sum(call["tokens"] for call in finished_calls),
        "toolUses": None,
        "durationMs": round((now() - started) * 1000),
        "reportChars": None,
        "noResult": None,
        "respKeys": [],
        "driver": "script",
        "calls": len(finished_calls),
    }
    try:
        script_utils.append_jsonl(usage_file, row)
    except OSError as error:
        report_write_failure("agent-usage row", error)


# ---------- main ----------

def stop_on_sigterm(_signal_number, _frame):
    """The stop signal of an abort, a review-again or a start --restart: kill the process group of every claude call
    that is running, then exit without a packet."""
    for pid in list(LIVE_CHILDREN):
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(pid, signal.SIGKILL)
    os._exit(128 + signal.SIGTERM)


def parse_review_loop_arguments(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("repo")
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--prompt-file", required=True)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_review_loop_arguments(argv)
    signal.signal(signal.SIGTERM, stop_on_sigterm)
    repo = str(pathlib.Path(args.repo).resolve())
    out = pathlib.Path(args.state_dir) / "loop-script" / args.agent_id
    out.mkdir(parents=True, exist_ok=True)
    started = now()
    progress = {"iter": 0, "fixed": [], "files_touched": set()}

    exit_code = 0
    outcome = None
    try:
        header, handoff = read_prompt(args.prompt_file)
        outcome = run_loop(repo, out, args.session, header, handoff, progress)
        message = packet_message(outcome)
        handback.load(message)
    except handback.PacketError as error:
        problems = "; ".join(error.problems)
        print(f"review-loop-script: the packet does not parse: {problems}", file=sys.stderr)
        reason = f"the review loop packet failed validation ({problems}); call log: {out / 'calls.jsonl'}"
        outcome = {**crash_outcome(progress, reason), "ask_rows": outcome["ask_rows"]}
        message = packet_message(outcome)
        exit_code = 1
    except Exception as error:
        print(f"review-loop-script: {type(error).__name__}: {error}", file=sys.stderr)
        reason = script_utils.one_line(f"the review loop script failed with {type(error).__name__}: {error}; "
                                       f"call log: {out / 'calls.jsonl'}", limit=None)
        outcome = crash_outcome(progress, reason)
        message = packet_message(outcome)
        exit_code = 1

    status = handback.load(message)["status"]
    (out / "packet.txt").write_text(message + "\n")
    write_handback_rows(repo, args, message, status, outcome["ask_rows"], outcome["unreviewed_fix"])
    write_usage_row(repo, started)
    print(message)
    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
