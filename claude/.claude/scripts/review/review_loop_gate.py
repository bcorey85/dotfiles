#!/usr/bin/env python3
"""review_loop_gate.py — deterministic checks on the review loop.

  SubagentStop (review-loop), the backstop: blocks once when no full check ran after the last code
      change: a shell call of review/full_check.py whose tool_result holds the line
      `full check: passed`; a shell call of several full_check.py calls counts only when each printed
      `full check: passed` or an Expected red `not run` line. A
      failed, unverified, setup-fault, or not-run result other than an Expected red one, and a checker run by hand,
      never count; full_check.py itself refuses a command scoped to files or tests, or one whose scope cannot be read,
      unless its text equals the CLAUDE.md `Quality check:` command, or, in a repo whose full suite runs in CI, one of
      its && steps. The last coder step — a
      dispatch, or a SendMessage to a coder it dispatched — is the last code change; with none, the loop start
      is, since the phase changed code before the loop ran. A handoff `tests-run` never exempts it. A loop returning
      `status: plan-impact` owes no check, and neither does a loop in a repo whose CLAUDE.md holds the line
      `Full suite: CI` (full_check.full_suite_runs_in_ci): CI runs that repo's full suite. That repo is the repo of
      the ROOT= or `repo:` line, else the hook cwd (handback.full_suite_in_ci). A stop with a
      delivered SubagentHandback (one no hook denied) skips this check and the plan-file check.
      A second stop in a row passes (stop_hook_active), so a stuck loop cannot spin. The block
      reason reaches the loop as context and it keeps working. Register with matcher
      `review-loop`; the agent_type check below still guards an unscoped entry.
    A stop while a background dispatch (`Async agent launched`) has not yet reported back, by task
      notification or agent message, passes: the loop is waiting, not done.
    A background dispatch is a launch whose result starts with `Async agent launched`, a SendMessage that
      resumed an agent (`Resuming agent <id>`) with no later agent message or task notification from it, or a
      shell call whose result record names a `backgroundTaskId` (run in the background, or moved there by its
      timeout) with no task notification for it. A shell whose result comes before the loop's last delivered
      SubagentHandback is no open work: the caller already holds the packet.
    Every review-loop SubagentStop appends a `kind=stop` row to the session's hand-back store (agent_id and
      the count of open background dispatches), through handback_store.record. A count of one or more means the loop
      is waiting: `review_fix.py packet` prints `ACTION: wait-for-loop`, not stop-no-handback. A row with 0 ends
      the wait. A stop whose transcript cannot be read writes a 0 row, then fails open as before. A store write
      error is reported on stderr and never blocks the stop.
      The row also carries `ask_rows`: the file, line and printed finding_id of each `actioned=ask` row the loop
      logged, so `review_fix.py packet` can give each ask its id.
  PreToolUse (Agent): a review-loop dispatch whose prompt says `caller: code` must carry a
      `handoff:` line. A review-loop dispatch from a subagent other than the /code fork is refused: the
      nested loop cannot ask for permission or wake on its reviewer's report, so it never hands back.
      A reviewer dispatch from a review-loop whose reviewed repo (LoopTranscript.reviewed_repo) is not its cwd's
      work tree is refused unless the reviewer prompt names that repo on a `Repo root: <path>` line.

  SubagentStop (review-loop), when the stop passes and no background dispatch is open: writes one
    `kind=run` row per reviewer dispatch (`*-reviewer`, `*-reviewer-deep`) through log-review-finding,
    with `n_findings` counted from that reviewer's own report. A report that cannot be counted,
    because it has no known layout or a findings section holds text and no entry, gets a row with
    `n_findings` null, never a guessed count. Each dispatch (tool_use_id) is written once per session, so a repeat
    stop adds nothing. The
    gate applies the telemetry switch before it calls the logger; a logging failure never blocks a stop.

Hook JSON on stdin; on a violation, a decision JSON on stdout; exit 0, but exit 1 when lib/script_utils.py
cannot be imported. Any parse failure passes (fail open) and says why on stderr: this gate adds a check, it must
never stop the loop on its own error.
"""
import json
import os
import pathlib
import re
import subprocess
import sys

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / folder) for folder in (".", "../lib", "../telemetry")]
import handback
import handback_store
import script_utils
from loop_transcript import (
    GATE_REASON,
    GIT_TIMEOUT_SECONDS,
    PROMPT_REPO_ROOT,
    LoopTranscript,
    plan_edit_reason,
    prompt_field,
    prompt_path_work_tree,
    scan,
)

