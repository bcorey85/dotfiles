#!/usr/bin/env python3
"""The scripted review loop: the walking between steps is code, the judgment inside each step is a model call.

    review_loop_script.py <repo> --state-dir <dir> --session <id> --agent-id <id> --prompt-file <path>
        [--gate-command <cmd>]... [--reviewers headless|main]

The prompt file (review_loop_prompt_file.py holds its header keys) is header lines, a blank line, then the handoff
block. A `findings:` line makes the run fix-first: the fix coder applies the caller's findings before any reviewer, and
`no-review: yes` then plans no reviewer. `base:` reviews every change since that commit, `files:` only the named files,
`reviewer-model:` runs each reviewer on that model, and `iter:` counts the rounds an earlier run already used.
The script walks a fixed graph: scope, first-round reviewers (code, plus smell and test reviewers on a large
diff), disposition routing, one fix coder, re-review by every reviewer that filed a fix and owns a changed file
(the smell reviewer only past the size bar), the two-round cap, the full-check execution gate, the class-closure
check, telemetry rows, and the hand-back packet.
The full check runs through full_check.py and writes the full-check receipt. It runs only the `Quality check:` command
of the repo's CLAUDE.md; it runs none in a repo with no such line. In a repo whose CLAUDE.md holds `Full suite: CI`,
where the coder calls run the changed files' tests, a run with no runner summary or that ran no test is
`passed (check only; CI runs the full suite)`. A check past
full_check_gate.CHECK_TIMEOUT_SECONDS is killed with its process
group, and a check whose step stops on a missing path is a check-command error. A check that fails on a missing
module the repo declares as a dependency is an environment gap. None is a failure: the packet's `full_check` says
`not run (CI)`, `not run (no check found; ...)`, `not run (timeout)`,
`not run (check-command error: ...)`, `not run (environment gap: ...)` or, when the phase's Expected red lines
leave out the whole check, `not run (expected red until Phase <id>[, <id>...])`. An exit 0 with no runner summary, or
that ran no test, is no failure either: it says `unverified (exit 0, no test result shown)`. So is a failure that the
check shows the same way
on HEAD without the diff: it says `pre-existing failure (...)` and did not verify the diff. To tell, a failed check is
rerun once per loop (the base run) in a detached worktree of HEAD, up to full_check_gate.CHECK_TIMEOUT_SECONDS. A
failed check's blocker holds the failing step's lines; after a repair coder, before recheck_full_check stops as a
blocker, the autofix formatters run on the touched files and the check reruns once if one changed a file.

Model steps are `claude -p` calls in auto permission mode, each named `child of <parent session> (<role>)` so
ListAgents tells it from a worker, and each with CLAUDE_FORMAT_HOOK_OFF=1 in its environment: the
reviewers (agents code-reviewer, smell-reviewer, test-reviewer), the fix coder (agent coder) and the class-closure
judgment (Sonnet). A Sonnet disposition call runs
only when a reviewer's output has no Fix/Ask/Nit sections the parser can read. Every call is logged to
<state dir>/loop-script/<agent id>/calls.jsonl with its session id, role, wall time and token counts.
With `--reviewers main` the reviewers are no `claude -p` call: reviewer_dispatch.py hands each round's reviewer
prompts to the main session, which runs them as its subagents and writes their reports back; each gets a call log
row with `via: main` and no token count.

On finish, or on any uncaught error, the script validates its packet with handback.load, then appends the
hand-back rows: the hand-back store row, the stop row, and, when the telemetry switch is on, one agent-usage row.
Exit 0 on a normal finish; exit 1 when the run crashed or the packet failed validation (a critical-blocker packet and
the rows are still written). A SIGTERM (a caller stopping the loop) kills every running claude call and exits 143 with
no packet and no rows.

review_loop_findings.py reads the reviewers' text; review_loop_closure.py runs the class-closure check;
review_loop_packet.py writes the packet and the hand-back rows.

Not covered: the second-order caller supplement and the critical-blocker judgment (a reviewer routes it as an ask).
"""

import argparse
import contextlib
import hashlib
import os
import pathlib
import re
import signal
import sys
import typing
from concurrent.futures import ThreadPoolExecutor

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
# The file in the loop's state folder that holds the whole output of a red scoped test run.
SCOPED_TESTS_LOG = "scoped-tests.log"
STALE_PROSE_LOG = "stale-prose.log"
READABILITY_LOG = "readability.log"
sys.path[:0] = [str(SCRIPT_DIR.parent / folder) for folder in (".", "review", "code", "lib", "telemetry")]
import change_removal
import coder_gate
import coder_report
import format_files
import full_check
import full_check_gate
import handback
import loop_transcript
import plan_format
import review_loop_held
import reviewer_dispatch
import script_utils
from finding_record import parse_finding
from review_loop_calls import (
    CALL_TIMEOUT_SECONDS,
    CALLS,
    LIVE_CHILDREN,
    PARENT_SESSION,
    claude_call,
    now,
    record_main_dispatch,
)
from review_loop_closure import (
    NO_CLOSURE,
    closure_check,
    receipt_after_class_repair,
    receipt_all_held,
    receipt_still_open,
)
from review_loop_coder import CoderCallError, coder_call, coder_fault_notes
from review_loop_findings import (
    PLAN_CHANGE_YES,
    UNLOCATED,
    absent_file_split,
    finding_records,
    merge_findings,
    near_title,
    parse_review,
    plan_change_items,
    pointer_ask_split,
    reply_with_one_retry,
    ruled_plan_split,
    same_finding,
)
from review_loop_fix_induced import fix_induced_tag, previous_fix_ranges
from review_loop_packet import crash_outcome, packet_message, write_handback_rows, write_usage_row
from review_loop_plan import ChangeUnderReview, first_round_plan, review_files, second_round_plan
from review_loop_prompt_file import (
    BASE_KEY,
    FILES_KEY,
    NO_REVIEW_KEY,
    REVIEWER_MODEL_KEY,
    REVIEWERS_HEADLESS,
    REVIEWERS_MAIN,
    YES,
    header_iter,
    header_list,
    read_findings,
    read_prompt,
    reviewer_brief,
)
from review_loop_prompts import coder_prompt, reviewer_prompt

