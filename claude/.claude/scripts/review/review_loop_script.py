#!/usr/bin/env python3
"""The scripted review loop: the walking between steps is code, the judgment inside each step is a model call.

    review_loop_script.py <repo> --state-dir <dir> --session <id> --run-id <id> --agent-id <id> --prompt-file <path>

The prompt file is the review prompt of a review-first dispatch: header lines (mode, caller, lane, plan, phase, an
optional `structure-pass: skip`), a blank line, then the handoff block. The script walks review-loop.md's fixed graph:
scope, first-round reviewers (code, plus smell and test reviewers on a large diff), disposition routing, one fix coder,
re-review by every reviewer that filed a fix and owns a changed file (the smell reviewer only past the size bar), the
two-round cap, the full-check execution gate, the class-closure check, telemetry rows, and the hand-back packet.
The full check runs through full_check.py. In a repo whose CLAUDE.md holds `Full suite: CI`, where the coder
calls run the changed files' tests, it runs only the `Quality check:` command; a run with no runner summary is
`passed (check only; CI runs the full suite)`; it runs none in a repo where no check is found. A check past
full_check_gate.CHECK_TIMEOUT_SECONDS is killed with its process
group, and a check whose step stops on a missing path is a check-command error. A check that fails on a missing
module the repo declares as a dependency is an environment gap. None is a failure: the packet's `full_check` says
`not run (CI)`, `not run (no check found; ...)`, `not run (timeout)`,
`not run (check-command error: ...)`, `not run (environment gap: ...)`, `not run (scoped command: ...)`,
`not run (unresolved command: ...)` or, when the phase's Expected red lines leave out the whole check,
`not run (expected red until Phase <id>[, <id>...])`. An exit 0 with no runner summary is no
failure either: it says `unverified (exit 0, no runner summary)`. So is a failure that the check shows the same way
on HEAD without the diff: it says `pre-existing failure (...)` and did not verify the diff. To tell, a failed check is
rerun once per loop (the base run) in a detached worktree of HEAD, up to full_check_gate.CHECK_TIMEOUT_SECONDS. A
failed check's blocker holds the failing step's lines; after a repair coder, before recheck_full_check stops as a
blocker, the autofix formatters run on the touched files and the check reruns once if one changed a file.

Model steps are `claude -p` calls in auto permission mode, each named `child of <parent session> (<role>)` so
ListAgents tells it from a worker, and each with CLAUDE_FORMAT_HOOK_OFF=1 in its environment: the
reviewers (agents code-reviewer, smell-reviewer, test-reviewer), the fix coder (agent coder) and the class-closure
judgment (Sonnet). When the repo CLAUDE.md names no `Quality check` line and no full check has passed there, a Haiku
check-finder call names the full check; when it names none, the review runs with no full check. A Sonnet
disposition call runs only when a reviewer's output has no Fix/Ask/Nit sections the parser can read. Every call is
logged to <state dir>/loop-script/<agent id>/calls.jsonl with its session id, role, wall time and token counts.

On finish, or on any uncaught error, the script validates its packet with handback.load, then appends the rows the
review-loop agent leaves: the run event of a hand-back, the hand-back store row, the stop row, and, when the telemetry
switch is on, one agent-usage row. Exit 0 on a normal finish; exit 1 when the run crashed or the packet failed
validation (a critical-blocker packet and the rows are still written). A SIGTERM (abort, review-again, start
--restart) kills every running claude call and exits 143 with no packet and no rows.

review_loop_findings.py reads the reviewers' text; review_loop_closure.py runs the class-closure check;
review_loop_packet.py writes the packet and the hand-back rows.

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
# The file in the loop's state folder that holds the whole output of a red scoped test run.
SCOPED_TESTS_LOG = "scoped-tests.log"
sys.path[:0] = [str(SCRIPT_DIR.parent / folder) for folder in (".", "review", "code", "lib", "telemetry")]
import code_step_core
import coder_gate
import full_check
import full_check_gate
import handback
import loop_transcript
import plan_format
import script_utils
import source_paths
import worktree_snapshot
from finding_record import parse_finding
from review_loop_closure import FIX_DIFF_STATS, NO_CLOSURE, closure_check
from review_loop_findings import (
    PLAN_CHANGE_YES,
    UNLOCATED,
    absent_file_split,
    finding_records,
    last_json_object,
    merge_findings,
    near_title,
    parse_review,
    plan_change_items,
    pointer_ask_split,
    reported_again,
    ruled_plan_split,
    still_fixed,
)
from review_loop_packet import crash_outcome, packet_message, write_handback_rows, write_usage_row
from review_loop_prompts import coder_prompt, reviewer_prompt

SKILLS = SCRIPT_DIR.parent.parent / "skills" / "review"
ROUND_BUDGET = 2
LARGE_ADDED_LINES = source_paths.LARGE_ADDED_LINES
SPLIT_FILES = 5
SPLIT_LINES = 300
DIFF_CONTEXT = 12
CALL_TIMEOUT_SECONDS = 1800
LOG_TIMEOUT_SECONDS = 60
TOKEN_FIELDS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
ABSENT_FILE_REASON = "the file is not in the tree"
NO_CHANGE_REASON = "the coder made no change"
TERMINAL_PANE_ENV = ("HERDR_ENV", "HERDR_PANE_ID", "HERDR_SOCKET_PATH", "TUIOS_SOCKET")
CHILD_ENV = {**{name: value for name, value in os.environ.items() if name not in TERMINAL_PANE_ENV},
             "CLAUDE_FORMAT_HOOK_OFF": "1"}

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

CALLS = []
CALLS_LOCK = threading.Lock()
LIVE_CHILDREN = full_check_gate.LIVE_CHILDREN
# The ListAgents label of the session that ran this loop; main() sets it. Each child session's --name carries it.
PARENT_SESSION = {"label": ""}


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
    command = ["claude", "-p", "--output-format", "json", "--permission-mode", "auto",
               "--name", f"child of {PARENT_SESSION['label']} ({role})"]
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
        script_utils.append_jsonl(out / "calls.jsonl", record)

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
    for path, change in worktree_snapshot.working_tree_changes(repo).items():
        status = change["code"].strip()
        files[path] = [change["added"], "??" if status == "??" else status[0]]
    return files


def first_round_plan(files, structure_pass_skipped=False):
    """Which reviewers go out in the first round, and who owns which files."""
    source = [path for path in files if not source_paths.is_test_path(path)]
    tests = [path for path in files if source_paths.is_test_path(path)]
    added = sum(files[path][0] for path in files if source_paths.counts_toward_size(path))
    new_paths = [path for path in source if files[path][1] in ("??", "A")]
    large = source_paths.is_large_change(added, new_paths)

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
        skipped_paths = [fix.path for fix in fixes if any(fix.text in item.text for item in skipped_findings)]
        owned = [path for path in dict.fromkeys(changed + skipped_paths)
                 if path and source_paths.is_test_path(path) == (agent == "test-reviewer")]
        if agent == "smell-reviewer" and not smell_runs:
            continue
        if not owned:
            continue
        dispatches.append((agent, owned))
    return dispatches


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
    return finding_records({"fix": parsed.get("fix", []), "ask": parsed.get("ask", []), "nit": parsed.get("nit", []),
                            "assessment": ""})


def check_command_for(repo, out):
    """The repo's full check: a CLAUDE.md `Quality check: \\`<command>\\`` line, else the check that last passed in the
    repo, else what a haiku call reads from the repo's docs, task runners and CI config. When CI runs the repo's full
    suite, only the `Quality check:` line counts. None when there is no such line in that repo or the finder names no
    check: full_check.run then runs nothing."""
    picked = full_check.picked_check_command(repo)
    if picked or full_check.full_suite_runs_in_ci(repo):
        return picked

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


def file_texts(repo):
    texts = {}
    for path in scope(repo):
        target = pathlib.Path(repo) / path
        if target.is_file():
            texts[path] = target.read_text(errors="replace")
    return texts


def added_source_lines(diffs):
    """Lines the given unified diffs add to files that count toward the size bar (`source_paths.counts_toward_size`)."""
    total, source = 0, False
    for diff in diffs:
        for line in diff.splitlines():
            if line.startswith("+++ b/"):
                source = source_paths.counts_toward_size(line[6:])
            elif line.startswith("+") and source:
                total += 1
    return total


class LaterPhaseEditError(RuntimeError):
    """A coder pass that edited a file the plan gives to a later phase."""


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
    one diff file per changed path under `out` (listed in the global FIX_DIFF_STATS) feeds the class-closure check;
    changed lists the paths whose text differs. A failed call raises CoderCallError naming the files it changed
    before it died."""
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
    diffs = []
    paths = sorted(set(before) | set(after))
    for path in paths:
        old_lines = before.get(path, "").splitlines()
        new_lines = after.get(path, "").splitlines()
        difference = list(difflib.unified_diff(old_lines, new_lines, f"a/{path}", f"b/{path}", n=DIFF_CONTEXT,
                                               lineterm=""))
        if not difference:
            continue
        diff_text = "\n".join(difference)
        diffs.append(diff_text)
        diff_file = out / "fix-diffs" / role / f"{path}.diff"
        diff_file.parent.mkdir(parents=True, exist_ok=True)
        diff_file.write_text(diff_text)
        added = sum(1 for line in difference if line.startswith("+") and not line.startswith("+++"))
        removed = sum(1 for line in difference if line.startswith("-") and not line.startswith("---"))
        FIX_DIFF_STATS.append({"path": path, "added": added, "removed": removed, "diff_file": str(diff_file)})
    changed = changed_paths(before, after)
    return report, diffs, changed


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
    return hashlib.sha256(key.encode()).hexdigest()[:loop_transcript.FINDING_ID_HEX_LEN]


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
            path, line = finding["finding"].path, finding["finding"].line
            location = [f"file={path}", f"line={line}"] if path else [f"file={UNLOCATED}"]
            finding_id = stable_finding_id(session, lane, scope_fields, row["gate"], finding["spot"])
            command = [logger, "kind=finding", f"finding_id={finding_id}", f"lane={lane}", *scope_fields,
                       f"iter={row['iter']}", f"gate={row['gate']}", f"disposition={finding['disposition']}",
                       f"class={finding['finding'].finding_class}", *location, f"actioned={finding['actioned']}"]
            if finding["disposition"] == "fix":
                command.append(f"source={finding['source']}")
            code, output = log_call(repo, command)
            printed_ids = loop_transcript.PRINTED_FINDING_ID.findall(output)
            if finding["disposition"] == "ask" and code == 0 and printed_ids:
                ask_ids.setdefault(finding["finding"], printed_ids[0])
                ask_rows.append({"file": path or UNLOCATED, "line": line, "finding_id": printed_ids[0]})
    return ask_ids, ask_rows