OWN_CLAUDE_DIR = pathlib.Path(__file__).resolve().parents[2]
CALLER_CODE = re.compile(r"(?i)(?<![\w-])caller[`*]*\s*[:=]\s*[`\"']?code\b")
HANDOFF = re.compile(r"(?im)^[ \t]*handoff[ \t]*:")

RUN_GATES = re.compile(r"-reviewer(-deep)?$")
NIT_SECTION = re.compile(r"(?mi)^\s*#{2,4}\s*[*_`]*Nits?\b")
FENCE =re.compile(r"^(```|~~~)")
HEADING_MARKUP = re.compile(r"[*_`:]")
SECTION_HEADING = re.compile(r"^(#{2,4})\s*(.*)")
LIST_MARKER = re.compile(r"^(?:[-*+]|\d+[.)])\s+")
PATH_TOKEN = r"`?[\w@~+./-]*[./][\w@~+./-]*"
ENTRY_START = re.compile(
    rf"^(?:\*{{0,2}}\[blocker\]\*{{0,2}}\s*)?\*{{0,2}}(?:{PATH_TOKEN}:\d[\d,\u2013-]*`?(?!\w)|{PATH_TOKEN}`?\s+[\u2014\u2013-])"
)
NO_ENTRIES = re.compile(r"^[\[(*_`]*(none|n/a|nothing|-|\u2014|\u2013)[\])*_`.!]*$", re.I)
INTENT_SECTIONS = re.compile(r"(BUG-PINNING|UNVERIFIABLE|CULL|REQUIRES-MUTATION|WEAK)\b")
# (report heading, does a section of this report hold findings: (heading level, title) -> bool)
LAYOUTS = (
    (re.compile(r"(?m)^\s*#{1,4}\s.*(?:Review Summary|Simplification Review)"),
     lambda level, title: title.split(" ")[0] in ("Fix", "Fixes", "Ask", "Findings")),
    (re.compile(r"(?m)^\s*#{1,4}\s.*Test Review Report"),
     lambda level, title: level >= 3 and not title.startswith("Summary of Recommended Actions")),
    (re.compile(r"(?m)^\s*#{1,4}\s.*Test-Intent Audit"),
     lambda level, title: bool(INTENT_SECTIONS.match(title))),
)
ASSESSMENT = re.compile(r"Overall Assessment\*{0,2}:?\s*\**(PASS WITH WARNINGS|PASS|NEEDS CHANGES)")


PROMPT_LANE = prompt_field("lane", r"(eng-spec|code|test-audit|other|none)\b")
PACKET_ROW_KEYS = ("fixed", "skipped_fp", "findings_remaining", "ask", "nit")
PROMPT_PHASE = prompt_field("phase", r"([\w.-]+)")

LEDGER_REASON = ("The packet lists {owed} finding(s) (fixed, skipped, deferred, ask, nit) but only {logged} "
                 "per-finding row(s) were logged{metrics}. Run Step 7 and Step 7b now, one "
                 "`log-review-finding kind=finding` call per finding, then return the packet.")
NIT_REASON = ("The packet lists {owed} nit(s) but only {logged} `disposition=nit` row(s) were logged. Log one "
              "`log-review-finding kind=finding disposition=nit` row per nit, then return the packet.")
METRICS_REASON = ("The last metrics line was logged before the last reviewer round, or its counts differ from the "
                  "packet's. Log the Step 7 metrics line again with the final counts (fixed={fixed}, "
                  "skipped_fp={skipped_fp}), then return the packet.")
RETURN_TAIL = "then return the packet."
DELIVERED_TAIL = "then stop: the packet was already delivered, and a second hand-back is denied."
HANDOFF_REASON = ("A review-loop dispatch from /code carries no handoff block. Build it per "
                  "~/.claude/skills/_shared/handoff-block.md and dispatch again.")
NESTED_REASON = ("Run /review from the main session: a review-loop that a subagent dispatches cannot ask for "
                 "permission or wake on its reviewer's report, so it ends with no hand-back.")
REVIEWER_REPO_REASON = ("This loop reviews {repo}, not your cwd. Put the line `Repo root: {repo}` in the "
                        "{reviewer} prompt and dispatch again.")


def reasons_for(scanned):
    ungated, open_dispatches = scanned
    if open_dispatches or not ungated:
        return []
    return [GATE_REASON]


def final_packet(transcript, final):
    """The loop's hand-back packet, or None when the last message holds none that parses."""
    try:
        return handback.load(transcript.last_text if final is None else final)
    except handback.PacketError:
        return None


