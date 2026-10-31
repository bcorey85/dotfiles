"""loop_transcript.py: one read of a review-loop transcript, and the checks that read the transcript: the last
code step, whether a valid full-check receipt exists for the tree the loop reviewed (lib/full_check_receipt), the open
background dispatches, a packet that names the plan file, and a packet that owes ledger rows (per-finding rows and a
metrics line) the loop did not log. review_loop_gate.py (the SubagentStop backstop), handback.py (the hand-back hook)
and open_child_gate.py read transcripts through it. Not a hook itself."""
import json
import os
import re
import shlex

import full_check_receipt
import script_utils
import shell_command

FINDING_ID_HEX_LEN = 16
FINDING_ID_PATTERN = re.compile(rf"[0-9a-f]{{{FINDING_ID_HEX_LEN}}}")
# A line `log-review-finding` prints for each finding row it writes.
PRINTED_FINDING_ID = re.compile(r"(?m)^finding_id=(" + FINDING_ID_PATTERN.pattern + r")\s*$")
AGENT_ID = re.compile(r"agentId:\s*([A-Za-z0-9-]+)")
ASYNC_LAUNCH = "Async agent launched"
RESUMED_AGENT_ID = re.compile(r"resumedAgentId\W+([A-Za-z0-9-]+)")
RESUMING_MESSAGE = re.compile(r"Resuming agent\s+([A-Za-z0-9-]+)")
# The status line of the old free-text packet form, or the "status" key of a JSON packet (minified or indented).
# The statuses whose protocol ends the loop for a human ruling in place of Step 6's full check,
# so a hand-back with one owes no full check.
UNVERIFIED_TREE_STATUSES = frozenset({"plan-impact", "setup-fault", "critical-blocker"})
_UNVERIFIED_STATUS = "(?:" + "|".join(sorted(UNVERIFIED_TREE_STATUSES)) + ")"
UNVERIFIED_TREE_STATUS = re.compile(
    r'(?im)^[ \t>*`-]*status[`*]*[ \t]*:[ \t`*]*' + _UNVERIFIED_STATUS + r'\b'
    r'|"status"[ \t]*:[ \t]*"[ \t`\'*]*' + _UNVERIFIED_STATUS + r'\b')
# One shell command ends at a ;, a | or && that joins the next command, or at a newline no backslash escapes.
SEGMENT_END = re.compile(r"&&|\|\||[;|]|(?<!\\)\n")
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
SHELL_VARIABLE_DIRECTORY = re.compile(r"^\$\{?\w+\}?/")
NO_REVIEW_MODE = re.compile(r"(?im)^[ \t>*`-]*no-review\b")
METRICS_CALL = re.compile(r"log-review-metrics\b")
METRICS_REFUSAL = "refusing to log"
SCOPE_CALL = re.compile(r"review-scope\b")
SCOPE_ROOT = re.compile(r"(?m)^ROOT=(\S.*?)\s*$")
PROMPT_REPO = prompt_field("repo", r"(\S+?)[`*]*[ \t]*$")
PLAN_EDIT_REASON = ("The packet's files_touched names the plan file {plan}. A review fix never edits the plan. Revert "
                    "that edit, and return the finding that needs a plan change with `status` set to `plan-impact`.")
RUN_GATES = re.compile(r"-reviewer(-deep)?$")
PACKET_ROW_KEYS = ("fixed", "skipped_fp", "findings_remaining", "ask", "nit")
RETURN_TAIL = "then return the packet."
DELIVERED_TAIL = "then stop: the packet was already delivered, and a second hand-back is denied."
LEDGER_REASON = ("The packet lists {owed} finding(s) (fixed, skipped, deferred, ask, nit) but only {logged} "
                 "per-finding row(s) were logged{metrics}. Run Step 7 and Step 7b now, one "
                 "`log-review-finding kind=finding` call per finding, then return the packet.")
METRICS_ONLY_REASON = ("The loop logged its per-finding rows but there is no metrics line. Log the Step 7 metrics "
                       "line now (log-review-metrics); for a loop where no reviewer ran, use "
                       "result=\"NOT DISPATCHED\", then return the packet.")
NIT_REASON = ("The packet lists {owed} nit(s) but only {logged} `disposition=nit` row(s) were logged. Log one "
              "`log-review-finding kind=finding disposition=nit` row per nit, then return the packet.")
METRICS_REASON = ("The last metrics line was logged before the last reviewer round, or its counts differ from the "
                  "packet's. Log the Step 7 metrics line again with the final counts (fixed={fixed}, "
                  "skipped_fp={skipped_fp}), then return the packet.")
