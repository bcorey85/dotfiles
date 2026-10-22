#!/usr/bin/env python3
"""review-loop-gate.py — deterministic checks on the review loop.

  SubagentHandback (PreToolUse, review-loop): refuses the loop's first hand-back while either check
    below would block, with the same reasons, so the loop can still act before its report goes out.
    The hand-back's own message stands in for the loop's last text. A second hand-back after a
    refusal goes through, and the stop check then stays quiet. Register with matcher
    `SubagentHandback`; the agent_type check still guards the other agents.
  SubagentStop (review-loop), the backstop: blocks once, with every reason that holds, when
    - a fix coder ran after the last code-reviewer read — a fresh dispatch, or a SendMessage to a
      code-reviewer it dispatched. `no-review` in the loop prompt exempts this check only.
    - no full check ran after the last code change: a shell call that runs a project checker, or
      redirects into the review-gate log, with no file, directory or test-name filter. For the
      checkers that take them, the value of `--manifest-path`, `-p`, `--package` or `--project`
      names a package or project and is no filter (see NON_SCOPING_FLAGS). The last
      coder step — a dispatch, or a SendMessage to a coder it dispatched — is the last code change;
      with none, the loop start is, since the phase changed code before the loop ran. A handoff
      `tests-run` never exempts it. A loop returning `status: plan-impact` owes no check.
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
    `n_findings` null, never a guessed count. Each dispatch (tool_use_id) is written once per session, so a repeat stop adds nothing. The
    gate applies the telemetry switch before it calls the logger; a logging failure never blocks a stop.

Hook JSON on stdin; on a violation, a decision JSON on stdout; exit 0 always. Any parse
failure passes (fail open) and says why on stderr: this gate adds a check, it must never
stop the loop on its own error.

Dry run for a saved transcript:  review-loop-gate.py --check <loop transcript.jsonl>
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
try:
    import script_utils
except ImportError:  # without the helpers each check keeps its stricter reading: it blocks where it could pass
    script_utils = None

CODERS = re.compile(r"^(backend-|frontend-)?coder(-deep)?$")
REVIEWERS = re.compile(r"^code-reviewer(-deep)?$")
AGENT_ID = re.compile(r"agentId:\s*([A-Za-z0-9-]+)")
REPORTED_TOOL_USE = re.compile(r"<tool-use-id>\s*([\w-]+)\s*</tool-use-id>")
REPORTED_AGENT = re.compile(r"<agent-message\s+from=\"([\w-]+)\"")
CALLER_CODE = re.compile(r"(?i)(?<![\w-])caller[`*]*\s*[:=]\s*[`\"']?code\b")
HANDOFF = re.compile(r"(?im)^[ \t]*handoff[ \t]*:")
NO_REVIEW = re.compile(r"(?<![\w-])no-review(?![\w-])")
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
NOTIFICATION_RESULT = re.compile(r"<tool-use-id>\s*([\w-]+)\s*</tool-use-id>(?:(?!</task-notification>).)*?"
                                 r"<result>((?:(?!</task-notification>).)*?)</result>", re.S)
NIT_SECTION = re.compile(r"(?mi)^\s*#{2,4}\s*[*_`]*Nits?\b")
FENCE =re.compile(r"^(```|~~~)")
HEADING_MARKUP = re.compile(r"[*_`:]")
SECTION_HEADING = re.compile(r"^(#{2,4})\s*(.*)")
LIST_MARKER = re.compile(r"^(?:[-*+]|\d+[.)])\s+")
PATH_TOKEN = r"`?[\w@~+./-]*[./][\w@~+./-]*"
ENTRY_START = re.compile(r"^(?:\*{0,2}\[blocker\]\*{0,2}\s*)?\*{0,2}(?:%s:\d[\d,\u2013-]*`?(?!\w)|%s`?\s+[\u2014\u2013-])"
                         % (PATH_TOKEN, PATH_TOKEN))
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

PASS_REASON = ("A fix coder ran after the last code-reviewer read of this loop, so its fix diff is unread. "
               "Run Step 5d now: dispatch one code-reviewer scoped to every unread fix diff, route its "
               "findings, then return the packet.")
GATE_REASON = ("No full check ran after the last code change in this phase. A scoped run, including the "
               "handoff's tests-run, does not count. Run the Step 6 execution gate now: the project's full "
               "quality-check command once, redirected to /tmp/review-gate.log. Route any failure as Step 6 "
               "says, then return the packet.")
HANDBACK_REFUSED = (" Your hand-back was refused before it went out, so you can still act: do this, then call "
                    "SubagentHandback again.")
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
    if script_utils is None:
        return arguments
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


def scan(path, final=None):
    """(a coder ran after the last reviewer read, no full check ran after the last code change, the loop prompt
    holds no-review, the count of background dispatches that have not reported). final is the loop's last message;
    the transcript's last text stands in when it is None."""
    kinds, reviewer_ids, coder_ids = {}, set(), set()
    background, reported_tool_uses, reported_agents = {}, set(), set()
    last_coder, last_step, last_read, last_full, prompt, last_text = -1, 0, -1, -1, None, ""
    with open(path, encoding="utf-8") as fh:
        for n, line in enumerate(fh):
            rec = json.loads(line)
            msg = rec.get("message") or {}
            content = msg.get("content")
            if prompt is None and rec.get("type") == "user":
                prompt = text_of(content)
            report_text = text_of(content) if rec.get("type") == "user" else ""
            report_text += " " + str((rec.get("attachment") or {}).get("prompt") or "")
            reported_tool_uses.update(REPORTED_TOOL_USE.findall(report_text))
            reported_agents.update(REPORTED_AGENT.findall(report_text))
            for b in content if isinstance(content, list) else []:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text" and rec.get("type") == "assistant" and b.get("text", "").strip():
                    last_text = b["text"]
                elif b.get("type") == "tool_use":
                    inp = b.get("input") or {}
                    if b.get("name") in ("Agent", "Task"):
                        kind = inp.get("subagent_type") or ""
                        kinds[b.get("id")] = kind
                        if CODERS.match(kind):
                            last_coder = last_step = n
                        elif REVIEWERS.match(kind):
                            last_read = n
                    elif b.get("name") == "SendMessage" and inp.get("to") in reviewer_ids:
                        last_read = n
                    elif b.get("name") == "SendMessage" and inp.get("to") in coder_ids:
                        last_step = n
                    elif b.get("name") == "Bash":
                        if full_check(str(inp.get("command") or "")):
                            last_full = n
                elif b.get("type") == "tool_result":
                    result_text = text_of(b.get("content"))
                    if b.get("tool_use_id") in kinds and "Async agent launched" in result_text:
                        launched = AGENT_ID.findall(result_text)
                        background[b.get("tool_use_id")] = launched[0] if launched else None
                    kind = kinds.get(b.get("tool_use_id"), "")
                    ids = reviewer_ids if REVIEWERS.match(kind) else coder_ids if CODERS.match(kind) else None
                    if ids is not None:
                        ids.update(AGENT_ID.findall(result_text))
    ungated = last_full < last_step and not PLAN_IMPACT.search(last_text if final is None else final)
    open_dispatches = sum(1 for tool_use_id, agent_id in background.items()
                          if tool_use_id not in reported_tool_uses and agent_id not in reported_agents)
    return last_coder > last_read, ungated, bool(NO_REVIEW.search(prompt or "")), open_dispatches