def ledger_reasons(transcript, final, delivered=False):
    """The reasons for a block when the packet owes ledger rows the loop did not write, or when it names the plan file
    as touched. Nothing when the packet does not parse: a stop check never guesses. After a delivered hand-back the
    ledger reasons tell the loop to stop, since a second hand-back is denied, and the plan file is not checked: the
    hand-back hook checked it before delivery."""
    packet = final_packet(transcript, final)
    if packet is None:
        return []
    reasons = []

    owed = sum(len(packet.get(key) or []) for key in PACKET_ROW_KEYS)
    missing_metrics = not transcript.metrics_calls
    if transcript.finding_rows_logged < owed or missing_metrics:
        metrics = " and no metrics line" if missing_metrics else ""
        reasons.append(LEDGER_REASON.format(owed=owed, logged=transcript.finding_rows_logged, metrics=metrics))
    elif unlogged_nits(transcript, packet):
        reasons.append(NIT_REASON.format(owed=len(packet.get("nit") or []), logged=nit_rows(transcript)))
    elif stale_metrics(transcript, packet):
        reasons.append(METRICS_REASON.format(fixed=len(packet.get("fixed") or []),
                                             skipped_fp=len(packet.get("skipped_fp") or [])))
    if delivered:
        return [reason.replace(RETURN_TAIL, DELIVERED_TAIL) for reason in reasons]

    plan_edit = plan_edit_reason(transcript, packet)
    if plan_edit:
        reasons.append(plan_edit)
    return reasons


def nit_rows(transcript):
    return sum(fields.get("disposition") == "nit" for calls in transcript.finding_calls.values() for fields in calls)


def unlogged_nits(transcript, packet):
    """True when the packet lists more nits than the loop logged `disposition=nit` rows. A finding call whose
    disposition is not spelled out (a shell variable, or no `disposition=` at all) leaves the count unknown, so
    nothing is claimed."""
    calls = [fields for calls in transcript.finding_calls.values() for fields in calls]
    if any(not fields.get("disposition", "").isalpha() for fields in calls):
        return False
    return nit_rows(transcript) < len(packet.get("nit") or [])


def stale_metrics(transcript, packet):
    """True when the last metrics line came before the last reviewer round, or when a fixed= or skipped_fp= count it
    logged differs from the packet's. A count the line leaves out or sends as a shell variable is not compared."""
    line, fields, _ = transcript.metrics_calls[-1]
    reviews = [transcript.dispatched_at[tool_use_id] for tool_use_id, kind in transcript.kinds.items()
               if RUN_GATES.search(kind)]
    last_review = max(reviews, default=-1)
    if line < last_review:
        return True

    for key in ("fixed", "skipped_fp"):
        logged = fields.get(key, "")
        if logged.isdigit() and int(logged) != len(packet.get(key) or []):
            return True
    return False


def section_findings(lines):
    """The findings in one report section: its top-level list items, or entry lines that open with a path. Prose
    before, between or after the entries is not counted. 0 when the section opens with a line that is only a none
    marker; None when the section has text and no entry to count."""
    content = [raw for raw in lines if raw.strip()]
    if not content:
        return 0
    if NO_ENTRIES.match(LIST_MARKER.sub("", content[0].strip())):
        return 0
    indents = [
        len(raw) - len(raw.lstrip())
        for raw in content
        if LIST_MARKER.match(raw.strip()) or ENTRY_START.match(raw.strip())
    ]
    if not indents:
        return None
    return indents.count(min(indents))


def findings_sections(report, holds_findings):
    """The lines of each report section that holds findings. Lines inside a code fence are skipped, and a deeper
    heading stays inside its section."""
    sections, current, level, fenced = [], None, 0, False
    for raw in report.splitlines():
        line = raw.strip()
        if FENCE.match(line):
            fenced = not fenced
            continue
        if fenced:
            continue
        heading = SECTION_HEADING.match(line)
        if heading and not (current is not None and len(heading.group(1)) > level):
            level = len(heading.group(1))
            title = HEADING_MARKUP.sub("", heading.group(2)).strip()
            current = [] if holds_findings(level, title) else None
            if current is not None:
                sections.append(current)
        elif current is not None:
            current.append(raw)
    return sections


def count_findings(report):
    """The number of findings in a reviewer report, or None when the count would be a guess: the text is no
    review report, or a section that holds findings has text and no entry in it."""
    holds_findings = next((counts for heading, counts in LAYOUTS if heading.search(report)), None)
    if holds_findings is None:
        return None

    counts = [section_findings(lines) for lines in findings_sections(report, holds_findings)]
    if None in counts:
        return None

    total = sum(counts)
    assessment = ASSESSMENT.search(report)
    verdict = assessment.group(1) if assessment else ""
    if total == 0 and verdict == "NEEDS CHANGES":
        return None
    if total == 0 and verdict == "PASS WITH WARNINGS" and not NIT_SECTION.search(report):
        return None
    return total


