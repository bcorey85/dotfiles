#!/usr/bin/env python3
"""review_loop_gate.py — deterministic checks on the review loop.

  SubagentStop (review-loop), the backstop: blocks once when no full check ran after the last code
      change: a shell call that runs a project checker, or redirects into the review-gate log, with
      no file, directory or test-name filter. For the checkers that take them, the value of
      `--manifest-path`, `-p`, `--package` or `--project` names a package or project and is no
      filter (see NON_SCOPING_FLAGS). The last coder step — a dispatch, or a SendMessage to a coder
      it dispatched — is the last code change; with none, the loop start is, since the phase changed
      code before the loop ran. A handoff `tests-run` never exempts it. A loop returning
      `status: plan-impact` owes no check, and neither does a loop in a repo whose CLAUDE.md holds the line
      `Full suite: CI` (full_check.full_suite_runs_in_ci): CI runs that repo's full suite. That repo is the one the loop
      reviewed (reviewed_root), else the hook cwd. A stop with a
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
      the count of open background dispatches), through handback.record. A count of one or more means the loop
      is waiting: `review_fix.py packet` prints `ACTION: wait-for-loop`, not stop-no-handback. A row with 0 ends
      the wait. A stop whose transcript cannot be read writes a 0 row, then fails open as before. A store write
      error is reported on stderr and never blocks the stop.
      The row also carries `ask_rows`: the file, line and printed finding_id of each `actioned=ask` row the loop
      logged, so `review_fix.py packet` can give each ask its id.
  PreToolUse (Agent): a review-loop dispatch whose prompt says `caller: code` must carry a
      `handoff:` line. A review-loop dispatch from a subagent other than the /code fork is refused: the
      nested loop cannot ask for permission or wake on its reviewer's report, so it never hands back.

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
import shlex
import subprocess
import sys

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / folder) for folder in (".", "../lib")]
import full_check as full_check_script
import handback
import script_utils

OWN_CLAUDE_DIR = pathlib.Path(__file__).resolve().parents[2]
AGENT_ID = re.compile(r"agentId:\s*([A-Za-z0-9-]+)")
ASYNC_LAUNCH = "Async agent launched"
RESUMED_AGENT_ID = re.compile(r"resumedAgentId\W+([A-Za-z0-9-]+)")
RESUMING_MESSAGE = re.compile(r"Resuming agent\s+([A-Za-z0-9-]+)")
CALLER_CODE = re.compile(r"(?i)(?<![\w-])caller[`*]*\s*[:=]\s*[`\"']?code\b")
HANDOFF = re.compile(r"(?im)^[ \t]*handoff[ \t]*:")
PLAN_IMPACT = re.compile(r"(?im)^[ \t>*`-]*status[`*]*[ \t]*:[ \t`*]*plan-impact\b")
REDIRECT = re.compile(r"\d*>>?\s*&?\S+|&>\s*\S+")
# One shell command ends at a ;, a | or && that joins the next command, or at a newline no backslash escapes.
SEGMENT_END = re.compile(r"&&|\|\||[;|]|(?<!\\)\n")
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
GATE_LOG = re.compile(r"(?:>\s*|\btee\s+(?:-a\s+)?|--log[=\s]+)\S*review-gate[\w.-]*\.log")
# A checker opens the command, a segment of it, or the words after `--` that full_check.py runs.
CHECKER = re.compile(r"(?:\A|[;&|(]\s*|\n\s*|\s--\s+['\"]?)(?:cd\s+\S+\s*&&\s*)?(?:[A-Za-z_]\w*=\S+\s+)*"
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
# A task notification's task id. For an agent it is the agent id, and a notification for an agent that died (killed,
# rate-limited or errored) can carry it with no tool_use_id.
NOTIFIED_TASK = re.compile(r"<task-notification>\s*<task-id>\s*([\w-]+)\s*</task-id>")
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


def prompt_field(key, value):
    """A pattern for a `key: value` line of the dispatch prompt, with the markdown a prompt may wrap it in."""
    return re.compile(rf"(?im)^[ \t>*`-]*{key}[`*]*[ \t]*:[ \t`*]*{value}")


PROMPT_LANE = prompt_field("lane", r"(eng-spec|code|test-audit|other|none)\b")
PROMPT_PLAN = prompt_field("plan", r"(\S+?)[`*]*[ \t]*$")
HELPER_ASSIGNMENT = re.compile(r"(?:^|[\s;&|])(\w+)=[\"']?[^\s;&|\"']*log-review-finding[\"']?(?=[\s;&|]|$)")
FINDING_CALL_TAIL = r"\s+kind=finding\b"
FINDING_CALL_ARGUMENTS_TAIL = rf"\s+(kind=finding\b(?:(?!{SEGMENT_END.pattern}).)*)"
SHELL_VARIABLE_DIRECTORY = re.compile(r"^\$\{?\w+\}?/")
METRICS_CALL = re.compile(r"log-review-metrics\b")
METRICS_REFUSAL = "refusing to log"
SCOPE_CALL = re.compile(r"review-scope\b")
SCOPE_ROOT = re.compile(r"(?m)^ROOT=(\S.*?)\s*$")
PROMPT_REPO = prompt_field("repo", r"(\S+?)[`*]*[ \t]*$")
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
PLAN_EDIT_REASON = ("The packet's files_touched names the plan file {plan}. A review fix never edits the plan. Revert "
                    "that edit, and return the finding that needs a plan change as `status: plan-impact`.")
GATE_REASON = ("No full check ran after the last code change in this phase. A scoped run, including the "
               "handoff's tests-run, does not count. Run the Step 6 execution gate now: the project's full "
               "quality-check command once, through Step 6's full_check.py call. Route the result as Step 6 "
               "says, then return the packet.")
HANDOFF_REASON = ("A review-loop dispatch from /code carries no handoff block. Build it per "
                  "~/.claude/skills/_shared/handoff-block.md and dispatch again.")
NESTED_REASON = ("Run /review from the main session: a review-loop that a subagent dispatches cannot ask for "
                 "permission or wake on its reviewer's report, so it ends with no hand-back.")


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


def finding_call_pattern(command, tail):
    """A pattern for a call of the log helper followed by `tail`, in the command's own spelling: the helper's name, or
    a shell variable the command set to a path that ends in it (`L=<skills dir>/review/log-review-finding`)."""
    variables = [rf"\$(?:\{{{re.escape(name)}\}}|{re.escape(name)}\b)" for name in HELPER_ASSIGNMENT.findall(command)]
    return re.compile("(?:" + "|".join(["log-review-finding", *variables]) + ")" + tail)


def finding_call_fields(arguments):
    """The key=value fields of one log-review-finding call's argument text. A word with no `=`, such as a shell
    variable that stands for fields, is no field."""
    try:
        words = shlex.split(arguments)
    except ValueError:
        words = arguments.split()
    return dict(word.split("=", 1) for word in words if "=" in word)


def metrics_calls(command):
    """The key=value fields of each log-review-metrics call in one command, in order."""
    calls = []
    for match in METRICS_CALL.finditer(command):
        rest = command[match.end():]
        end = SEGMENT_END.search(rest)
        arguments = rest[:end.start()] if end else rest
        calls.append(finding_call_fields(arguments))
    return calls


class LoopTranscript:
    """One read of a loop transcript: what the stop check and the run rows need from it."""

    def __init__(self, path):
        self.prompt, self.last_text = None, ""
        self.kinds = {}  # dispatch tool_use_id -> subagent_type, in dispatch order
        self.dispatched_at = {}  # dispatch tool_use_id -> transcript line
        self.results = {}  # dispatch tool_use_id -> the text of its tool_result
        self.notifications = {}  # tool_use_id -> the results its task notifications carried, [] for none
        self.agent_messages = {}  # agent id -> the texts of its agent messages
        self.notified_at = {}  # tool_use_id -> the transcript lines of its task notifications
        self.task_notified_at = {}  # task id (an agent id for an agent) -> the transcript lines of its notifications
        self.messaged_at = {}  # agent id -> the transcript lines of its agent messages
        self.messages_sent = []  # (transcript line, SendMessage recipient)
        self.send_lines = {}  # SendMessage tool_use_id -> (transcript line, recipient)
        self.resumes = []  # (transcript line, agent id, SendMessage tool_use_id) of each resume
        self.background_shells = []  # (transcript line, tool_use_id) of the shell calls that run on in the background
        self.handback_ids = set()  # tool_use_ids of the SubagentHandback calls
        self.handback_lines = []  # the transcript lines of the SubagentHandback calls a hook did not deny
        self.finding_rows_logged = 0  # per-finding ledger rows the loop's own Bash calls wrote
        self.metrics_calls = []  # (transcript line, key=value fields, Bash tool_use_id) of each log-review-metrics call
        self.scope_calls = set()  # Bash tool_use_ids of the review-scope calls
        self.scope_root = None  # the ROOT= that the last review-scope call printed
        self.finding_calls = {}  # Bash tool_use_id -> the key=value fields of each `kind=finding` call, in order
        self.ask_rows = []  # {file, line, finding_id} of each `actioned=ask` row whose id the log helper printed
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
        self.read_reports(n, carrier)

        blocks = [block for block in content if isinstance(block, dict)] if isinstance(content, list) else []
        for block in blocks:
            self.read_block(n, rec.get("type"), block)

        shell_result = rec.get("toolUseResult")
        if isinstance(shell_result, dict) and shell_result.get("backgroundTaskId"):
            self.background_shells += [(n, block.get("tool_use_id")) for block in blocks
                                       if block.get("type") == "tool_result"]

    def read_reports(self, n, carrier):
        for notification in NOTIFICATION.finditer(carrier):
            reports = self.notifications.setdefault(notification.group(1), [])
            self.notified_at.setdefault(notification.group(1), []).append(n)
            if notification.group(2) is not None:
                reports.append(notification.group(2))
        for task_id in NOTIFIED_TASK.findall(carrier):
            self.task_notified_at.setdefault(task_id, []).append(n)
        for agent_id, report in AGENT_MESSAGE.findall(carrier):
            self.agent_messages.setdefault(agent_id, []).append(report)
            self.messaged_at.setdefault(agent_id, []).append(n)

    def read_block(self, n, record_type, block):
        if block.get("type") == "text" and record_type == "assistant" and block.get("text", "").strip():
            self.last_text = block["text"]
        elif block.get("type") == "tool_use":
            self.read_tool_use(n, block)
        elif block.get("type") == "tool_result" and block.get("tool_use_id") in self.handback_ids:
            if not block.get("is_error"):
                self.handback_lines.append(n)
        elif block.get("type") == "tool_result" and block.get("tool_use_id") in self.kinds:
            self.results[block["tool_use_id"]] = text_of(block.get("content"))
        elif block.get("type") == "tool_result" and block.get("tool_use_id") in self.send_lines:
            self.read_send_result(block)
        elif block.get("type") == "tool_result":
            self.read_bash_result(block)

    def read_bash_result(self, block):
        """One Bash call can chain a finding row, a metrics row and a scope call, so each check reads the result."""
        tool_use_id = block.get("tool_use_id")
        if tool_use_id in self.finding_calls:
            self.read_printed_finding_ids(block)
        refused = block.get("is_error") or METRICS_REFUSAL in text_of(block.get("content"))
        if tool_use_id in self.metrics_ids() and refused:
            self.metrics_calls = [call for call in self.metrics_calls if call[2] != tool_use_id]
        if tool_use_id in self.scope_calls:
            root = SCOPE_ROOT.search(text_of(block.get("content")))
            self.scope_root = root.group(1) if root else self.scope_root

    def metrics_ids(self):
        return {tool_use_id for _, _, tool_use_id in self.metrics_calls}

    def read_printed_finding_ids(self, block):
        """Pair each `kind=finding` call of a command with the finding_id the helper printed for it, in order, and keep
        the pairs of the ask rows. A command whose printed ids do not number its calls (one failed) pairs nothing: an
        id on the wrong row is worse than none."""
        calls = self.finding_calls[block["tool_use_id"]]
        printed_ids = handback.PRINTED_FINDING_ID.findall(text_of(block.get("content")))
        if len(calls) != len(printed_ids):
            return
        for fields, finding_id in zip(calls, printed_ids, strict=True):
            if fields.get("actioned") == "ask":
                path = SHELL_VARIABLE_DIRECTORY.sub("", fields.get("file", ""))
                self.ask_rows.append({"file": path, "line": script_utils.first_number(fields.get("line")) or 0,
                                      "finding_id": finding_id})

    def read_send_result(self, block):
        """Record a SendMessage that resumed an agent. The result names the agent in full as `resumedAgentId`; its
        message carries only a short prefix of that id, which stands in when the key is absent."""
        text = text_of(block.get("content"))
        full_id = RESUMED_AGENT_ID.search(text)
        short_id = RESUMING_MESSAGE.search(text)
        if full_id:
            agent_id = full_id.group(1)
        elif short_id:
            known_agents = [self.launched_agent(tool_use_id) for tool_use_id in self.results]
            agent_id = next((known for known in known_agents if known and known.startswith(short_id.group(1))),
                            short_id.group(1))
        else:
            return
        self.resumes.append((self.send_lines[block["tool_use_id"]][0], agent_id, block["tool_use_id"]))

    def read_tool_use(self, n, block):
        tool_input = block.get("input") or {}
        if block.get("name") == "Agent":
            self.kinds[block.get("id")] = tool_input.get("subagent_type") or ""
            self.dispatched_at[block.get("id")] = n
        elif block.get("name") == "SendMessage":
            self.messages_sent.append((n, tool_input.get("to")))
            self.send_lines[block.get("id")] = (n, tool_input.get("to"))
        elif block.get("name") == "SubagentHandback":
            self.handback_ids.add(block.get("id"))
        elif block.get("name") == "Bash":
            self.read_command(n, block.get("id"), str(tool_input.get("command") or ""))

    def read_command(self, n, tool_use_id, command):
        command = command.replace("\\\n", " ")
        self.finding_rows_logged += len(finding_call_pattern(command, FINDING_CALL_TAIL).findall(command))
        arguments_pattern = finding_call_pattern(command, FINDING_CALL_ARGUMENTS_TAIL)
        finding_calls = [finding_call_fields(arguments) for arguments in arguments_pattern.findall(command)]
        if finding_calls:
            self.finding_calls[tool_use_id] = finding_calls
        self.metrics_calls += [(n, fields, tool_use_id) for fields in metrics_calls(command)]
        if SCOPE_CALL.search(command):
            self.scope_calls.add(tool_use_id)
        if full_check(command):
            self.full_checks.append(n)

    def reviewed_root(self):
        """The repo the loop reviewed: the ROOT= review-scope printed, else the prompt's `repo:` line, when it names a
        directory that still exists; else None."""
        repo = PROMPT_REPO.search(self.prompt or "")
        named = os.path.expanduser(repo.group(1).strip("`\"'")) if repo else None
        candidates = [path for path in (self.scope_root, named) if path and os.path.isdir(path)]
        return candidates[0] if candidates else None

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

    def open_launches(self):
        """The tool_use_ids of background launches that have not reported back, by task notification (keyed by the
        launch's tool_use_id or by the launched agent's id) or agent message. Only a result that starts with the
        launch text is a launch: a foreground report may quote it."""
        return [tool_use_id for tool_use_id, text in self.results.items()
                if text.lstrip().startswith(ASYNC_LAUNCH) and tool_use_id not in self.notifications
                and self.launched_agent(tool_use_id) not in self.agent_messages
                and self.launched_agent(tool_use_id) not in self.task_notified_at]

    def resume_is_open(self, line, agent_id, send_id, open_launches):
        """True when a SendMessage that resumed `agent_id` has had no agent message from it and no task notification
        on a later transcript line, keyed by the SendMessage's id (the harness's key for a resumed agent), by its
        launch's, or by the agent's task id. A launch that is itself still open already counts."""
        launch_ids = [tool_use_id for tool_use_id in self.results if self.launched_agent(tool_use_id) == agent_id]
        if any(tool_use_id in open_launches for tool_use_id in launch_ids):
            return False
        later_reports = [*self.messaged_at.get(agent_id, []), *self.task_notified_at.get(agent_id, []),
                         *self.notified_at.get(send_id, []),
                         *(at for tool_use_id in launch_ids for at in self.notified_at.get(tool_use_id, []))]
        return not any(at > line for at in later_reports)

    def open_dispatches(self):
        """The count of background dispatches that have not reported back, including each background resume of an
        agent whose earlier notification already closed its launch, and each background shell call with no task
        notification yet, unless its result comes before the loop's last delivered SubagentHandback (the caller
        already holds the packet)."""
        open_launches = self.open_launches()
        open_resumes = [resume for resume in self.resumes if self.resume_is_open(*resume, open_launches)]
        last_handback = max(self.handback_lines, default=-1)
        open_shells = [tool_use_id for line, tool_use_id in self.background_shells
                       if line > last_handback and tool_use_id not in self.notifications]
        return len(open_launches) + len(open_resumes) + len(open_shells)


def last_code_step(transcript):
    """The transcript line of the loop's last coder dispatch or message to a coder, 0 when there is none."""
    return max(transcript.steps(script_utils.CODERS), default=0)