SKILLS = SCRIPT_DIR.parent.parent / "skills" / "review"
ROUND_BUDGET = 2
LOG_TIMEOUT_SECONDS = 60
ABSENT_FILE_REASON = "the file is not in the tree"
NO_CHANGE_REASON = "the coder made no change"


def git_lines(repo, *args):
    output = script_utils.git_output(repo, *args)
    if output is None:
        raise RuntimeError(f"`git {' '.join(args)}` failed in {repo}")
    return output.splitlines()


def disposition_call(text, repo, out):
    prompt = (
        "Below is a code reviewer's output. Copy each finding into one of three lists without changing its words: "
        "fix, ask, nit "
        "(the reviewer's own section decides; do not re-label). Reply with one JSON object only: "
        '{"fix": [..], "ask": [..], "nit": [..]}.\n\n' + text
    )
    parsed = reply_with_one_retry(claude_call, "disposition", prompt, repo, out, ("fix", "ask", "nit"),
                                  '{"fix": [..], "ask": [..], "nit": [..]}', model="sonnet")
    return finding_records({"fix": parsed.get("fix", []), "ask": parsed.get("ask", []), "nit": parsed.get("nit", []),
                            "assessment": ""})


class HitCheck(typing.NamedTuple):
    """A gate check whose hits go to a coder pass: its name in messages, the coder call, its log file, its commands."""

    label: str
    call_name: str
    log: str
    commands: list


class LaterPhaseEditError(RuntimeError):
    """A coder pass that edited a file the plan gives to a later phase."""


class ChangeRemovedError(RuntimeError):
    """A coder pass that removed half or more of the lines the change under review adds. The message is the blocker."""


class ReviewRequest(typing.NamedTuple):
    """One reviewer call of a round: its role name, its agent and its prompt."""

    role: str
    agent: str
    prompt: str


class ReviewSplit(typing.NamedTuple):
    """One review sorted by split_review: the parsed review, its fixes, its design-decision fixes and its
    absent-file findings."""

    parsed: dict
    fixes: list
    design: list
    absent: list


def skipped_issues(report, issue_count):
    """Issue number -> the coder's `SKIPPED <n>: <reason>` line, for numbers that name a listed issue."""
    skips = {}
    for line in report.splitlines():
        match = re.match(r"\s*[-*]?\s*`?SKIPPED (\d+):", line)
        if not match:
            continue
        number = int(match.group(1))
        if 1 <= number <= issue_count:
            skips.setdefault(number, line.strip())
    return skips


def fixes_of_round(round_fix):
    """Every fix of a round's (agent, owned, fixes) entries, in order."""
    fixes = []
    for _agent, _owned, agent_fixes in round_fix:
        fixes += agent_fixes
    return fixes


def matches_any_finding(item, findings):
    """Whether `item` is the same finding as one of `findings`."""
    return any(same_finding(item, other) for other in findings)


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


class TelemetryRun(typing.NamedTuple):
    """What the telemetry rows of one loop run carry. With `out`, a finding of round two or later gets `fix_induced`
    from the fix diff that the round before it wrote there."""

    session: str
    lane: str
    scope_fields: list
    iter_count: int
    tallies: dict
    run_rows: list
    out: pathlib.Path | None = None


def log_metrics_row(repo, run):
    """Writes the metrics row of the run."""
    tallies = run.tallies
    log_call(repo, [str(SKILLS / "log-review-metrics"), f"lane={run.lane}", f"iter={run.iter_count}",
                    f"fix={tallies['fix']}", f"ask={tallies['ask']}", f"nit={tallies['nit']}",
                    f"blocker={tallies['blocker']}", f"fixed={tallies['fixed']}",
                    f"skipped_fp={tallies['skipped_fp']}", "test_intent_ran=0", "culled=0", "comment_noise=0",
                    f"smells={tallies['smells']}", f"result={tallies['result']}"])


def finding_log_command(run, row, finding, fix_ranges):
    """The log-review-finding command of one finding of a run row."""
    path, line = finding["finding"].path, finding["finding"].line
    location = [f"file={path}", f"line={line}"] if path else [f"file={UNLOCATED}"]
    finding_id = stable_finding_id(run.session, run.lane, run.scope_fields, row["gate"], finding["spot"])
    command = [str(SKILLS / "log-review-finding"), "kind=finding", f"finding_id={finding_id}", f"lane={run.lane}",
               *run.scope_fields, f"iter={row['iter']}", f"gate={row['gate']}",
               f"disposition={finding['disposition']}", f"class={finding['finding'].finding_class}", *location,
               f"actioned={finding['actioned']}"]
    if finding["disposition"] == "fix":
        command.append(f"source={finding['source']}")
    fix_induced = fix_induced_tag(finding.get("fix_induced", ""), row["iter"], path, line, fix_ranges)
    if fix_induced:
        command.append(f"fix_induced={fix_induced}")
    return command