GATE_REASON = ("No valid full-check receipt exists for the work tree as it stands: {problem}. A scoped run, "
               "including the handoff's tests-run, does not count. If the latest full_check.py run did not pass, do "
               "not run it again: follow Step 6's route for its result and return the packet. Otherwise run the "
               "Step 6 execution gate now.")


def text_of(content):
    if isinstance(content, str):
        return content
    return " ".join(b.get("text", "") for b in content or [] if isinstance(b, dict))


def finding_rows(command):
    """The key=value fields of each `kind=finding` call of the log helper in one command, in order, wherever `kind`
    stands among its arguments. The helper is called by its name, a path that ends in it, or a shell variable the
    command set to such a path (`L=<skills dir>/review/log-review-finding`)."""
    names = HELPER_ASSIGNMENT.findall(command)
    helper_variables = {f"${name}" for name in names} | {f"${{{name}}}" for name in names}

    rows = []
    for words in shell_command.step_words(command):
        if not words:
            continue
        if os.path.basename(words[0]) != "log-review-finding" and words[0] not in helper_variables:
            continue
        fields = dict(word.split("=", 1) for word in words[1:] if "=" in word)
        if fields.get("kind") == "finding":
            rows.append(fields)
    return rows


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
        self.path = str(path)
        self.died = {}  # agent id -> whether its own transcript ends on an API error
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
        # log-review-finding and log-review-metrics calls the loop made, refused ones too
        self.ledger_calls_attempted = 0
        self.metrics_calls = []  # (transcript line, key=value fields, Bash tool_use_id) of each log-review-metrics call
        self.scope_calls = set()  # Bash tool_use_ids of the review-scope calls
        self.scope_root = None  # the ROOT= that the last review-scope call printed
        self.finding_calls = {}  # Bash tool_use_id -> the key=value fields of each `kind=finding` call, in order
        self.ask_rows = []  # {file, line, finding_id} of each `actioned=ask` row whose id the log helper printed
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

        # An api-request-blob record repeats the turn's blocks, so skip it: each call counts once. No other record
        # type carries tool blocks.
        if rec.get("type") not in ("user", "assistant"):
            return

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
        finding_calls = finding_rows(command)
        self.finding_rows_logged += len(finding_calls)
        if finding_calls:
            self.finding_calls[tool_use_id] = finding_calls
        logged_metrics = [(n, fields, tool_use_id) for fields in metrics_calls(command)]
        self.metrics_calls += logged_metrics
        self.ledger_calls_attempted += len(finding_calls) + len(logged_metrics)
        if SCOPE_CALL.search(command):
            self.scope_calls.add(tool_use_id)

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
        launch's tool_use_id or by the launched agent's id) or agent message, and whose agent has not ended on an API
        error. Only a result that starts with the launch text is a launch: a foreground report may quote it."""
        return [tool_use_id for tool_use_id, text in self.results.items()
                if text.lstrip().startswith(ASYNC_LAUNCH) and tool_use_id not in self.notifications
                and self.launched_agent(tool_use_id) not in self.agent_messages
                and self.launched_agent(tool_use_id) not in self.task_notified_at
                and not self.agent_died(self.launched_agent(tool_use_id))]

    def agent_died(self, agent_id):
        """True when the transcript of agent `agent_id`, kept beside this loop's own, ends on an API
        error: it may never report, so no notification need close its launch."""
        if not agent_id:
            return False
        if agent_id not in self.died:
            sibling = script_utils.sibling_transcript_path(self.path, agent_id)
            self.died[agent_id] = script_utils.ends_on_api_error(sibling)
        return self.died[agent_id]

    def dead_reviewers(self):
        """The sorted agent ids of the loop's latest dispatch of each reviewer kind whose agent ended on an API
        error, so the loop holds no finished review from that run. A re-dispatch of the same kind, or its -deep
        variant, supersedes the earlier one. Empty when none died or the loop dispatched no reviewer."""
        latest_by_kind = {kind.removesuffix("-deep"): tool_use_id for tool_use_id, kind in self.kinds.items()
                          if script_utils.REVIEWERS.match(kind)}
        agent_ids = {self.launched_agent(tool_use_id) for tool_use_id in latest_by_kind.values()}

        return sorted(agent_id for agent_id in agent_ids if self.agent_died(agent_id))

    def resume_is_open(self, line, agent_id, send_id, open_launches):
        """True when a SendMessage that resumed `agent_id` has had no agent message from it and no task notification
        on a later transcript line, keyed by the SendMessage's id (the harness's key for a resumed agent), by its
        launch's, or by the agent's task id, and whose agent has not ended on an API error. A launch that is itself
        still open already counts."""
        launch_ids = [tool_use_id for tool_use_id in self.results if self.launched_agent(tool_use_id) == agent_id]
        if any(tool_use_id in open_launches for tool_use_id in launch_ids):
            return False
        later_reports = [*self.messaged_at.get(agent_id, []), *self.task_notified_at.get(agent_id, []),
                         *self.notified_at.get(send_id, []),
                         *(at for tool_use_id in launch_ids for at in self.notified_at.get(tool_use_id, []))]
        if any(at > line for at in later_reports):
            return False
        return not self.agent_died(agent_id)

    def open_kinds(self, kinds):
        """The tool_use_ids of the dispatches whose subagent_type matches `kinds` that have not reported back: a
        background launch with no report yet whose agent has not ended on an API error, or a dispatch with no
        tool_result at all."""
        open_launches = self.open_launches()
        return [tool_use_id for tool_use_id, kind in self.kinds.items()
                if kinds.search(kind) and (tool_use_id in open_launches or tool_use_id not in self.results)]

    def open_dispatches(self):
        """The count of background dispatches that have not reported back and whose agent has not ended on an API
        error, including each background resume of an agent whose earlier notification already closed its launch, and
        each background shell call with no task notification yet, unless its result comes before the loop's last
        delivered SubagentHandback (the caller already holds the packet)."""
        open_launches = self.open_launches()
        open_resumes = [resume for resume in self.resumes if self.resume_is_open(*resume, open_launches)]
        last_handback = max(self.handback_lines, default=-1)
        open_shells = [tool_use_id for line, tool_use_id in self.background_shells
                       if line > last_handback and tool_use_id not in self.notifications]
        return len(open_launches) + len(open_resumes) + len(open_shells)


def last_code_step(transcript):
    """The transcript line of the loop's last coder dispatch or message to a coder, 0 when there is none."""
    return max(transcript.steps(script_utils.CODERS), default=0)


