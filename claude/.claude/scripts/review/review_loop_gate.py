#!/usr/bin/env python3
"""review_loop_gate.py — deterministic checks on the review loop.

  SubagentStop (review-loop), the backstop: blocks once when no full check ran after the last code
      change: a shell call that runs a project checker, or redirects into the review-gate log, with
      no file, directory or test-name filter. For the checkers that take them, the value of
      `--manifest-path`, `-p`, `--package` or `--project` names a package or project and is no
      filter (see NON_SCOPING_FLAGS). The last coder step — a dispatch, or a SendMessage to a coder
      it dispatched — is the last code change; with none, the loop start is, since the phase changed
      code before the loop ran. A handoff `tests-run` never exempts it. A loop returning
      `status: plan-impact` owes no check.
      A second stop in a row passes (stop_hook_active), so a stuck loop cannot spin. The block
      reason reaches the loop as context and it keeps working. Register with matcher
      `review-loop`; the agent_type check below still guards an unscoped entry.
    A stop while a background dispatch (`Async agent launched`) has not yet reported back, by task
      notification or agent message, passes: the loop is waiting, not done.
  PreToolUse (Agent): a review-loop dispatch whose prompt says `caller: code` must carry a
      `handoff:` line.

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

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / folder) for folder in (".", "../lib")]
import script_utils

OWN_CLAUDE_DIR = pathlib.Path(__file__).resolve().parents[2]
CODERS = re.compile(r"^(backend-|frontend-)?coder(-deep)?$")
AGENT_ID = re.compile(r"agentId:\s*([A-Za-z0-9-]+)")
CALLER_CODE = re.compile(r"(?i)(?<![\w-])caller[`*]*\s*[:=]\s*[`\"']?code\b")
HANDOFF = re.compile(r"(?im)^[ \t]*handoff[ \t]*:")
PLAN_IMPACT = re.compile(r"(?im)^[ \t>*`-]*status[`*]*[ \t]*:[ \t`*]*plan-impact\b")
REDIRECT = re.compile(r"\d*>>?\s*&?\S+|&>\s*\S+")
SEGMENT_END = re.compile(r"&&|\|\||[;|\n]")
SCOPED = re.compile(r"(?:^|\s)(?:-k|-t|-m|-run|--testNamePattern|--grep|--findRelatedTests|--onlyChanged|--changedSince"
                    r"|--related)(?=[\s=]|$)|(?:^|\s)(?!\./\.\.\.(?:\s|$))[^\s-]\S*(?:/|::|\.(?:[cm]?[jt]sx?|py|go|rb|rs|php|vue|svelte)\b)")
# By checker: the flags whose value names a package, a project or a manifest, never a test, so the value does not
# scope a run. Another checker's `-p` or `--project` may select a test file (`rspec -p`, `bats -p`), so a flag counts
# only for the checkers listed here.
NON_SCOPING_FLAGS = {
    "cargo": ("--manifest-path", "-p", "--package"),
    "pytest": ("-p",),
    "go": ("-p",),
    "mypy": ("-p",),
    "pyright": ("-p",),
    "tsc": ("-p", "--project"),
    "vitest": ("--project",),
    "dotnet": ("--project",),
}
GATE_LOG = re.compile(r"(?:>\s*|\btee\s+(?:-a\s+)?)\S*review-gate[\w.-]*\.log")
CHECKER = re.compile(r"(?:\A|[;&|(]\s*|\n\s*)(?:cd\s+\S+\s*&&\s*)?(?:[A-Za-z_]\w*=\S+\s+)*"
                     r"(?:(?:time|npx|bunx|uv\s+run|poetry\s+run|python3?\s+-m|bundle\s+exec)\s+)*"
                     r"(?P<checker>(?:npm|pnpm|yarn|bun)\s+(?:(?:-F|--filter|workspace)\s+\S+\s+)?(?:run\s+)?"
                     r"[\w:-]*(?:test|lint|typecheck|type-check|check|build)[\w:-]*"
                     r"|jest|vitest|pytest|tsc|vue-tsc|svelte-check|eslint|oxlint|ruff|mypy|pyright|golangci-lint"
                     r"|go\s+(?:test|vet)|cargo\s+(?:test|clippy|check)|make\s+[\w-]*(?:test|lint|check)[\w-]*"
                     r"|\S*quality-check|bats|shellcheck|rspec|phpunit|dotnet\s+test)(?![\w-])")

RUN_GATES = re.compile(r"-reviewer(-deep)?$")
AGENT_MESSAGE = re.compile(r"<agent-message\s+from=\"([\w-]+)\">(.*?)(?=</agent-message>|<agent-message\s|\Z)", re.S)
# A task notification's tool_use_id, and its result when it carries one: a killed dispatch reports with none.
NOTIFICATION = re.compile(r"<tool-use-id>\s*([\w-]+)\s*</tool-use-id>(?:(?:(?!</task-notification>).)*?"
                          r"<result>((?:(?!</task-notification>).)*?)</result>)?", re.S)
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
PROMPT_LANE = re.compile(r"(?im)^[ \t>*`-]*lane[`*]*[ \t]*:[ \t`*]*(eng-spec|code|other|none)\b")
PROMPT_PHASE = re.compile(r"(?im)^[ \t>*`-]*phase[`*]*[ \t]*:[ \t`*]*([\w.-]+)")

GATE_REASON = ("No full check ran after the last code change in this phase. A scoped run, including the "
               "handoff's tests-run, does not count. Run the Step 6 execution gate now: the project's full "
               "quality-check command once, redirected to /tmp/review-gate.log. Route any failure as Step 6 "
               "says, then return the packet.")
HANDOFF_REASON = ("A review-loop dispatch from /code carries no handoff block. Build it per "
                  "~/.claude/skills/_shared/handoff-block.md and dispatch again.")


def text_of(content):
    if isinstance(content, str):
        return content
    return " ".join(b.get("text", "") for b in content or [] if isinstance(b, dict))


def scoping_words(rest, checker):
    """The arguments of one checker call as the scope check reads them: redirects gone, and the values of the flags
    that pick a package, a project or a manifest for this checker gone, since those values do not narrow which tests
    run."""
    arguments = REDIRECT.sub(" ", rest)
    flags = NON_SCOPING_FLAGS.get(checker, ())
    return script_utils.strip_flag_values(arguments, flags)


def full_check(cmd):
    """True when the command runs a checker, or writes the review-gate log, and no checker in it is filtered to
    files, directories or test names."""
    hits = list(CHECKER.finditer(cmd))
    for m in hits:
        rest = SEGMENT_END.split(cmd[m.end():], 1)[0]
        checker = m.group("checker").split()[0]
        if SCOPED.search(scoping_words(rest, checker)):
            return False
    return bool(hits) or bool(GATE_LOG.search(cmd))


class LoopTranscript:
    """One read of a loop transcript: what the stop check and the run rows need from it."""

    def __init__(self, path):
        self.prompt, self.last_text = None, ""
        self.kinds = {}  # dispatch tool_use_id -> subagent_type, in dispatch order
        self.dispatched_at = {}  # dispatch tool_use_id -> transcript line
        self.results = {}  # dispatch tool_use_id -> the text of its tool_result
        self.notifications = {}  # tool_use_id -> the results its task notifications carried, [] for none
        self.agent_messages = {}  # agent id -> the texts of its agent messages
        self.messages_sent = []  # (transcript line, SendMessage recipient)
        self.full_checks = []  # the transcript lines of the shell calls that ran a full check
        with open(path, encoding="utf-8") as fh:
            for n, line in enumerate(fh):
                self.read_record(n, json.loads(line))

    def read_record(self, n, rec):
        content = (rec.get("message") or {}).get("content")
        if self.prompt is None and rec.get("type") == "user":
            self.prompt = text_of(content)

        carrier = text_of(content) if rec.get("type") == "user" else ""
        carrier += " " + str((rec.get("attachment") or {}).get("prompt") or "")
        self.read_reports(carrier)

        for block in content if isinstance(content, list) else []:
            if isinstance(block, dict):
                self.read_block(n, rec.get("type"), block)

    def read_reports(self, carrier):
        for notification in NOTIFICATION.finditer(carrier):
            reports = self.notifications.setdefault(notification.group(1), [])
            if notification.group(2) is not None:
                reports.append(notification.group(2))
        for agent_id, report in AGENT_MESSAGE.findall(carrier):
            self.agent_messages.setdefault(agent_id, []).append(report)

    def read_block(self, n, record_type, block):
        if block.get("type") == "text" and record_type == "assistant" and block.get("text", "").strip():
            self.last_text = block["text"]
        elif block.get("type") == "tool_use":
            self.read_tool_use(n, block)
        elif block.get("type") == "tool_result" and block.get("tool_use_id") in self.kinds:
            self.results[block["tool_use_id"]] = text_of(block.get("content"))

    def read_tool_use(self, n, block):
        tool_input = block.get("input") or {}
        if block.get("name") == "Agent":
            self.kinds[block.get("id")] = tool_input.get("subagent_type") or ""
            self.dispatched_at[block.get("id")] = n
        elif block.get("name") == "SendMessage":
            self.messages_sent.append((n, tool_input.get("to")))
        elif block.get("name") == "Bash" and full_check(str(tool_input.get("command") or "")):
            self.full_checks.append(n)

    def launched_agent(self, tool_use_id):
        """The agent id that the dispatch's tool_result names, or None."""
        launched = AGENT_ID.findall(self.results.get(tool_use_id, ""))
        return launched[0] if launched else None

    def dispatch_lines(self, kinds):
        """The transcript lines of the dispatches whose subagent_type matches kinds."""
        return [self.dispatched_at[tool_use_id] for tool_use_id, kind in self.kinds.items() if kinds.match(kind)]

    def steps(self, kinds):
        """The transcript lines of the dispatches whose subagent_type matches kinds, and of the SendMessages to the
        agents that those dispatches launched."""
        agents = {agent_id for tool_use_id, kind in self.kinds.items() if kinds.match(kind)
                  for agent_id in AGENT_ID.findall(self.results.get(tool_use_id, ""))}
        return self.dispatch_lines(kinds) + [n for n, recipient in self.messages_sent if recipient in agents]

    def open_dispatches(self):
        """The count of background dispatches that have not reported back, by task notification or agent message."""
        return sum(1 for tool_use_id, text in self.results.items()
                   if "Async agent launched" in text and tool_use_id not in self.notifications
                   and self.launched_agent(tool_use_id) not in self.agent_messages)