def log_finding(repo, run, row, finding, fix_ranges):
    """Writes one finding row. Returns its {file, line, finding_id} stop-row entry when it is an ask and the logger
    printed an id, else None."""
    code, output = log_call(repo, finding_log_command(run, row, finding, fix_ranges))
    printed_ids = loop_transcript.PRINTED_FINDING_ID.findall(output)
    if finding["disposition"] != "ask" or code != 0 or not printed_ids:
        return None
    return {"file": finding["finding"].path or UNLOCATED, "line": finding["finding"].line,
            "finding_id": printed_ids[0]}


def write_telemetry(repo, run):
    """Writes the metrics row, and each run and finding row of one TelemetryRun. Returns ({ask text: finding_id},
    ask_rows): the id that log-review-finding printed for each ask row, and the {file, line, finding_id} entries the
    stop row carries. With `run.out`, a finding of round two or later gets `fix_induced` from the fix diff that the
    round before it wrote there."""
    log_metrics_row(repo, run)
    logger = str(SKILLS / "log-review-finding")
    ask_ids, ask_rows = {}, []
    for row in run.run_rows:
        log_call(repo, [logger, "kind=run", f"lane={run.lane}", *run.scope_fields, f"iter={row['iter']}",
                        f"gate={row['gate']}", f"n_findings={len(row['findings'])}", f"diff_loc={row['loc']}",
                        f"result={row['result']}"])
        fix_ranges = previous_fix_ranges(run.out, row["iter"]) if run.out and row["iter"] > 1 else {}
        row_ask_ids, row_ask_rows = log_row_findings(repo, run, row, fix_ranges)
        for ask, finding_id in row_ask_ids.items():
            ask_ids.setdefault(ask, finding_id)
        ask_rows += row_ask_rows
    return ask_ids, ask_rows