def full_suite_in_ci(transcript, cwd):
    """True when the repo the loop reviewed (else the repo holding cwd, the process cwd when empty) leaves its full
    suite to CI."""
    repo = script_utils.repo_root(transcript.reviewed_root() or cwd or os.getcwd())
    return repo is not None and full_check_script.full_suite_runs_in_ci(repo)


def scan(transcript, final=None, full_suite_in_ci=False):
    """(no full check ran after the last code change, the count of background dispatches that have not reported).
    final is the loop's last message; the transcript's last text stands in when it is None."""
    last_step = last_code_step(transcript)
    last_full = max(transcript.full_checks, default=-1)

    plan_impact = PLAN_IMPACT.search(transcript.last_text if final is None else final)
    ungated = last_full < last_step and not plan_impact and not full_suite_in_ci
    return ungated, transcript.open_dispatches()


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


def plan_edit_reason(transcript, packet):
    """PLAN_EDIT_REASON when the packet's files_touched names the plan file of the loop's dispatch prompt, else None."""
    plan = PROMPT_PLAN.search(transcript.prompt or "")
    if plan and touches_plan(packet.get("files_touched") or [], plan.group(1)):
        return PLAN_EDIT_REASON.format(plan=plan.group(1))
    return None


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


def touches_plan(files_touched, plan):
    """True when a files_touched entry names the plan file, as the same path or as a path that ends the other."""
    plan_path = plan.strip("`\"'")
    touched_paths = [path for entry in files_touched for path in re.split(r"[\s,\[\]]+", str(entry))]
    for entry in touched_paths:
        touched = entry.strip("`\"'")
        if touched and (touched == plan_path or touched.endswith("/" + plan_path.lstrip("./"))
                        or plan_path.endswith("/" + touched.lstrip("./"))):
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
    return state_dir / (re.sub(r"[^\w.-]", "_", str(session_id)) + ".jsonl")