def reviewer_runs(transcript):
    """([{tool_use_id, gate, n_findings, result}], lane, phase) for every reviewer dispatch of the loop. The report
    is the dispatch's tool_result, the result of its task notification, or an agent message from the agent that
    the dispatch launched; the first one that counts is used. n_findings is None when none of them counts."""
    runs = []
    for tool_use_id, gate in transcript.kinds.items():
        if not RUN_GATES.search(gate):
            continue
        launched = transcript.launched_agent(tool_use_id)
        texts = [
            transcript.results.get(tool_use_id, ""),
            *transcript.notifications.get(tool_use_id, []),
            *transcript.agent_messages.get(launched, []),
        ]
        counted = [(count_findings(text), text) for text in texts]
        count, report = next(((c, t) for c, t in counted if c is not None), (None, ""))
        assessment = ASSESSMENT.search(report)
        runs.append({"tool_use_id": tool_use_id, "gate": gate, "n_findings": count,
                     "result": assessment.group(1) if assessment else ""})
    lane = PROMPT_LANE.search(transcript.prompt or "")
    phase = PROMPT_PHASE.search(transcript.prompt or "")
    return runs, lane.group(1) if lane else "none", phase.group(1) if phase else "-"


def write_run_row(hook, run, lane, phase, root=None):
    """True when log-review-finding wrote the row. The logger runs in root, the repo the loop reviewed, so the row
    names that repo and branch; with no root it runs in the session cwd. It writes nothing while the telemetry
    switch is off, and it prints one stderr line for each skip. With no ledger found (PATH, then
    `${CARGO_HOME:-~/.cargo}/bin`) the row goes to review-findings.jsonl, and the writer's stderr line is passed on."""
    if not script_utils.telemetry_switch_on():
        print("review-loop-gate: run row for {} skipped: telemetry is off".format(run["gate"]), file=sys.stderr)
        return False
    claude_dir = pathlib.Path(os.environ.get("REVIEW_LOOP_GATE_CLAUDE_DIR") or OWN_CLAUDE_DIR)
    command = [
        "bash",
        str(claude_dir / "skills" / "review" / "log-review-finding"),
        "kind=run",
        "gate=" + run["gate"],
        f"n_findings={('null' if run['n_findings'] is None else run['n_findings'])}",
        "lane=" + lane,
        "phase=" + phase,
    ]
    if run["result"]:
        command.append("result=" + run["result"])
    env = {**os.environ, "CLAUDE_CODE_SESSION_ID": hook["session_id"]}
    done = subprocess.run(command, env=env, cwd=root or hook.get("cwd") or None, capture_output=True, text=True,
                          timeout=30)
    if done.returncode:
        print(
            "review-loop-gate: run row for {} not written: {}".format(run["gate"], done.stderr.strip()), file=sys.stderr
        )
    dropped = False
    if done.returncode == 0:
        for line in done.stderr.splitlines():
            if line.startswith("ledger-write:"):
                print("review-loop-gate: " + line, file=sys.stderr)
                dropped = dropped or line.endswith("row dropped")
    return done.returncode == 0 and not dropped and "run_id=" in done.stdout


def state_file_for(session_id):
    """The gate's state file of run-row marks for one session."""
    state_dir = pathlib.Path(os.environ.get("REVIEW_LOOP_GATE_STATE_DIR")
                             or pathlib.Path.home() / ".claude" / "state" / "review-loop-gate")
    return script_utils.state_file_path(state_dir, session_id, ".jsonl")


def log_run_rows(hook, transcript):
    """Write the run rows that this session has not written yet. Never raises: a logging failure must not stop the
    loop."""
    try:
        session_id = hook.get("session_id")
        if not session_id:
            return
        runs, lane, phase = reviewer_runs(transcript)
        if not runs:
            return

        root = transcript.reviewed_repo(hook.get("cwd"))
        state_file = state_file_for(session_id)
        marks = {}
        for row in script_utils.read_jsonl(state_file):
            marks[row.get("tool_use_id")] = not row.get("undone")
        for run in runs:
            if marks.get(run["tool_use_id"]):
                continue
            # The mark goes first: when it cannot be saved the row is not written, so a repeat stop never
            # duplicates it. A row the logger did not write (switch off, logger error) takes its mark back.
            script_utils.append_jsonl(state_file, {"tool_use_id": run["tool_use_id"]})
            if not write_run_row(hook, run, lane, phase, root):
                script_utils.append_jsonl(state_file, {"tool_use_id": run["tool_use_id"], "undone": True})
    except Exception as e:
        print(f"review-loop-gate: run rows skipped, {type(e).__name__}: {e}", file=sys.stderr)