def log_row_findings(repo, run, row, fix_ranges):
    """Writes the finding rows of one run row. Returns ({ask text: finding_id}, ask_rows) of its asks."""
    ask_ids, ask_rows = {}, []
    for finding in row["findings"]:
        ask_row = log_finding(repo, run, row, finding, fix_ranges)
        if ask_row:
            ask_ids.setdefault(finding["finding"], ask_row["finding_id"])
            ask_rows.append(ask_row)
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
        self.last_review_round = 0  # the last round a reviewer ran in; a repair pass raises iter_count, never this
        self.init_findings_state()
        self.init_full_check_state()
        self.init_round_state()
        self.init_review_settings()

    def init_findings_state(self):
        """The findings, asks and plan impacts the loop collects."""
        self.skipped_fp, self.remaining, self.asks, self.nits, self.run_rows = [], [], [], [], []
        self.plan_impacts = []  # {text, gate, ac_change, cause, adopted, applied} of each plan impact, shown at the end
        # every finding the coder skipped or left unchanged in a round whose plan impact is held: still open, not false
        # positives, until a later round fixes it
        self.open_fixes = []
        # the ruling line, the ruled PLAN-IMPACT block and the carried findings: the only plan-marked items it settles
        self.resolved_texts = []
        self.ask_gates = {}
        self.pointer_asks = []  # the asks that only pointed back to another ask, dropped before the packet
        self.tallies = {"fix": 0, "ask": 0, "nit": 0, "blocker": 0, "fixed": 0, "skipped_fp": 0, "smells": 0,
                        "result": "PASS"}
        self.prior_issues = []
        self.status = "converged"
        self.class_closure = NO_CLOSURE
        self.open_classes = []  # the class members the repair pass left unfixed

    def init_round_state(self):
        """The per-round bookkeeping: dispatches, filed entries, which pass ran last and what it left untested."""
        self.round_two_fix_diff_path = ""
        self.files = {}
        self.dispatches = []
        self.filed = {}  # {(reviewer, file): [finding entries]}, so a refiled finding updates its first row
        self.round_claimed = set()  # ids of the entries this round filed or refiled, so no two reports share one
        self.round_fixes = []  # the fix entries this round's reviewers filed, for fix_round to mark
        # findings fixed outside a reviewer round (the caller's fix-first findings, the full check, the class
        # closure), which file no finding row
        self.check_fixed = 0
        # the items skipped with no finding row: the caller's fix-first findings the coder skipped, and every item on
        # a held file
        self.given_skipped = 0
        self.last_pass = ""
        # a change (a coder pass, or a whole expected-red not-run) that no passed full check ran after
        self.untested_fix = False
        self.scoped_tests = ""

    def init_review_settings(self):
        """The settings the prompt header gives; build_loop overwrites them."""
        self.later_phase_files = set()  # the plan's later-phase files, which no coder pass may edit
        self.guidance = ""
        self.test_strategy = ""  # the plan's test strategy section, which only the test reviewer gets
        self.change = None  # ChangeUnderReview: the lines the change adds, which the fix passes must not remove
        self.reviewers = REVIEWERS_HEADLESS  # who runs the reviewers: REVIEWERS_HEADLESS or REVIEWERS_MAIN
        self.reviewer_model = ""  # the model every reviewer runs on; "" leaves each agent's own
        self.review_base = ""  # the commit the review diffs against; "" is HEAD
        self.only_files = []  # the files the caller scoped the review to; [] is every changed file
        self.held_files = set()  # files another session holds, which no reviewer reads and no coder pass may edit

    def review_scope(self):
        files = review_files(self.repo, self.review_base, self.only_files)
        return script_utils.without_paths(files, self.held_files)

    def format_reviewed_files(self, check_command):
        """Run the formatters the repo configures on the reviewed and touched files, so the tree the hand-back records
        is already formatted and a formatter run after the loop leaves the reviewed tree as it was. The changed files
        count as touched."""
        paths = sorted(set(self.review_scope()) | self.files_touched)
        changed = format_files.run_formatters(self.repo, paths, include_python=True, configured_only=True,
                                              check_command=check_command or "")
        self.files_touched.update(changed)

    def next_round(self):
        self.iter_count += 1
        self.progress["iter"] = self.iter_count

    def stop(self, status, remaining):
        self.status = status
        self.remaining = remaining

    def review_request(self, dispatch):
        """The ReviewRequest (role, agent, prompt) of one reviewer of this round."""
        agent, owned = dispatch
        prompt = reviewer_prompt(self.repo, agent, owned, self.prior_issues, self.round_two_fix_diff_path,
                                 tuple(ask.text for ask in self.asks), self.brief, self.test_strategy)
        lens = getattr(owned, "lens", "")
        if lens:
            prompt += "\n" + lens
        return ReviewRequest(f"review{self.iter_count}-{agent}", agent, prompt)

    def read_review(self, text):
        return parse_review(text) or disposition_call(text, self.repo, self.out)

    def review_one(self, dispatch):
        role, agent, prompt = self.review_request(dispatch)
        text = claude_call(role, prompt, self.repo, self.out, agent=agent, model=self.reviewer_model or None)
        return self.read_review(text)

    def reviews_from_main(self):
        """The round's reviews, run by the main session as its subagents (`--reviewers main`)."""
        requests = [self.review_request(dispatch) for dispatch in self.dispatches]
        replies = reviewer_dispatch.request_round(self.out, self.iter_count, requests, CALL_TIMEOUT_SECONDS,
                                                  model=self.reviewer_model)
        reviews = []
        for (role, agent, _prompt), (text, wall) in zip(requests, replies, strict=True):
            record_main_dispatch(self.out, role, agent, wall)
            reviews.append(self.read_review(text))
        return reviews

    def run_reviewers(self):
        if self.reviewers == REVIEWERS_MAIN:
            return self.reviews_from_main()
        with ThreadPoolExecutor(max_workers=len(self.dispatches)) as pool:
            return list(pool.map(self.review_one, self.dispatches))

    def earlier_filing(self, entries, finding):
        """The entry from an earlier round that this finding refiles: not yet claimed this round, with the same
        disposition and a near title. None when it is new."""
        return next((entry for entry in entries if id(entry) not in self.round_claimed
                     and entry["disposition"] == finding["disposition"]
                     and near_title(entry["title"], finding["title"])), None)

    def ask_already_filed(self, ask):
        """Whether another reviewer already asked this text, so it stays one ask and files no second finding."""
        if ask in self.asks:
            return True
        for entries in self.filed.values():
            if any(entry["disposition"] == "ask" and entry["finding"] == ask for entry in entries):
                return True
        return False

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
            self.file_finding(agent, finding, findings)

        loc = sum(self.files[path][0] for path in owned if path in self.files)
        return {"iter": self.iter_count, "gate": agent, "loc": loc, "result": parsed["assessment"] or "PASS",
                "findings": findings}

    def file_finding(self, agent, finding, findings):
        """Files one reported finding. A refiling updates its earlier entry; a new finding gets a spot and joins
        `findings`, the run row's list; an ask another reviewer already filed is dropped."""
        path = finding["finding"].path or UNLOCATED
        finding["title"] = finding["finding"].title
        entries = self.filed.setdefault((agent, path), [])
        earlier = self.earlier_filing(entries, finding)
        if earlier:
            self.refile(earlier, finding)
            filed = earlier
        elif finding["disposition"] == "ask" and self.ask_already_filed(finding["finding"]):
            return
        else:
            finding["spot"] = new_spot(path, finding["title"], entries)
            entries.append(finding)
            findings.append(finding)
            filed = finding
        self.round_claimed.add(id(filed))
        if filed["disposition"] == "fix":
            self.round_fixes.append(filed)

    def refile(self, earlier, finding):
        """Updates an earlier round's entry from the same finding filed again, keeping its spot."""
        finding["spot"] = earlier["spot"]
        if finding["disposition"] == "ask":
            finding["finding"] = earlier["finding"]
        earlier.update(finding)

    def record_review(self, agent, owned, parsed, fixes, design):
        """Files one review's row, tallies its new findings and returns them by disposition."""
        row = self.filing_row(agent, owned, parsed, fixes, design)
        new_findings = {}
        for disposition in ("fix", "ask", "nit"):
            new_findings[disposition] = [finding["finding"] for finding in row["findings"]
                                         if finding["disposition"] == disposition]
        tally_review(self.tallies, new_findings, parsed["assessment"])
        self.run_rows.append(row)
        return new_findings

    def owned_files(self):
        """The files the run owns, for telling a held file's tail from an owned file's tail. It needs no git call,
        and it is empty when no file is held."""
        if not self.held_files:
            return set()
        return set(self.only_files) | self.files_touched

    def sendable(self, items):
        """(the items that name no held file, the ones that do). Each held one goes to skipped_fp with its reason: no
        coder gets it."""
        kept, held_items, recorded = review_loop_held.skip_held_items(items, self.held_files, self.owned_files(),
                                                                         self.skipped_fp, self.repo)
        self.given_skipped += recorded
        return kept, held_items

    def without_held_findings(self, review):
        """The review without its fixes, asks and nits on held files: fixes and asks go to skipped_fp, nits to nits."""
        kept_nits, held_nits = review_loop_held.split_held_findings(review["nit"], self.held_files,
                                                                          self.owned_files(), self.repo)
        new_nits = [nit for nit in held_nits if nit not in self.nits]
        self.nits += new_nits
        self.tallies["nit"] += len(new_nits)
        kept_fixes, _held_fixes = self.sendable(review["fix"])
        kept_asks, _held_asks = self.sendable(review["ask"])
        return {**review, "fix": kept_fixes, "ask": kept_asks, "nit": kept_nits}

    def split_review(self, tree_paths, review):
        """A ReviewSplit: the review without its absent-file findings, its fixes, its [design-decision] fixes, its
        absent-file findings. The fixes a plan ruling covers move to the review's asks. An ask that only points back
        to another ask leaves the review for the packet's dropped asks."""
        parsed, absent = absent_file_split(self.repo, tree_paths, review)
        parsed["ask"], pointer_asks = pointer_ask_split(parsed["ask"], self.asks)
        self.pointer_asks += [ask for ask in pointer_asks if ask not in self.pointer_asks]

        design = [item for item in parsed["fix"] if "[design-decision]" in item.text.lower()]
        fixes = [item for item in parsed["fix"] if item not in design]
        fixes, ruled = ruled_plan_split(self.repo, self.plan, fixes)
        parsed["ask"] += ruled
        return ReviewSplit(parsed, fixes, design, absent)

    def record_plan_impact(self, impact):
        """Adds one plan impact ({text, gate, ac_change, cause, adopted, applied}). The same text again, from a later
        round or a second reviewer, stays one. `applied` is True when the coder's edits for it are already in the
        tree."""
        if any(near_title(entry["text"], impact["text"]) for entry in self.plan_impacts):
            return
        self.plan_impacts.append(impact)

    def route_plan_items(self, agent, items):
        """(the items the coder fixes this round, the items held for a ruling). A plan impact that changes no
        acceptance criterion is adopted by rule and fixed like any finding; one that changes a criterion, or says
        nothing, is held for the end. Once the caller ruled on the plan impacts, a plan-marked item the ruling or a
        carried finding names is a plain fix; a new one takes the path above."""
        to_coder, ruling_held = [], []
        for item in items:
            if any(near_title(known, item.text) for known in self.resolved_texts):
                to_coder.append(item)
                continue

            ac_change = plan_format.changes_acceptance_criteria(item.text)
            self.record_plan_impact({"text": item.text, "gate": agent, "ac_change": ac_change,
                                     "cause": plan_format.PLAN_CAUSE, "adopted": not ac_change, "applied": False})
            (ruling_held if ac_change else to_coder).append(item)
        return to_coder, ruling_held

    def record_coder_plan_impact(self, report, changed):
        """A coder's PLAN-IMPACT report joins the plan impacts. Its edits stay and the loop goes on. A toolkit cause,
        or a cause that does not parse, is never adopted. `changed` holds the files the coder's edits changed. Returns
        True when the impact is held for a ruling."""
        text = coder_report.plan_impact_block(report) or report.strip()
        cause = plan_format.stopping_plan_impact_cause([text], cause_required=True)
        ac_change = plan_format.changes_acceptance_criteria(text)
        adopted = not ac_change and cause == plan_format.PLAN_CAUSE
        self.record_plan_impact({"text": text, "gate": "coder", "ac_change": ac_change, "cause": cause,
                                 "adopted": adopted, "applied": bool(changed)})

        return not adopted and cause != plan_format.TOOLKIT_CAUSE

    def add_ask(self, agent, item):
        """Adds one ask with its reviewer as its gate. The same text from a second reviewer stays one ask, under the
        first reviewer."""
        if item in self.asks:
            return
        self.asks.append(item)
        self.ask_gates[item] = agent

    def review_round(self):
        """Runs the round's reviewers in parallel and sorts their findings. Returns (round_fix, round_nits). A plan
        impact never stops the round: route_plan_items sends it to the coder or holds it."""
        reviews = self.run_reviewers()
        self.last_pass = "reviewer"
        self.last_review_round = self.iter_count

        self.round_claimed, self.round_fixes = set(), []
        round_fix, round_nits = [], []
        tree_paths = git_lines(self.repo, "ls-files", "--cached", "--others", "--exclude-standard")
        for (agent, owned), review in zip(self.dispatches, reviews, strict=True):
            review = self.without_held_findings(review)
            split = self.split_review(tree_paths, review)
            parsed, design = split.parsed, split.design
            self.skipped_fp += [{"item": item, "reason": ABSENT_FILE_REASON} for item in split.absent]

            plan_items = plan_change_items(parsed["ask"] + design)
            routed, ruling_held = self.route_plan_items(agent, plan_items)
            parsed["ask"] = [item for item in parsed["ask"] if item not in routed]
            design = [item for item in design if item not in routed]
            fixes = split.fixes + routed

            new_findings = self.record_review(agent, owned, parsed, fixes, design)
            self.add_asks_without_ruling(agent, new_findings["ask"], ruling_held)
            round_nits += parsed["nit"]
            round_fix.append((agent, owned, fixes))
        return round_fix, round_nits

    def add_asks_without_ruling(self, agent, asks, ruling_held):
        """Adds each ask of a review that no plan impact holds for a ruling at the end."""
        for item in asks:
            if item not in ruling_held:
                self.add_ask(agent, item)

    def repair(self, call_name, findings, nits=()):
        """One coder pass on the findings. Returns a CoderResult (report, diffs, changed files). Raises
        LaterPhaseEditError when the pass edited a later-phase file, and ChangeRemovedError when the passes so far
        removed half or more of the lines the change under review adds."""
        finding_paths = [finding.path for finding in findings if finding.path]
        files_in_scope = list(dict.fromkeys([*self.review_scope(), *finding_paths]))
        prompt = coder_prompt(self.repo, [finding.text for finding in findings], [nit.text for nit in nits],
                              files_in_scope, self.gate_env, self.later_phase_files, self.guidance, self.held_files)
        self.last_pass = "coder"
        self.untested_fix = True
        try:
            result = coder_call(call_name, prompt, self.repo, self.out, self.held_files)
        except CoderCallError as error:
            self.files_touched.update(error.changed)
            raise

        later_phase_edits = sorted(set(result.changed) & self.later_phase_files)
        if later_phase_edits:
            self.files_touched.update(result.changed)
            raise LaterPhaseEditError(f"{call_name} edited files the plan gives to a later phase: "
                                      + ", ".join(later_phase_edits))

        removed = self.change.removed()
        if change_removal.is_gutted(self.change.added, removed):
            self.files_touched.update(result.changed)
            raise ChangeRemovedError(change_removal.removal_blocker(self.change.added, removed))
        return result

    def fix_round(self, round_fix, round_nits):
        """The coder pass on the round's merged fixes, and the plan for the next round. Returns False when the loop
        ends here."""
        round_findings = merge_findings(fixes_of_round(round_fix))
        if not round_findings:
            self.nits += round_nits
            return False

        result = self.repair(f"coder{self.iter_count}", round_findings, round_nits)
        changed = result.changed
        self.files_touched.update(changed)

        skips = skipped_issues(result.report, len(round_findings))
        plan_reported = PLAN_CHANGE_YES.search(result.report.strip()) is not None
        plan_held = plan_reported and self.record_coder_plan_impact(result.report, changed)

        skipped_findings, round_open_fixes = self.record_skips(round_findings, skips, changed, plan_held)
        self.open_fixes += round_open_fixes
        self.mark_round_fixes(round_open_fixes, skipped_findings)
        applied = [item for item in round_findings if item not in skipped_findings]
        self.fixed += applied
        self.open_fixes = [item for item in self.open_fixes if not matches_any_finding(item, applied)]
        self.prior_issues = prior_issue_entries(round_findings, skips)

        self.files = self.review_scope()
        if self.iter_count < ROUND_BUDGET:
            self.plan_second_round(round_fix, result, skipped_findings)
        # A toolkit .md file is code, so only a docs-class fix that changes only .md files skips the re-review.
        docs_only = (bool(applied) and all(item.finding_class == "docs" for item in applied)
                     and all(path.endswith(".md") for path in changed))
        return not docs_only

    def record_skips(self, round_findings, skips, changed, plan_held):
        """Sorts the round's findings the coder did not fix. Returns (skipped findings, findings still open). With a
        plan impact held, they stay open; otherwise they join skipped_fp."""
        skipped_entries = [{"item": round_findings[number - 1], "reason": line}
                           for number, line in sorted(skips.items())]
        round_open_fixes = []
        if plan_held:
            round_open_fixes += [entry["item"] for entry in skipped_entries]
        else:
            self.skipped_fp += skipped_entries
        skipped_findings = [round_findings[number - 1] for number in sorted(skips)]
        if changed:
            return skipped_findings, round_open_fixes

        unchanged = [item for item in round_findings if item not in skipped_findings]
        if plan_held:
            round_open_fixes += unchanged
        else:
            self.skipped_fp += [{"item": item, "reason": NO_CHANGE_REASON} for item in unchanged]
        return skipped_findings + unchanged, round_open_fixes

    def mark_round_fixes(self, round_open_fixes, skipped_findings):
        """Sets `actioned` on each fix this round's reviewers filed: none while open, skipped_fp, or fixed."""
        for finding in self.round_fixes:
            if any(finding["finding"].text in item.text for item in round_open_fixes):
                finding["actioned"] = "none"
                continue

            skipped = any(finding["finding"].text in item.text for item in skipped_findings)
            finding["actioned"] = "skipped_fp" if skipped else "fixed"

    def plan_second_round(self, round_fix, result, skipped_findings):
        """Writes the round's fix diff for the next reviewers and plans which of them run."""
        fix_diff_file = self.out / f"round{self.iter_count}-fix.diff"
        fix_diff_file.write_text("\n\n".join(result.diffs))
        self.round_two_fix_diff_path = str(fix_diff_file)
        self.dispatches = second_round_plan(round_fix, result.changed, skipped_findings, result.diffs)

    def fix_first(self, texts):
        """The fix coder on the caller's findings, before any reviewer. Their skips and fixes file no finding row."""
        parsed_findings = [parse_finding(text) for text in texts]
        findings, _held_findings = self.sendable(parsed_findings)
        if not findings:
            return

        report, _diffs, changed = self.repair("coder0", findings)
        self.files_touched.update(changed)
        if PLAN_CHANGE_YES.search(report.strip()):
            self.record_coder_plan_impact(report, changed)

        skips = skipped_issues(report, len(findings))
        skipped = [{"item": findings[number - 1], "reason": line} for number, line in sorted(skips.items())]
        kept = [item for number, item in enumerate(findings, 1) if number not in skips]
        if not changed:
            skipped += [{"item": item, "reason": NO_CHANGE_REASON} for item in kept]
            kept = []
        self.skipped_fp += skipped
        self.given_skipped += len(skipped)
        self.fixed += kept
        self.check_fixed += len(kept)
        self.prior_issues = prior_issue_entries(findings, skips)

    def mark_repaired(self, findings, changed, records_skip=True):
        """A repair's findings go to fixed when it changed a file, else to skipped_fp. With `records_skip` False, a
        repair that changed nothing records nothing: the findings are a gate's prompt, not a reviewer's claim."""
        if not changed:
            if records_skip:
                self.skipped_fp += [{"item": item, "reason": NO_CHANGE_REASON} for item in findings]
            return
        self.fixed += findings
        self.check_fixed += len(findings)
        self.files_touched.update(changed)

    def class_closure_pass(self, check_command):
        """The class-closure judgment on the fixes, and one coder pass with a full check on any class left open. When
        that pass changes a file, the receipt names the members it fixed, so no member shows as both fixed and open."""
        closure = closure_check(self.repo, self.out, [finding.text for finding in self.fixed], claude_call)
        self.class_closure = closure["receipt"]
        if not closure["open"]:
            return

        parsed_open = [parse_finding(text) for text in closure["open"]]
        # A member in a held file is only skipped: this run can never fix it, so it never gates clean status.
        open_findings, held_items = self.sendable(parsed_open)
        held_texts = [item.text for item in held_items]
        if not open_findings:
            self.class_closure = receipt_all_held(held_texts)
            return

        _report, _diffs, class_changed = self.repair("coder-class", open_findings)
        self.mark_repaired(open_findings, class_changed)
        if class_changed:
            sent_texts = [item.text for item in open_findings]
            self.class_closure = receipt_after_class_repair(sent_texts, held_texts)
        else:
            self.open_classes = [item.text for item in open_findings]
            self.class_closure = receipt_still_open(self.open_classes, held_texts)

        self.next_round()
        self.recheck_full_check(check_command, "full check failing after the class repair")

    def scoped_tests_pass(self, check_command, gate_commands):
        """The phase's scoped tests after a fix that no passed full check ran after. A red one stops the loop. The
        readability and stale-prose checks are no tests: their hits go to the coder, readability first, since its
        repair can change the prose a stale-prose hit names."""
        readability_commands = [command for command in gate_commands if coder_gate.is_readability_check(command)]
        prose_commands = [command for command in gate_commands if coder_gate.is_stale_prose_check(command)]
        test_commands = [command for command in gate_commands
                         if command not in readability_commands and command not in prose_commands]
        if not self.run_test_commands(test_commands):
            return

        readability = HitCheck("readability check", "coder-readability", READABILITY_LOG, readability_commands)
        prose = HitCheck("stale-prose check", "coder-prose", STALE_PROSE_LOG, prose_commands)
        edited = self.hit_check_pass(check_command, readability)
        if self.status == "converged":
            edited = self.hit_check_pass(check_command, prose) or edited
        if edited and self.status == "converged" and self.untested_fix:
            self.run_test_commands(test_commands)

    def run_test_commands(self, test_commands):
        """Run the scoped test commands and keep their result. A red run the autofix formatters can fix is fixed and
        run once more. False, with the loop stopped, when one stays red."""
        log_path = self.out / SCOPED_TESTS_LOG
        self.scoped_tests, tails = coder_gate.run_scoped_tests(self.repo, test_commands, self.gate_env, log_path)
        if tails and self.autofix_touched_files():
            self.scoped_tests, tails = coder_gate.run_scoped_tests(self.repo, test_commands, self.gate_env, log_path)
        if tails:
            self.stop("critical-blocker", ["scoped tests failing after the last fix:\n" + "\n\n".join(tails)])
            return False

        return True

    def hit_check_pass(self, check_command, check):
        """One coder pass on the hits of a readability or stale-prose check after the last fix. Only a real hit (exit
        1) goes to the coder; with no edit the last pass stays the one before it, and with one the full check runs
        again. Any other failure of the check stops as `critical-blocker`, and a result that is neither a pass nor a
        hit joins `scoped_tests`. True when the coder edited a file."""
        if not check.commands:
            return False

        log_path = self.out / check.log
        result, hit_outputs, script_failures = coder_gate.run_hit_check(self.repo, check.commands, self.gate_env,
                                                                        log_path)
        if script_failures:
            self.stop("critical-blocker", [f"{check.label} failing:\n" + "\n\n".join(script_failures)])
            return False

        if not hit_outputs:
            if result != coder_gate.SCOPED_PASSED:
                self.scoped_tests += f"; {check.label} {result}"
            return False

        hits = [parse_finding("\n\n".join(hit_outputs))]
        pass_before_repair = self.last_pass
        _report, _diffs, changed = self.repair(check.call_name, hits)
        self.mark_repaired(hits, changed, records_skip=False)
        if not changed:
            self.last_pass = pass_before_repair
            return False

        self.next_round()
        self.recheck_full_check(check_command, f"full check failing after the {check.label} repair")
        return True

    def outcome(self, ask_ids, ask_rows):
        return {
            "status": self.status,
            "iter": self.iter_count,
            "review_round": self.last_review_round,
            "fixed": self.fixed,
            "skipped_fp": self.skipped_fp,
            "blockers": self.remaining if self.status in handback.BLOCKER_STATUSES else [],
            "plan_impacts": self.plan_impacts,
            "open_fixes": merge_findings(self.open_fixes),
            "asks": self.asks,
            "ask_gates": self.ask_gates,
            "pointer_asks": self.pointer_asks,
            "ask_ids": ask_ids,
            "ask_rows": ask_rows,
            "class_closure": self.class_closure,
            "open_classes": self.open_classes,
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
            "tool_fault": " ".join(filter(None, [full_check.fault_note(self.full_check), *coder_fault_notes()])),
        }