def missing_receipt_reason(transcript, cwd=None):
    """Why no full-check receipt is valid for the repo the loop reviewed (else the repo holding cwd, the process cwd
    when empty), or None when one is. None too when that place is no git work tree: it keeps no receipts, so the gate
    fails open there rather than ask for one that cannot exist."""
    repo = script_utils.repo_root(transcript.reviewed_root() or cwd or os.getcwd())
    if repo is None:
        return None
    return full_check_receipt.receipt_problem(repo)


def scan(transcript, final=None, cwd=None):
    """(the GATE_REASON text when no valid full-check receipt exists for the tree the loop reviewed, else None; the
    count of background dispatches that have not reported and whose agent has not ended on an API error).
    A loop that ends `plan-impact`, `setup-fault` or `critical-blocker` owes no check.
    final is the loop's last message; the transcript's last text stands in when it is None."""
    open_dispatches = transcript.open_dispatches()
    if UNVERIFIED_TREE_STATUS.search(transcript.last_text if final is None else final):
        return None, open_dispatches

    problem = missing_receipt_reason(transcript, cwd)
    if problem is None:
        return None, open_dispatches
    return GATE_REASON.format(problem=problem), open_dispatches


def plan_edit_reason(transcript, packet):
    """PLAN_EDIT_REASON when the packet's files_touched names the plan file of the loop's dispatch prompt, else None."""
    plan = PROMPT_PLAN.search(transcript.prompt or "")
    if plan and touches_plan(packet.get("files_touched") or [], plan.group(1)):
        return PLAN_EDIT_REASON.format(plan=plan.group(1))
    return None


def packet_ledger_reasons(transcript, packet):
    """The reasons for a block when the packet owes ledger rows the loop did not write: too few per-finding rows or no
    metrics line, else too few nit rows, else a metrics line older than the last reviewer round or with other counts
    than the packet. The reasons end in RETURN_TAIL."""
    owed = sum(len(packet.get(key) or []) for key in PACKET_ROW_KEYS)
    missing_metrics = not transcript.metrics_calls
    if transcript.finding_rows_logged >= owed and missing_metrics:
        return [METRICS_ONLY_REASON]
    if transcript.finding_rows_logged < owed or missing_metrics:
        metrics = " and no metrics line" if missing_metrics else ""
        return [LEDGER_REASON.format(owed=owed, logged=transcript.finding_rows_logged, metrics=metrics)]
    if unlogged_nits(transcript, packet):
        return [NIT_REASON.format(owed=len(packet.get("nit") or []), logged=nit_rows(transcript))]
    if stale_metrics(transcript, packet):
        return [METRICS_REASON.format(fixed=len(packet.get("fixed") or []),
                                      skipped_fp=len(packet.get("skipped_fp") or []))]
    return []


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