def dispatch_deny_reason(hook):
    """Why a review-loop dispatch is refused, or None. Only the main session and the /code fork may dispatch one."""
    tool_input = hook.get("tool_input") or {}
    if tool_input.get("subagent_type") != "review-loop":
        return None
    if hook.get("agent_id") and hook.get("agent_type") != script_utils.FORK_AGENT_TYPE:
        return NESTED_REASON

    prompt = tool_input.get("prompt") or ""
    if CALLER_CODE.search(prompt) and not HANDOFF.search(prompt):
        return HANDOFF_REASON
    return None


def reviewer_repo_deny_reason(hook):
    """Why a review-loop's reviewer dispatch is refused, or None: a loop on a repo other than its cwd's work tree
    must name that repo on a `Repo root:` line of each reviewer prompt."""
    tool_input = hook.get("tool_input") or {}
    reviewer = tool_input.get("subagent_type") or ""
    if hook.get("agent_type") != "review-loop" or not RUN_GATES.search(reviewer):
        return None

    cwd = hook.get("cwd")
    transcript = LoopTranscript(script_utils.agent_transcript_path(hook))
    repo = transcript.reviewed_repo(cwd)
    if not repo or repo == script_utils.work_tree_top(cwd, timeout=GIT_TIMEOUT_SECONDS):
        return None

    named = PROMPT_REPO_ROOT.search(tool_input.get("prompt") or "")
    if named and prompt_path_work_tree(named, cwd) == repo:
        return None
    return REVIEWER_REPO_REASON.format(repo=repo, reviewer=reviewer)


def check_dispatch(hook):
    reason = dispatch_deny_reason(hook) or reviewer_repo_deny_reason(hook)
    if reason:
        script_utils.pre_tool_use_deny(reason)


def record_stop(hook, open_dispatches, ask_rows=(), blocked=False):
    """Store this stop with the count of background dispatches still open, so `review_fix.py packet` can tell a loop
    that waits on an agent from one that ended without handing back, with the ask rows the loop logged, so `packet`
    can give each ask its finding_id, and with whether the gate blocked the stop, so a reader waits for the stop
    that follows a block. Never raises: a store failure must not stop the loop."""
    try:
        session_id = hook.get("session_id")
        if session_id:
            handback_store.record(session_id, "stop", agent_id=hook.get("agent_id") or "unknown",
                                  open_dispatches=open_dispatches, ask_rows=list(ask_rows),
                                  blocked=blocked)
    except Exception as e:
        print(f"review-loop-gate: stop row skipped, {type(e).__name__}: {e}", file=sys.stderr)


def check_stop(hook):
    try:
        transcript = LoopTranscript(hook["agent_transcript_path"])
        in_ci = handback.full_suite_in_ci(transcript, hook.get("cwd"))
        scanned = scan(transcript, hook.get("last_assistant_message"), in_ci)
    except Exception:
        # A transcript the gate cannot read still ends an earlier wait: with no row, the last open count would stand.
        record_stop(hook, 0)
        raise
    try:
        # A delivered hand-back passed the hand-back hook's gate, unless that gate failed open on an error
        # (it never blocks on its own failure) or let a repeat on the same code state through; pushing work after
        # delivery only makes the loop hand back a second time.
        delivered = bool(transcript.handback_lines)
        why = [] if hook.get("stop_hook_active") or delivered else reasons_for(scanned)
        if not hook.get("stop_hook_active") and not scanned[1]:
            why += ledger_reasons(transcript, hook.get("last_assistant_message"), delivered)
    except Exception:
        record_stop(hook, scanned[1], transcript.ask_rows)
        raise
    record_stop(hook, scanned[1], transcript.ask_rows, blocked=bool(why))
    if why:
        print(json.dumps({"decision": "block", "reason": " ".join(why)}))
    elif not scanned[1]:
        log_run_rows(hook, transcript)


def main():
    if os.environ.get("CLAUDE_SKIP_HOOKS"):
        return
    hook = json.load(sys.stdin)
    event = hook.get("hook_event_name")
    if event == "PreToolUse" and hook.get("tool_name") == "Agent":
        check_dispatch(hook)
    elif event == "SubagentStop" and hook.get("agent_type") == "review-loop":
        check_stop(hook)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # fail open, visibly
        print(f"review-loop-gate: skipped, {type(e).__name__}: {e}", file=sys.stderr)
