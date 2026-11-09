"""The model calls of the scripted review loop and their call log.

A `claude -p` call runs one model step. A reviewer that the main session dispatched (reviewer_dispatch.py) runs no
process here; it gets a call log row with no token count, since its tokens land in the main session's own usage.
"""
import json
import os
import threading
import time

import full_check_gate
import script_utils

CALL_TIMEOUT_SECONDS = 1800
TOKEN_FIELDS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
TERMINAL_PANE_ENV = ("HERDR_ENV", "HERDR_PANE_ID", "HERDR_SOCKET_PATH", "TUIOS_SOCKET")
CHILD_ENV = {**{name: value for name, value in os.environ.items() if name not in TERMINAL_PANE_ENV},
             "CLAUDE_FORMAT_HOOK_OFF": "1"}
# The `via` of a call log row for a reviewer the main session dispatched as a subagent.
VIA_MAIN = "main"

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


def next_call_number():
    with CALLS_LOCK:
        CALLS.append(None)
        return len(CALLS)


def record_call(out, sequence, record):
    """Puts the finished call's row in CALLS and appends it to <out>/calls.jsonl."""
    with CALLS_LOCK:
        CALLS[sequence - 1] = record
        script_utils.append_jsonl(out / "calls.jsonl", record)


def record_main_dispatch(out, role, agent, wall):
    """The call log row of a reviewer the main session ran as a subagent."""
    sequence = next_call_number()
    record = {"n": sequence, "role": role, "agent": agent, "model": None, "session": "", "wall": wall, "rc": 0,
              "tokens": 0, "via": VIA_MAIN}
    record_call(out, sequence, record)


def claude_call(role, prompt, repo, out, agent=None, model=None, tools=None):
    """One `claude -p` model step. Returns the result text. A call that fails or prints no JSON reply raises. The
    prompt goes on stdin: a round-two prompt holds the fix diff and can pass the 128 KB limit of one argument."""
    command = ["claude", "-p", "--output-format", "json", "--permission-mode", "auto",
               "--name", f"child of {PARENT_SESSION['label']} ({role})"]
    if agent:
        command += ["--agent", agent]
        skills_prompt = script_utils.preloaded_skills_prompt(agent)
        if skills_prompt:
            command += ["--append-system-prompt", skills_prompt]
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

    sequence = next_call_number()
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
    record_call(out, sequence, record)

    if return_code != 0 or not replied:
        said = f" saying \"{script_utils.one_line(text)}\"" if text.strip() else ""
        raise RuntimeError(f"the {role} call failed (exit {return_code}){said}; reply {raw}, stderr {errors}")
    return text
