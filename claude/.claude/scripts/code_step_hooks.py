"""code_step_hooks.py: the hook commands of code_step.py. The hooks write the run's event log and deny or block the
fork's calls; none writes state.json.

Imports run one way: code_step_core, code_step_boundary, code_step_hooks, code_step."""
import collections
import datetime
import json
import os
import pathlib
import sys
import time

import plan_format
import script_utils
from code_step_boundary import verification_format_failure
from code_step_core import (
    BASH_TIMEOUT_MS,
    CODER,
    FORK_AGENT_TYPE,
    FORK_STOP_BLOCK_LIMIT,
    HOOK_STAGES,
    INSTALLED_COMMAND,
    PROMPT_DENIAL_LIMIT,
    RESUME_VERB,
    SAY_MAX_AGE_SECONDS,
    StateFileError,
    dispatch_marker,
    dispatch_standing,
    expected_agent,
    is_dispatch_open,
    load_state,
    log_event,
    newest_dispatch_standing,
    own_path,
    read_events,
    say_file_in,
    state_dir,
    timed_command,
)

HookCall = collections.namedtuple("HookCall", "event cwd state run_id session_id tool_input")


def read_hook_call(require_run=True):
    # The setup every hook shares. Reads the event on stdin and returns it with the repo's state, the run id, the
    # session and the tool call's input. Returns None when the event is not an object, the repo holds no state, the
    # state is pinned to another session, or (require_run) the state has no run.
    event = json.load(sys.stdin)
    if not isinstance(event, dict):
        return None

    cwd = event.get("cwd") or "."
    state = load_state(cwd)
    if not state:
        return None

    run_id = state.get("runId")
    if require_run and not run_id:
        return None

    session_id = event.get("session_id")
    if session_id and state.get("sessionId") and session_id != state["sessionId"]:
        return None

    tool_input = event.get("tool_input") if isinstance(event.get("tool_input"), dict) else {}
    return HookCall(event, cwd, state, run_id, session_id, tool_input)


def tool_response_agent_id(tool_response):
    # The id in the tool_response of a nested Agent call that launched async, or None when the response holds none.
    if not isinstance(tool_response, dict):
        return None
    return tool_response.get("agentId")


def is_pinned_fork_event(event, state):
    # The /code fork is the one general-purpose agent in the session that /code pinned. A general-purpose agent of
    # another session, or of a session /code did not pin, is not touched. The agent type is the only thing a hook
    # event records about the fork (its description is not in the event).
    session_id = event.get("session_id")
    pinned_session = state.get("sessionId")
    return event.get("agent_type") == FORK_AGENT_TYPE and bool(session_id) and session_id == pinned_session


def deny_early_fork_handback(cwd, state):
    # The fork's hand-back while a coder or review-loop is still out leaves that agent's report with nobody to read
    # it. Deny it once per dispatch and name the command that waits.
    standing = newest_dispatch_standing(cwd, state)
    already_denied = any(block.get("kind") == "handback-deny" for block in standing["blocks"])
    if already_denied or not is_dispatch_open(cwd, state):
        return

    log_event(cwd, state["runId"], "fork-block", state.get("sessionId"), dispatch=standing["dispatch"]["id"],
              kind="handback-deny")
    reason = (f"A dispatched agent has not handed back yet. Do not hand back. Run `{own_path(INSTALLED_COMMAND)} "
              f"{RESUME_VERB}` with Bash timeout {BASH_TIMEOUT_MS}: it waits for the hand-back and "
              "prints the next action.")
    script_utils.pre_tool_use_deny(reason)


def command_hook():
    # PreToolUse on SubagentHandback: every attempt is logged, then the pinned fork's early hand-back is denied once
    # per dispatch. Claude Code runs the hooks of one matcher side by side, so this one sees an attempt that the other
    # gates deny. Only a hand-back that went through (PostToolUse) ends a wait.
    try:
        call = read_hook_call(require_run=False)
        if call is None or not call.run_id:
            return

        event, state = call.event, call.state
        if state.get("stage") != "done":
            log_event(call.cwd, call.run_id, "handback-attempt", call.session_id, agent_id=event.get("agent_id"),
                      agent_type=event.get("agent_type"), message=str(call.tool_input.get("message", "")))
        if state.get("stage") not in HOOK_STAGES or event.get("agent_type") != FORK_AGENT_TYPE:
            return
        if not is_pinned_fork_event(event, state):
            return

        deny_early_fork_handback(call.cwd, state)
    except Exception as error:
        print(f"code-step hook: {error}", file=sys.stderr)