def walk(loop, check_command, gate_commands):
    """The review rounds, then the full check, the class closure and the scoped tests while the loop converges."""
    while loop.iter_count < ROUND_BUDGET and loop.dispatches:
        loop.next_round()
        round_fix, round_nits = loop.review_round()
        if not loop.fix_round(round_fix, round_nits):
            break

    if loop.status == "converged":
        loop.format_reviewed_files(check_command)
        loop.full_check_pass(check_command)
    if loop.status == "converged":
        loop.class_closure_pass(check_command)
    if loop.status == "converged" and loop.untested_fix:
        loop.scoped_tests_pass(check_command, list(gate_commands))


def first_pass(loop, findings, no_review, structure_pass_skipped):
    """The first round's reviewers. A fix-first run sends the caller's findings to the coder first, and then skips
    the structure pass; with no_review it plans no reviewer at all."""
    if findings:
        loop.fix_first(findings)
        structure_pass_skipped = True
    loop.files = loop.review_scope()
    if no_review or not loop.files:
        loop.dispatches = []
        return
    loop.dispatches = first_round_plan(loop.files, structure_pass_skipped)


class LoopRequest(typing.NamedTuple):
    """What one run of the loop is given: the repo, the state folder, the caller's prompt file and its settings."""

    repo: str
    out: pathlib.Path
    session: str
    header: dict
    handoff: str
    progress: dict
    gate_commands: typing.Sequence = ()
    reviewers: str = REVIEWERS_HEADLESS