def reasons_for(scanned):
    unread, ungated, exempt, open_dispatches = scanned
    if open_dispatches:
        return []
    return [r for r, hit in ((PASS_REASON, unread and not exempt), (GATE_REASON, ungated)) if hit]


def reasons(path, final=None):
    return reasons_for(scan(path, final))


def section_findings(lines):
    """The findings in one report section: its top-level list items, or entry lines that open with a path. Prose
    before, between or after the entries is not counted. 0 when the section opens with a line that is only a none
    marker; None when the section has text and no entry to count."""
    content = [raw for raw in lines if raw.strip()]
    if not content:
        return 0
    if NO_ENTRIES.match(LIST_MARKER.sub("", content[0].strip())):
        return 0
    indents = [len(raw) - len(raw.lstrip()) for raw in content if LIST_MARKER.match(raw.strip()) or ENTRY_START.match(raw.strip())]
    if not indents:
        return None
    return indents.count(min(indents))


def count_findings(report):
    """The number of findings in a reviewer report, or None when the count would be a guess: the text is no
    review report, or a section that holds findings has text and no entry in it."""
    holds_findings = next((counts for heading, counts in LAYOUTS if heading.search(report)), None)
    if holds_findings is None:
        return None
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
    total = 0
    for lines in sections:
        found = section_findings(lines)
        if found is None:
            return None
        total += found
    assessment = ASSESSMENT.search(report)
    if total == 0 and assessment and assessment.group(1) == "NEEDS CHANGES":
        return None
    if total == 0 and assessment and assessment.group(1) == "PASS WITH WARNINGS" and not NIT_SECTION.search(report):
        return None
    return total