# ---------- the loop ----------

def tally_review(tallies, findings, assessment):
    """Adds one review's new findings ({disposition: [finding records]}) to the metrics tallies, so a finding refiled
    in a later round counts once."""
    tallies["fix"] += len(findings["fix"])
    tallies["ask"] += len(findings["ask"])
    tallies["nit"] += len(findings["nit"])
    tallies["blocker"] += sum("[blocker]" in item.text.lower() for item in findings["fix"])
    every_finding = findings["fix"] + findings["ask"] + findings["nit"]
    tallies["smells"] += sum(item.finding_class == "smell" for item in every_finding)
    if assessment == "NEEDS CHANGES":
        tallies["result"] = "NEEDS CHANGES"
    elif assessment and tallies["result"] == "PASS":
        tallies["result"] = assessment


def prior_issue_entries(round_findings, skips):
    """The round's findings as the next reviewers' prior issues: fixed, or skipped with the coder's reason."""
    entries = []
    for number, item in enumerate(round_findings, 1):
        entry = {"issue": item.text, "status": "skipped" if number in skips else "fixed",
                 "file": item.path or "unknown"}
        if number in skips:
            entry["reason"] = skips[number]
        entries.append(entry)
    return entries


class LoopRun(full_check_gate.FullCheckSteps):
    """The state one review loop builds up round by round. `progress` holds what a crash still reports: iter, fixed
    and files_touched, updated in place as the loop goes."""

    def __init__(self, repo, out, brief, gate_env, progress, plan=""):
        self.repo, self.out, self.brief, self.gate_env, self.plan = repo, out, brief, gate_env, plan
        self.progress = progress
        self.fixed, self.files_touched = progress["fixed"], progress["files_touched"]
        self.iter_count = 0
        self.skipped_fp, self.remaining, self.asks, self.nits, self.run_rows = [], [], [], [], []
        self.open_fixes = []  # the fix findings a plan-change stop leaves unapplied
        self.ask_gates = {}
        self.pointer_asks = []  # the asks that only pointed back to another ask, dropped before the packet
        self.tallies = {"fix": 0, "ask": 0, "nit": 0, "blocker": 0, "fixed": 0, "skipped_fp": 0, "smells": 0,
                        "result": "PASS"}
        self.prior_issues = []
        self.status = "converged"
        self.class_closure = NO_CLOSURE
        self.init_full_check_state()
        self.round_two_fix_diff_path = ""
        self.files = {}
        self.dispatches = []
        self.filed = {}  # {(reviewer, file): [finding entries]}, so a refiled finding updates its first row
        self.round_claimed = set()  # ids of the entries this round filed or refiled, so no two reports share one
        self.round_fixes = []  # the fix entries this round's reviewers filed, for fix_round to mark
        self.check_fixed = 0  # findings the full check and the class closure fixed, which file no finding row
        self.last_pass = ""
        # a change (a coder pass, or a whole expected-red not-run) that no passed full check ran after
        self.untested_fix = False
        self.scoped_tests = ""
        self.later_phase_files = set()  # the plan's later-phase files, which no coder pass may edit
        self.guidance = ""

    def next_round(self):
        self.iter_count += 1
        self.progress["iter"] = self.iter_count

    def stop(self, status, remaining):
        self.status = status
        self.remaining = remaining

    def review_one(self, dispatch):
        agent, owned = dispatch
        prompt = reviewer_prompt(self.repo, agent, owned, self.prior_issues, self.round_two_fix_diff_path,
                                 tuple(ask.text for ask in self.asks), self.brief)
        text = claude_call(f"review{self.iter_count}-{agent}", prompt, self.repo, self.out, agent=agent)
        return parse_review(text) or disposition_call(text, self.repo, self.out)

    def earlier_filing(self, entries, finding):
        """The entry from an earlier round that this finding refiles: not yet claimed this round, with the same
        disposition and a near title. None when it is new."""
        return next((entry for entry in entries if id(entry) not in self.round_claimed
                     and entry["disposition"] == finding["disposition"]
                     and near_title(entry["title"], finding["title"])), None)

    def ask_already_filed(self, ask):
        """Whether another reviewer already asked this text, so it stays one ask and files no second finding."""
        return ask in self.asks or any(entry["disposition"] == "ask" and entry["finding"] == ask
                                       for entries in self.filed.values() for entry in entries)

    def filing_row(self, agent, owned, parsed, fixes, design):
        """The run row of one review. A fix starts `actioned: none`; fix_round sets it once the coder returns. A
        finding this reviewer filed in an earlier round, in the same file with the same disposition and the same or
        near title, updates that round's entry and stays off this row, wherever its line moved."""
        reported = [{"finding": item, "disposition": "fix", "actioned": "none", "source": "round"} for item in fixes]
        reported += [{"finding": item, "disposition": "ask", "actioned": "ask", "source": ""}
                     for item in parsed["ask"] + design]
        reported += [{"finding": item, "disposition": "nit", "actioned": "none", "source": ""}
                     for item in parsed["nit"]]

        findings = []
        for finding in reported:
            path = finding["finding"].path or UNLOCATED
            finding["title"] = finding["finding"].title
            entries = self.filed.setdefault((agent, path), [])
            earlier = self.earlier_filing(entries, finding)
            if earlier:
                finding["spot"] = earlier["spot"]
                if finding["disposition"] == "ask":
                    finding["finding"] = earlier["finding"]
                earlier.update(finding)
                finding = earlier
            elif finding["disposition"] == "ask" and self.ask_already_filed(finding["finding"]):
                continue
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

    def record_review(self, agent, owned, parsed, fixes, design):
        """Files one review's row, tallies its new findings and returns them by disposition."""
        row = self.filing_row(agent, owned, parsed, fixes, design)
        new_findings = {disposition: [finding["finding"] for finding in row["findings"]
                                      if finding["disposition"] == disposition]
                        for disposition in ("fix", "ask", "nit")}
        tally_review(self.tallies, new_findings, parsed["assessment"])
        self.run_rows.append(row)
        return new_findings

    def split_review(self, tree_paths, review):
        """(the review without its absent-file findings, its fixes, its [design-decision] fixes, its absent-file
        findings). The fixes a plan ruling covers move to the review's asks. An ask that only points back to another
        ask leaves the review for the packet's dropped asks."""
        parsed, absent = absent_file_split(self.repo, tree_paths, review)
        parsed["ask"], pointer_asks = pointer_ask_split(parsed["ask"], self.asks)
        self.pointer_asks += [ask for ask in pointer_asks if ask not in self.pointer_asks]

        design = [item for item in parsed["fix"] if "[design-decision]" in item.text.lower()]
        fixes = [item for item in parsed["fix"] if item not in design]
        fixes, ruled = ruled_plan_split(self.repo, self.plan, fixes)
        parsed["ask"] += ruled
        return parsed, fixes, design, absent

    def stop_on_review_plan_change(self, tree_paths, round_fix, stopping_review, later_reviews):
        """A plan-change ask stops the loop. The round's fix findings, the later reviews' included, stay open, and the
        stopping and later reviews' other asks and [design-decision] items join the asks."""
        agent, owned, parsed, fixes, design = stopping_review
        new_findings = self.record_review(agent, owned, parsed, fixes, design)
        open_fixes = [item for _agent, earlier_fixes in round_fix for item in earlier_fixes] + fixes
        open_asks = [(agent, item) for item in new_findings["ask"]]
        plan_changes = plan_change_items(parsed["ask"] + design)
        for (later_agent, later_owned), later in later_reviews:
            later_parsed, later_fixes, later_design, later_absent = self.split_review(tree_paths, later)
            self.skipped_fp += [{"item": item, "reason": ABSENT_FILE_REASON} for item in later_absent]
            later_new = self.record_review(later_agent, later_owned, later_parsed, later_fixes, later_design)
            open_fixes += later_fixes
            open_asks += [(later_agent, item) for item in later_new["ask"]]
            plan_changes += plan_change_items(later_parsed["ask"] + later_design)

        open_ask_findings = [item for _agent, item in open_asks]
        plan_change_asks = set(plan_change_items(open_ask_findings))
        for ask_agent, item in open_asks:
            if item not in plan_change_asks:
                self.add_ask(ask_agent, item)

        self.open_fixes = merge_findings(open_fixes)
        for row in self.run_rows:
            for finding in row["findings"]:
                if finding["actioned"] == "fixed" and reported_again(finding["finding"], self.open_fixes):
                    finding["actioned"] = "none"
        self.fixed[:] = still_fixed(self.fixed, self.open_fixes)

        unique_changes = list(dict.fromkeys(plan_changes))
        self.stop("plan-change", [item.text for item in unique_changes])

    def add_ask(self, agent, item):
        """Adds one ask with its reviewer as its gate. The same text from a second reviewer stays one ask, under the
        first reviewer."""
        if item in self.asks:
            return
        self.asks.append(item)
        self.ask_gates[item] = agent

    def review_round(self):
        """Runs the round's reviewers in parallel and sorts their findings. Returns (round_fix, round_nits). A
        plan-change ask stops the loop (stop_on_review_plan_change)."""
        with ThreadPoolExecutor(max_workers=len(self.dispatches)) as pool:
            reviews = list(pool.map(self.review_one, self.dispatches))
        self.last_pass = "reviewer"

        self.round_claimed, self.round_fixes = set(), []
        round_fix, round_nits = [], []
        tree_paths = git_lines(self.repo, "ls-files", "--cached", "--others", "--exclude-standard")
        dispatched_reviews = list(zip(self.dispatches, reviews, strict=True))
        for index, ((agent, owned), review) in enumerate(dispatched_reviews):
            parsed, fixes, design, absent = self.split_review(tree_paths, review)
            self.skipped_fp += [{"item": item, "reason": ABSENT_FILE_REASON} for item in absent]

            if plan_change_items(parsed["ask"] + design):
                later_reviews = dispatched_reviews[index + 1:]
                self.stop_on_review_plan_change(tree_paths, round_fix, (agent, owned, parsed, fixes, design),
                                                later_reviews)
                break

            new_findings = self.record_review(agent, owned, parsed, fixes, design)
            for item in new_findings["ask"]:
                self.add_ask(agent, item)
            round_nits += parsed["nit"]
            round_fix.append((agent, fixes))
        return round_fix, round_nits

    def repair(self, call_name, findings, nits=()):
        """One coder pass on the findings. Returns (report, diffs, changed files). Raises LaterPhaseEditError when the
        pass edited a later-phase file."""
        before = scope(self.repo)
        prompt = coder_prompt(self.repo, [finding.text for finding in findings], [nit.text for nit in nits],
                              list(before), self.gate_env, self.later_phase_files, self.guidance)
        self.last_pass = "coder"
        self.untested_fix = True
        try:
            report, diffs, changed = coder_call(call_name, prompt, self.repo, self.out)
        except CoderCallError as error:
            self.files_touched.update(error.changed)
            raise

        later_phase_edits = sorted(set(changed) & self.later_phase_files)
        if later_phase_edits:
            self.files_touched.update(changed)
            raise LaterPhaseEditError(f"{call_name} edited files the plan gives to a later phase: "
                                      + ", ".join(later_phase_edits))
        return report, diffs, changed

    def stop_on_coder_plan_change(self, round_findings, skips, changed, report):
        """A coder that reports a plan change keeps the edits it made. The issues it did not skip go to fixed when it
        changed a file; the skipped ones, or all of them when it changed none, stay open. The loop ran no full check
        or scoped-test pass on those fixes."""
        applied = [item for number, item in enumerate(round_findings, 1) if changed and number not in skips]
        self.fixed += applied
        for finding in self.round_fixes:
            if any(finding["finding"].text in item.text for item in applied):
                finding["actioned"] = "fixed"

        self.open_fixes = [item for item in round_findings if item not in applied]
        self.stop("plan-change", [report.strip()])

    def fix_round(self, round_fix, round_nits):
        """The coder pass on the round's merged fixes, and the plan for the next round. Returns False when the loop
        ends here."""
        round_findings = merge_findings([item for _agent, fixes in round_fix for item in fixes])
        if not round_findings:
            self.nits += round_nits
            return False

        report, coder_diffs, changed = self.repair(f"coder{self.iter_count}", round_findings, round_nits)
        self.files_touched.update(changed)
        skips = skipped_issues(report, len(round_findings))
        if PLAN_CHANGE_YES.search(report.strip()):
            self.stop_on_coder_plan_change(round_findings, skips, changed, report)
            return False

        self.skipped_fp += [{"item": round_findings[number - 1], "reason": line}
                            for number, line in sorted(skips.items())]
        skipped_findings = [round_findings[number - 1] for number in sorted(skips)]
        if not changed:
            unchanged = [item for item in round_findings if item not in skipped_findings]
            self.skipped_fp += [{"item": item, "reason": NO_CHANGE_REASON} for item in unchanged]
            skipped_findings += unchanged
        for finding in self.round_fixes:
            skipped = any(finding["finding"].text in item.text for item in skipped_findings)
            finding["actioned"] = "skipped_fp" if skipped else "fixed"
        self.fixed += [item for item in round_findings if item not in skipped_findings]
        self.prior_issues = prior_issue_entries(round_findings, skips)

        self.files = scope(self.repo)
        if self.iter_count < ROUND_BUDGET:
            fix_diff_file = self.out / f"round{self.iter_count}-fix.diff"
            fix_diff_file.write_text("\n\n".join(coder_diffs))
            self.round_two_fix_diff_path = str(fix_diff_file)
            self.dispatches = second_round_plan(round_fix, changed, skipped_findings, coder_diffs)
        return not (changed and all(path.endswith(".md") for path in changed))

    def mark_repaired(self, findings, changed):
        """A repair's findings go to fixed when it changed a file, else to skipped_fp."""
        if not changed:
            self.skipped_fp += [{"item": item, "reason": NO_CHANGE_REASON} for item in findings]
            return
        self.fixed += findings
        self.check_fixed += len(findings)
        self.files_touched.update(changed)

    def class_closure_pass(self, check_command):
        """The class-closure judgment on the fixes, and one coder pass with a full check on any class left open."""
        closure = closure_check(self.repo, self.out, [finding.text for finding in self.fixed], claude_call)
        self.class_closure = closure["receipt"]
        if not closure["open"]:
            return

        open_findings = [parse_finding(text) for text in closure["open"]]
        _report, _diffs, class_changed = self.repair("coder-class", open_findings)
        self.mark_repaired(open_findings, class_changed)
        self.next_round()
        self.recheck_full_check(check_command, "full check failing after the class repair")

    def scoped_tests_pass(self, gate_commands):
        """The phase's scoped tests after a fix that no passed full check ran after. A red one stops the loop."""
        log_path = self.out / SCOPED_TESTS_LOG
        self.scoped_tests, tails = coder_gate.run_scoped_tests(self.repo, gate_commands, self.gate_env, log_path)
        if tails:
            self.stop("critical-blocker", ["scoped tests failing after the last fix:\n" + "\n\n".join(tails)])

    def outcome(self, ask_ids, ask_rows):
        return {
            "status": self.status,
            "iter": self.iter_count,
            "fixed": self.fixed,
            "skipped_fp": self.skipped_fp,
            "blockers": self.remaining if self.status in handback.BLOCKER_STATUSES else [],
            "plan_change": self.remaining if self.status == "plan-change" else [],
            "open_fixes": self.open_fixes,
            "asks": self.asks,
            "ask_gates": self.ask_gates,
            "pointer_asks": self.pointer_asks,
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
            "scoped_tests": self.scoped_tests,
        }