def telemetry_scope_fields(header, caller):
    """The `scope=` fields every telemetry row of this run carries."""
    if caller != "code":
        return ["scope=standalone"]
    if header.get("phase"):
        return ["scope=phase", f"phase={header['phase']}"]
    return ["scope=phase"]


def later_phase_files(header):
    """The set of files the plan gives to a later phase, from the prompt header's comma-separated list."""
    listed = header.get("later-phase files", "")
    names = listed.split(", ")
    return set(filter(None, names))


def build_loop(request):
    """The LoopRun for one request, with the settings its prompt header gives. Returns (loop, check_command)."""
    header, handoff, repo = request.header, request.handoff, request.repo
    brief = reviewer_brief(header, handoff)
    gate_env = plan_format.gate_env_words_in(handoff)
    loop = LoopRun(repo, request.out, brief, gate_env, request.progress, header.get("plan", ""))
    loop.reviewers = request.reviewers
    loop.later_phase_files = later_phase_files(header)
    loop.guidance = header.get("guidance", "")
    loop.resolved_texts = plan_format.resolved_plan_texts(handoff)
    loop.change = ChangeUnderReview(repo)

    log_call(repo, [str(SKILLS / "review-scope"), f"caller={header.get('caller', 'code')}"])
    found_command = full_check.configured_check_command(repo)
    plan = header.get("plan")
    plan_on_disk = plan if plan and (pathlib.Path(repo) / plan).is_file() else None
    check_command, loop.expected_red = full_check.phase_check(repo, found_command, plan_on_disk, header.get("phase"))
    if plan_on_disk:
        plan_lines = (pathlib.Path(repo) / plan_on_disk).read_text().splitlines()
        loop.test_strategy = plan_format.test_strategy_section(plan_lines)

    loop.reviewer_model = header.get(REVIEWER_MODEL_KEY, "")
    loop.review_base = header.get(BASE_KEY, "")
    loop.only_files = header_list(header, FILES_KEY)
    loop.held_files = review_loop_held.run_held_files(repo, loop.only_files)
    loop.iter_count = min(header_iter(header), ROUND_BUDGET - 1)
    request.progress["iter"] = loop.iter_count
    return loop, check_command