def reviewer_runs(path):
    """([{tool_use_id, gate, n_findings, result}], lane, phase) for every reviewer dispatch of the loop. The report
    is the dispatch's tool_result, the result of its task notification, or an agent message from the agent that
    the dispatch launched; the first one that counts is used. n_findings is None when none of them counts."""
    kinds, agent_of, foreground = {}, {}, {}
    by_tool_use, by_agent, prompt = {}, {}, None
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            content = (rec.get("message") or {}).get("content")
            if prompt is None and rec.get("type") == "user":
                prompt = text_of(content)
            carrier = text_of(content) if rec.get("type") == "user" else ""
            carrier += " " + str((rec.get("attachment") or {}).get("prompt") or "")
            for tool_use_id, report in NOTIFICATION_RESULT.findall(carrier):
                by_tool_use.setdefault(tool_use_id, []).append(report)
            for agent_id, report in AGENT_MESSAGE.findall(carrier):
                by_agent.setdefault(agent_id, []).append(report)
            for b in content if isinstance(content, list) else []:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "tool_use" and b.get("name") in ("Agent", "Task"):
                    kinds[b.get("id")] = (b.get("input") or {}).get("subagent_type") or ""
                elif b.get("type") == "tool_result" and b.get("tool_use_id") in kinds:
                    result_text = text_of(b.get("content"))
                    foreground[b["tool_use_id"]] = result_text
                    launched = AGENT_ID.findall(result_text)
                    agent_of[b["tool_use_id"]] = launched[0] if launched else None
    runs = []
    for tool_use_id, gate in kinds.items():
        if not RUN_GATES.search(gate):
            continue
        texts = [foreground.get(tool_use_id, "")] + by_tool_use.get(tool_use_id, []) + by_agent.get(agent_of.get(tool_use_id), [])
        counted = [(count_findings(text), text) for text in texts]
        count, report = next(((c, t) for c, t in counted if c is not None), (None, ""))
        assessment = ASSESSMENT.search(report)
        runs.append({"tool_use_id": tool_use_id, "gate": gate, "n_findings": count, "texts": texts,
                     "result": assessment.group(1) if assessment else ""})
    lane = PROMPT_LANE.search(prompt or "")
    phase = PROMPT_PHASE.search(prompt or "")
    return runs, lane.group(1) if lane else "none", phase.group(1) if phase else "-"


def write_run_row(hook, run, lane, phase):
    """True when log-review-finding wrote the row. It writes nothing while the telemetry switch is off or `ledger`
    is not on PATH, and it prints one stderr line for each skip."""
    claude_dir = pathlib.Path(os.environ.get("REVIEW_LOOP_GATE_CLAUDE_DIR") or pathlib.Path.home() / ".claude")
    switch_script = claude_dir / "scripts" / "telemetry_enabled.sh"
    if not switch_script.is_file():
        print("review-loop-gate: run row for %s skipped: %s is missing" % (run["gate"], switch_script), file=sys.stderr)
        return False
    try:
        switch = subprocess.run(["bash", str(switch_script)], capture_output=True, timeout=10)
    except subprocess.TimeoutExpired:
        print("review-loop-gate: run row for %s skipped: the telemetry switch timed out" % run["gate"], file=sys.stderr)
        return False
    if switch.returncode:
        print("review-loop-gate: run row for %s skipped: telemetry is off" % run["gate"], file=sys.stderr)
        return False
    if not shutil.which("ledger"):
        print("review-loop-gate: run row for %s skipped: ledger is not on PATH" % run["gate"], file=sys.stderr)
        return False
    command = ["bash", str(claude_dir / "skills" / "review" / "log-review-finding"), "kind=run", "gate=" + run["gate"],
               "n_findings=%s" % ("null" if run["n_findings"] is None else run["n_findings"]), "lane=" + lane, "phase=" + phase]
    if run["result"]:
        command.append("result=" + run["result"])
    env = {**os.environ, "CLAUDE_CODE_SESSION_ID": hook["session_id"]}
    done = subprocess.run(command, env=env, cwd=hook.get("cwd") or None, capture_output=True, text=True, timeout=30)
    if done.returncode:
        print("review-loop-gate: run row for %s not written: %s" % (run["gate"], done.stderr.strip()), file=sys.stderr)
    return done.returncode == 0 and "run_id=" in done.stdout


def state_file_for(session_id, suffix):
    """The gate's state file for one session: run-row marks use `.jsonl`, hand-back marks `-handback.jsonl`."""
    state_dir = pathlib.Path(os.environ.get("REVIEW_LOOP_GATE_STATE_DIR")
                             or pathlib.Path.home() / ".claude" / "state" / "review-loop-gate")
    return state_dir / (re.sub(r"[^\w.-]", "_", str(session_id)) + suffix)