def scan(transcript, final=None):
    """(no full check ran after the last code change, the count of background dispatches that have not reported).
    final is the loop's last message; the transcript's last text stands in when it is None."""
    last_step = max(transcript.steps(CODERS), default=0)
    last_full = max(transcript.full_checks, default=-1)

    plan_impact = PLAN_IMPACT.search(transcript.last_text if final is None else final)
    ungated = last_full < last_step and not plan_impact
    return ungated, transcript.open_dispatches()


def reasons_for(scanned):
    ungated, open_dispatches = scanned
    if open_dispatches or not ungated:
        return []
    return [GATE_REASON]


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


def write_run_row(hook, run, lane, phase):
    """True when log-review-finding wrote the row. It writes nothing while the telemetry switch is off, and it
    prints one stderr line for each skip. With no `ledger` on PATH the row goes to review-findings.jsonl, and the
    writer's stderr line is passed on."""
    claude_dir = pathlib.Path(os.environ.get("REVIEW_LOOP_GATE_CLAUDE_DIR") or OWN_CLAUDE_DIR)
    switch_script = claude_dir / "scripts" / "telemetry" / "telemetry_enabled.sh"
    if not switch_script.is_file():
        print(
            "review-loop-gate: run row for {} skipped: {} is missing".format(run["gate"], switch_script),
            file=sys.stderr,
        )
        return False
    try:
        switch = subprocess.run(["bash", str(switch_script)], capture_output=True, timeout=10)
    except subprocess.TimeoutExpired:
        print(
            "review-loop-gate: run row for {} skipped: the telemetry switch timed out".format(run["gate"]),
            file=sys.stderr,
        )
        return False
    if switch.returncode:
        print("review-loop-gate: run row for {} skipped: telemetry is off".format(run["gate"]), file=sys.stderr)
        return False
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
    done = subprocess.run(command, env=env, cwd=hook.get("cwd") or None, capture_output=True, text=True, timeout=30)
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
    return state_dir / (re.sub(r"[^\w.-]", "_", str(session_id)) + ".jsonl")