def log_launch(call):
    marker = dispatch_marker(call.tool_input.get("prompt"))
    if marker is None or marker[0] != call.run_id:
        return

    # A launch with no agent id is logged too: the dispatch counts as launched, and the wait stops on it.
    agent_id = tool_response_agent_id(call.event.get("tool_response"))
    log_event(call.cwd, call.run_id, "launch", call.session_id, agent_id=agent_id, dispatch=marker[1])


def command_log_hook():
    # PostToolUse on Agent, SubagentHandback and SendMessage: one event per call that went through. A hand-back that
    # the PreToolUse gates denied never reaches PostToolUse, so it is never logged.
    try:
        call = read_hook_call()
        if call is None or call.state.get("stage") == "done":
            return

        tool_name = call.event.get("tool_name")
        if tool_name == "Agent":
            log_launch(call)
        elif tool_name == "SendMessage":
            log_event(call.cwd, call.run_id, "resume", call.session_id, agent_id=call.tool_input.get("to"))
        elif tool_name == "SubagentHandback":
            message = str(call.tool_input.get("message", ""))
            log_event(call.cwd, call.run_id, "handback", call.session_id, agent_id=call.event.get("agent_id"),
                      agent_type=call.event.get("agent_type"), message=message)
    except Exception as error:
        print(f"code-step log-hook: {error}", file=sys.stderr)


def relaunch_denial(call, standing):
    # The reason to deny an Agent call that launches a coder dispatch a second time, or None for any other call.
    dispatch = standing["dispatch"]
    carries_marker = dispatch_marker(call.tool_input.get("prompt")) == (call.run_id, dispatch["id"])
    if dispatch.get("agent_type") != CODER or not carries_marker:
        return None
    return (f"This dispatch was already launched (agent {standing['launched'].get('agent_id')}). Do not dispatch it "
            f"again. Run {own_path(timed_command(dispatch['verb']))}: it waits for the hand-back and prints the next "
            "action.")


def prompt_denial(call, standing):
    # The reason to deny an Agent call that does not carry the saved dispatch prompt, or None when it carries it.
    dispatch = standing["dispatch"]
    prompt_file = dispatch.get("prompt_file") or ""
    try:
        saved_prompt = pathlib.Path(prompt_file).read_text()
    except OSError:
        return None
    if script_utils.contains_ignoring_whitespace(call.tool_input.get("prompt"), saved_prompt):
        return None

    denials = sum(1 for block in standing["blocks"] if block.get("kind") == "prompt-deny")
    if denials >= PROMPT_DENIAL_LIMIT:
        return (f"This Agent call was denied {denials} times. Stop. Do not dispatch again and do not run another "
                f"verb. Tell the user the dispatch prompt in {prompt_file} could not be passed.")
    return (f"The prompt of this Agent call is not the dispatch prompt. Read {prompt_file} and pass its whole text.")


def command_dispatch_hook():
    # PreToolUse on Agent: while a coder or review-loop dispatch of the run is pending, the Agent call for that agent
    # type must carry the whole saved dispatch prompt. A coder dispatch may not be launched twice: an Agent call that
    # carries its marker after its launch is denied. A review-loop launch is never denied for a repeat, because the
    # shared hand-back store records a review-loop dispatch even when this hook denies the call.
    try:
        call = read_hook_call()
        if call is None or call.event.get("tool_name") != "Agent" or call.state.get("stage") not in HOOK_STAGES:
            return

        standing = dispatch_standing(read_events(call.cwd, call.run_id))
        dispatch = standing["dispatch"]
        if dispatch is None or dispatch.get("stage") != call.state["stage"]:
            return
        if time.time() - dispatch["ts"] > SAY_MAX_AGE_SECONDS:
            return
        if call.tool_input.get("subagent_type") != dispatch.get("agent_type"):
            return

        if standing["launched"] is not None:
            kind, reason = "relaunch", relaunch_denial(call, standing)
        else:
            kind, reason = "prompt-deny", prompt_denial(call, standing)
        if reason is None:
            return

        log_event(call.cwd, call.run_id, "fork-block", call.session_id, dispatch=dispatch["id"], kind=kind)
        script_utils.pre_tool_use_deny(reason)
    except Exception as error:
        print(f"code-step dispatch-hook: {error}", file=sys.stderr)