def tally_actioned(loop):
    """Sets the metrics tallies of fixed and skipped findings from the run rows and the findings fixed outside them."""
    every_actioned = []
    for row in loop.run_rows:
        every_actioned += [finding["actioned"] for finding in row["findings"]]
    loop.tallies["fixed"] = every_actioned.count("fixed") + loop.check_fixed
    loop.tallies["skipped_fp"] = every_actioned.count("skipped_fp") + loop.given_skipped


def run_loop(request):
    """Walks the graph. Returns the outcome mapping. `request.progress` holds what a crash still reports: iter, fixed
    and files_touched, updated in place as the loop goes. `request.reviewers` says who runs the reviewers."""
    header = request.header
    structure_pass_skipped = header.get("structure-pass") == "skip"
    scope_fields = telemetry_scope_fields(header, header.get("caller", "code"))
    loop, check_command = build_loop(request)
    try:
        first_pass(loop, read_findings(header), header.get(NO_REVIEW_KEY) == YES, structure_pass_skipped)
        walk(loop, check_command, request.gate_commands)
    except LaterPhaseEditError as error:
        loop.stop("critical-blocker", [str(error)])
    except ChangeRemovedError as error:
        loop.stop(handback.FIX_REMOVED_CHANGE, [str(error)])

    tally_actioned(loop)
    run = TelemetryRun(request.session, header["lane"], scope_fields, loop.iter_count, loop.tallies, loop.run_rows,
                       request.out)
    ask_ids, ask_rows = write_telemetry(request.repo, run)
    return loop.outcome(ask_ids, ask_rows)


# ---------- main ----------

def stop_on_sigterm(_signal_number, _frame):
    """The stop signal of a caller stopping the loop: kill the process group of every claude call
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
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--prompt-file", required=True)
    parser.add_argument("--gate-command", action="append", default=[])
    parser.add_argument("--reviewers", choices=(REVIEWERS_HEADLESS, REVIEWERS_MAIN), default=REVIEWERS_HEADLESS)
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
        request = LoopRequest(repo, out, args.session, header, handoff, progress, args.gate_command, args.reviewers)
        outcome = run_loop(request)
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
    write_handback_rows(args, message, status, outcome["ask_rows"], outcome["unreviewed_fix"])
    write_usage_row(repo, started, CALLS)
    print(message)
    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