def log_run_rows(hook, transcript):
    """Write the run rows that this session has not written yet. Never raises: a logging failure must not stop the
    loop."""
    try:
        session_id = hook.get("session_id")
        if not session_id:
            return
        runs, lane, phase = reviewer_runs(transcript)
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
            if not write_run_row(hook, run, lane, phase):
                script_utils.append_jsonl(state_file, {"tool_use_id": run["tool_use_id"], "undone": True})
    except Exception as e:
        print(f"review-loop-gate: run rows skipped, {type(e).__name__}: {e}", file=sys.stderr)


def check_dispatch(tool_input):
    prompt = tool_input.get("prompt") or ""
    if tool_input.get("subagent_type") == "review-loop" and CALLER_CODE.search(prompt) and not HANDOFF.search(prompt):
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                 "permissionDecisionReason": HANDOFF_REASON}}))


def check_stop(hook):
    transcript = LoopTranscript(hook["agent_transcript_path"])
    scanned = scan(transcript, hook.get("last_assistant_message"))
    why = [] if hook.get("stop_hook_active") else reasons_for(scanned)
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
        check_dispatch(hook.get("tool_input") or {})
    elif event == "SubagentStop" and hook.get("agent_type") == "review-loop":
        check_stop(hook)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # fail open, visibly
        print(f"review-loop-gate: skipped, {type(e).__name__}: {e}", file=sys.stderr)