def command_stop_hook():
    # SubagentStop: the fork ends its turn while a dispatch is open (it answered the Agent call's immediate return
    # instead of waiting). Block that stop and name the waiting command, at most FORK_STOP_BLOCK_LIMIT times per
    # dispatch.
    try:
        event = json.load(sys.stdin)
        cwd = event.get("cwd") or "."
        state = load_state(cwd)
        if state is None or state["stage"] not in HOOK_STAGES or not state.get("runId"):
            return
        if not is_pinned_fork_event(event, state):
            return

        standing = newest_dispatch_standing(cwd, state)
        if standing["dispatch"] is None:
            return

        stop_blocks = sum(1 for block in standing["blocks"] if block.get("kind") == "stop-block")
        if stop_blocks >= FORK_STOP_BLOCK_LIMIT or not is_dispatch_open(cwd, state):
            return

        log_event(cwd, state["runId"], "fork-block", state.get("sessionId"), dispatch=standing["dispatch"]["id"],
                  kind="stop-block")
        reason = (f"The dispatched {expected_agent(state)} has not handed back. Do not stop. Run "
                  f"`{own_path(INSTALLED_COMMAND)} {RESUME_VERB}` with Bash timeout {BASH_TIMEOUT_MS}: "
                  "it waits for the hand-back and prints the next action.")
        print(json.dumps({"decision": "block", "reason": reason}))
    except Exception as error:
        print(f"code-step stop-hook: {error}", file=sys.stderr)


def command_plan_hook():
    # PostToolUse on a write to the plan file: a plan that does not parse, or whose Manual or Automated Verification
    # items cannot run, exits 2 with the lines to fix.
    try:
        event = json.load(sys.stdin)
        if not isinstance(event, dict):
            return
        cwd = event.get("cwd") or "."
        tool_input = event.get("tool_input") or {}
        edited_path = tool_input.get("file_path") if isinstance(tool_input, dict) else None
        if not isinstance(cwd, str) or not isinstance(edited_path, str) or not edited_path:
            return
        state = load_state(cwd)
        if state is None or not state.get("plan"):
            return
        plan_path = pathlib.Path(cwd) / state["plan"]
        if pathlib.Path(edited_path).resolve() != plan_path.resolve():
            return

        plan_lines = plan_path.read_text().splitlines()
        plan = plan_format.parse_plan_with_closing_phases(plan_lines)
        failure = plan_write_failure(plan, plan_lines, state["plan"], pathlib.Path(cwd))
        if failure:
            print(failure, file=sys.stderr)
            sys.exit(2)
    except ValueError:
        return
    except (OSError, StateFileError) as error:
        print(f"code-step plan-hook: {error}", file=sys.stderr)


def plan_write_failure(plan, plan_lines, plan_name, repo_dir):
    # The first message that stops a plan write: Phase Status, then Manual Verification, then Automated Verification.
    if plan["failures"]:
        return plan_format.plan_failure_message(plan, plan_name)
    manual_failure = plan_format.manual_format_failure(plan_lines, plan_name)
    if manual_failure:
        return manual_failure
    return verification_format_failure(plan_lines, plan_name, repo_dir, plan["entries"])


def command_say_hook():
    # Stop hook: print the saved user-facing text as the hook's systemMessage, keep a copy in say.log, empty say.md.
    try:
        event = json.loads(sys.stdin.read() or "{}")
        directory = state_dir(pathlib.Path(event.get("cwd") or os.getcwd()))
        if directory is None or not say_file_in(directory).exists():
            return
        say_path = say_file_in(directory)
        is_stale = time.time() - say_path.stat().st_mtime > SAY_MAX_AGE_SECONDS
        text = say_path.read_text().strip()
        say_path.write_text("")
        if not text or is_stale:
            return
        with open(directory / "say.log", "a") as log_file:
            log_file.write(f"--- {datetime.datetime.now().isoformat()}\n{text}\n")
        print(json.dumps({"systemMessage": text}))
    except Exception as error:
        print(f"code-step say-hook: {error}", file=sys.stderr)