def walk(loop, check_command, gate_commands):
    """The review rounds, then the full check, the class closure and the scoped tests while the loop converges."""
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
    if loop.status == "converged" and loop.untested_fix:
        loop.scoped_tests_pass(list(gate_commands))


def run_loop(repo, out, session, header, handoff, progress, gate_commands=()):
    """Walks the graph. Returns the outcome mapping. `progress` holds what a crash still reports: iter, fixed and
    files_touched, updated in place as the loop goes."""
    lane = header["lane"]
    structure_pass_skipped = header.get("structure-pass") == "skip"
    brief = reviewer_brief(header, handoff)
    gate_env = plan_format.gate_env_words_in(handoff)
    scope_fields = ["scope=phase"] + ([f"phase={header['phase']}"] if header.get("phase") else [])
    loop = LoopRun(repo, out, brief, gate_env, progress, header.get("plan", ""))
    loop.later_phase_files = set(filter(None, header.get("later-phase files", "").split(", ")))
    loop.guidance = header.get("guidance", "")

    log_call(repo, [str(SKILLS / "review-scope"), "caller=code"])
    found_command = check_command_for(repo, out)
    plan = header.get("plan")
    plan_on_disk = plan if plan and (pathlib.Path(repo) / plan).is_file() else None
    check_command, loop.expected_red = full_check.phase_check(repo, found_command, plan_on_disk, header.get("phase"))
    loop.remember_as = found_command

    loop.files = scope(repo)
    loop.dispatches = first_round_plan(loop.files, structure_pass_skipped)
    try:
        walk(loop, check_command, gate_commands)
    except LaterPhaseEditError as error:
        loop.stop("critical-blocker", [str(error)])

    every_actioned = [finding["actioned"] for row in loop.run_rows for finding in row["findings"]]
    loop.tallies["fixed"] = every_actioned.count("fixed") + loop.check_fixed
    loop.tallies["skipped_fp"] = every_actioned.count("skipped_fp")
    ask_ids, ask_rows = telemetry(repo, session, lane, scope_fields, loop.iter_count, loop.tallies, loop.run_rows)
    return loop.outcome(ask_ids, ask_rows)


# ---------- main ----------

def stop_on_sigterm(_signal_number, _frame):
    """The stop signal of an abort, a review-again or a start --restart: kill the process group of every claude call
    that is running and remove the base run's worktree, then exit without a packet."""
    for pid in list(LIVE_CHILDREN):
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(pid, signal.SIGKILL)
    full_check_gate.remove_live_base_trees()
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
    PARENT_SESSION["label"] = script_utils.session_display_name(args.session) or f"session {args.session}"
    repo = str(pathlib.Path(args.repo).resolve())
    out = pathlib.Path(args.state_dir) / "loop-script" / args.agent_id
    out.mkdir(parents=True, exist_ok=True)
    started = now()
    progress = {"iter": 0, "fixed": [], "files_touched": set()}

    exit_code = 0
    outcome = None
    try:
        header, handoff = read_prompt(args.prompt_file)
        run_state = code_step_core.read_state_file(pathlib.Path(args.state_dir)) or {}
        outcome = run_loop(repo, out, args.session, header, handoff, progress, run_state.get("gateCommands", []))
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
    write_usage_row(repo, started, CALLS)
    print(message)
    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