def log_run_rows(hook, path):
    """Write the run rows that this session has not written yet. Never raises: a logging failure must not stop the
    loop."""
    try:
        session_id = hook.get("session_id")
        if not session_id:
            return
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
        import script_utils
        runs, lane, phase = reviewer_runs(path)
        state_file = state_file_for(session_id, ".jsonl")
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
        print("review-loop-gate: run rows skipped, %s: %s" % (type(e).__name__, e), file=sys.stderr)


def loop_transcript(hook):
    path = hook.get("agent_transcript_path")
    if path:
        return path
    aid, top = hook.get("agent_id"), hook.get("transcript_path") or ""
    return os.path.join(top[:-len(".jsonl")], "subagents", "agent-%s.jsonl" % aid) if aid and top else None


def agent_type(hook, path):
    if hook.get("agent_type"):
        return hook["agent_type"]
    if not path:
        return None
    try:
        with open(path[:-len(".jsonl")] + ".meta.json", encoding="utf-8") as fh:
            return json.load(fh).get("agentType")
    except (OSError, ValueError):
        return None


def last_handback_event(hook):
    """What the gate last did with a hand-back from this agent: "denied", "insisted" (the agent handed back again
    after a denial, so the second hand-back went through) or "clear"; None when it has seen none."""
    mark_file = state_file_for(hook.get("session_id"), "-handback.jsonl")
    marks = script_utils.read_jsonl(mark_file)
    events = [row.get("event") for row in marks if row.get("agent_id") == hook.get("agent_id")]
    return events[-1] if events else None


def check_handback(hook):
    """PreToolUse on SubagentHandback: refuse a review-loop's first hand-back while the stop checks would block, so
    the agent can still act on the reason. The hand-back's own message stands in for the loop's last text. A second
    hand-back after a refusal goes through, so a stuck loop cannot spin; the stop check then stays quiet."""
    if hook.get("agent_type") != "review-loop" or not hook.get("session_id"):
        return
    if script_utils is None:
        raise ImportError("script_utils is not beside review-loop-gate.py; no hand-back check ran")
    path = loop_transcript(hook)
    if not path or not os.path.exists(path):
        raise FileNotFoundError("no loop transcript for agent %s" % hook.get("agent_id"))
    why = reasons(path, str((hook.get("tool_input") or {}).get("message") or ""))
    refused_before = last_handback_event(hook) in ("denied", "insisted")
    event = "clear" if not why else "insisted" if refused_before else "denied"
    # The mark goes first: when it cannot be saved the hand-back is not refused, so a stuck loop cannot spin.
    script_utils.append_jsonl(state_file_for(hook["session_id"], "-handback.jsonl"),
                              {"agent_id": hook.get("agent_id"), "event": event})
    if event == "denied":
        script_utils.pre_tool_use_deny(" ".join(why) + HANDBACK_REFUSED)


def hand_back_insisted(hook):
    """True when this agent handed back again after the gate refused its hand-back: the stop that follows has nothing
    left to ask. A mark that cannot be read is no mark."""
    try:
        return bool(hook.get("session_id")) and last_handback_event(hook) == "insisted"
    except Exception:
        return False


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--check":
        unread, ungated, exempt, open_dispatches = scan(sys.argv[2])
        print(", ".join([("unread, no-review" if exempt else "unread") if unread else "read"]
                        + (["no full check after the last code change"] if ungated else [])
                        + (["waiting on %d background dispatches" % open_dispatches] if open_dispatches else [])))
        return
    if os.environ.get("CLAUDE_SKIP_HOOKS"):
        return
    hook = json.load(sys.stdin)
    event = hook.get("hook_event_name")
    if event == "PreToolUse" and hook.get("tool_name") in ("Agent", "Task"):
        inp = hook.get("tool_input") or {}
        prompt = inp.get("prompt") or ""
        if inp.get("subagent_type") == "review-loop" and CALLER_CODE.search(prompt) and not HANDOFF.search(prompt):
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                     "permissionDecisionReason": HANDOFF_REASON}}))
    elif event == "PreToolUse" and hook.get("tool_name") == "SubagentHandback":
        check_handback(hook)
    elif event == "SubagentStop":
        path = loop_transcript(hook)
        if agent_type(hook, path) != "review-loop":
            return
        if not path or not os.path.exists(path):
            raise FileNotFoundError("no loop transcript for agent %s" % hook.get("agent_id"))
        scanned = scan(path, hook.get("last_assistant_message"))
        why = [] if hook.get("stop_hook_active") or hand_back_insisted(hook) else reasons_for(scanned)
        if why:
            print(json.dumps({"decision": "block", "reason": " ".join(why)}))
        elif not scanned[3]:
            log_run_rows(hook, path)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # fail open, visibly
        print("review-loop-gate: skipped, %s: %s" % (type(e).__name__, e), file=sys.stderr)