def log_run_rows(hook, transcript):
    """Write the run rows that this session has not written yet. Never raises: a logging failure must not stop the
    loop."""
    try:
        session_id = hook.get("session_id")
        if not session_id:
            return
        runs, lane, phase = reviewer_runs(transcript)
        root = transcript.reviewed_root()
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


def check_dispatch(hook):
    reason = dispatch_deny_reason(hook)
    if reason:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                 "permissionDecisionReason": reason}}))


def record_stop(hook, open_dispatches, ask_rows=(), blocked=False):
    """Store this stop with the count of background dispatches still open, so `review_fix.py packet` can tell a loop
    that waits on an agent from one that ended without handing back, with the ask rows the loop logged, so `packet`
    can give each ask its finding_id, and with whether the gate blocked the stop, so a reader waits for the stop
    that follows a block. Never raises: a store failure must not stop the loop."""
    try:
        session_id = hook.get("session_id")
        if session_id:
            handback.record(session_id, "stop", agent_id=hook.get("agent_id") or "unknown",
                            open_dispatches=open_dispatches, ask_rows=list(ask_rows), blocked=blocked)
    except Exception as e:
        print(f"review-loop-gate: stop row skipped, {type(e).__name__}: {e}", file=sys.stderr)


def check_stop(hook):
    try:
        transcript = LoopTranscript(hook["agent_transcript_path"])
        in_ci = full_suite_in_ci(transcript, hook.get("cwd"))
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
