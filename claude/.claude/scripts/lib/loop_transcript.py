"""loop_transcript.py: one read of a review-loop transcript, and the checks that read only the transcript: the last
code step, whether a passed full check follows it, the open background dispatches, and a packet that names the plan
file. review_loop_gate.py (the SubagentStop backstop), handback.py (the hand-back hook) and open_child_gate.py read
transcripts through it. Not a hook itself."""
import json
import os
import re
import shlex

import script_utils

FINDING_ID_HEX_LEN = 16
FINDING_ID_PATTERN = re.compile(rf"[0-9a-f]{{{FINDING_ID_HEX_LEN}}}")
# A line `log-review-finding` prints for each finding row it writes.
PRINTED_FINDING_ID = re.compile(r"(?m)^finding_id=(" + FINDING_ID_PATTERN.pattern + r")\s*$")
AGENT_ID = re.compile(r"agentId:\s*([A-Za-z0-9-]+)")
ASYNC_LAUNCH = "Async agent launched"
RESUMED_AGENT_ID = re.compile(r"resumedAgentId\W+([A-Za-z0-9-]+)")
RESUMING_MESSAGE = re.compile(r"Resuming agent\s+([A-Za-z0-9-]+)")
# The status line of the old free-text packet form, or the "status" key of a JSON packet (minified or indented).
PLAN_IMPACT = re.compile(r'(?im)^[ \t>*`-]*status[`*]*[ \t]*:[ \t`*]*plan-impact\b'
                         r'|"status"[ \t]*:[ \t]*"[ \t`\'*]*plan-impact\b')
# One shell command ends at a ;, a | or && that joins the next command, or at a newline no backslash escapes.
SEGMENT_END = re.compile(r"&&|\|\||[;|]|(?<!\\)\n")
# A shell call that ran the review loop's full-check script, and the first line that script prints: its result.
FULL_CHECK_SCRIPT = re.compile(r"(?<![\w.-])full_check\.py(?![\w-])")
FULL_CHECK_RESULT = re.compile(r"(?m)^full check: (.*)$")
AGENT_MESSAGE = re.compile(r"<agent-message\s+from=\"([\w-]+)\">(.*?)(?=</agent-message>|<agent-message\s|\Z)", re.S)
# A task notification's tool_use_id, and its result when it carries one: a killed dispatch reports with none.
NOTIFICATION = re.compile(r"<tool-use-id>\s*([\w-]+)\s*</tool-use-id>(?:(?:(?!</task-notification>).)*?"
                          r"<result>((?:(?!</task-notification>).)*?)</result>)?", re.S)
# A task notification's task id. For an agent it is the agent id, and a notification for an agent that died (killed,
# rate-limited or errored) can carry it with no tool_use_id.
NOTIFIED_TASK = re.compile(r"<task-notification>\s*<task-id>\s*([\w-]+)\s*</task-id>")


def prompt_field(key, value):
    """A pattern for a `key: value` line of the dispatch prompt, with the markdown a prompt may wrap it in."""
    return re.compile(rf"(?im)^[ \t>*`-]*{key}[`*]*[ \t]*:[ \t`*]*{value}")


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
PLAN_EDIT_REASON = ("The packet's files_touched names the plan file {plan}. A review fix never edits the plan. Revert "
                    "that edit, and return the finding that needs a plan change with `status` set to `plan-impact`.")
GATE_REASON = ("No passed full_check.py result follows the last code change in this phase. A scoped run, "
               "including the handoff's tests-run, does not count. If a full_check.py result already follows the "
               "last code change and was not passed, do not run it again: follow Step 6's route for that result "
               "and return the packet. Otherwise run the Step 6 execution gate now.")


def text_of(content):
    if isinstance(content, str):
        return content
    return " ".join(b.get("text", "") for b in content or [] if isinstance(b, dict))


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
        self.full_check_calls = {}  # Bash tool_use_id -> transcript line, of each full_check.py call
        self.full_checks = []  # the transcript lines of the full_check.py calls whose result is `full check: passed`
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
        if tool_use_id in self.full_check_calls:
            first_result = FULL_CHECK_RESULT.search(text_of(block.get("content")))
            if first_result and first_result.group(1).strip() == "passed":
                self.full_checks.append(self.full_check_calls[tool_use_id])
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
        printed_ids = PRINTED_FINDING_ID.findall(text_of(block.get("content")))
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
        if FULL_CHECK_SCRIPT.search(command):
            self.full_check_calls[tool_use_id] = n

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


def scan(transcript, final=None, full_suite_in_ci=False):
    """(no passed full_check.py result after the last code change, the count of background dispatches that have
    not reported).
    final is the loop's last message; the transcript's last text stands in when it is None."""
    last_step = last_code_step(transcript)
    last_full = max(transcript.full_checks, default=-1)

    plan_impact = PLAN_IMPACT.search(transcript.last_text if final is None else final)
    ungated = last_full < last_step and not plan_impact and not full_suite_in_ci
    return ungated, transcript.open_dispatches()


def plan_edit_reason(transcript, packet):
    """PLAN_EDIT_REASON when the packet's files_touched names the plan file of the loop's dispatch prompt, else None."""
    plan = PROMPT_PLAN.search(transcript.prompt or "")
    if plan and touches_plan(packet.get("files_touched") or [], plan.group(1)):
        return PLAN_EDIT_REASON.format(plan=plan.group(1))
    return None


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
