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
    log_event,
    newest_dispatch_standing,
    own_path,
    read_events,
    read_state_file,
    say_file_in,
    session_repo_dirs,
    state_dir,
    timed_command,
)

HookCall = collections.namedtuple("HookCall", "event repo state run_id session_id tool_input")


def hook_repo_dirs(event):
    # (repo, state folder) for the event's cwd and for each repo the event's session pinned, each state folder once.
    # The cwd is the session's, so a /code run in a worktree or another checkout is found only through the session's
    # list.
    seen_directories = set()
    for repo in [event.get("cwd") or ".", *session_repo_dirs(event.get("session_id"))]:
        directory = state_dir(repo)
        if directory is None or directory in seen_directories:
            continue
        seen_directories.add(directory)
        yield repo, directory


def hook_repo_states(event):
    # (repo, state) for each repo hook_repo_dirs reaches that holds state.
    for repo, directory in hook_repo_dirs(event):
        state = read_state_file(directory)
        if state:
            yield repo, state


def read_hook_calls():
    # The setup every hook shares. Reads the event on stdin and returns one call per repo the event reaches, each with
    # the repo's state, the run id, the session and the tool call's input. A repo is left out when it holds no state,
    # its state has no run, or its state is pinned to another session.
    event = json.load(sys.stdin)
    if not isinstance(event, dict):
        return []

    session_id = event.get("session_id")
    tool_input = event.get("tool_input") if isinstance(event.get("tool_input"), dict) else {}
    calls = []
    for repo, state in hook_repo_states(event):
        run_id = state.get("runId")
        if not run_id:
            continue
        if session_id and state.get("sessionId") and session_id != state["sessionId"]:
            continue
        calls.append(HookCall(event, repo, state, run_id, session_id, tool_input))
    return calls


def tool_response_agent_id(tool_response):
    # The id in the tool_response of a nested Agent call that launched async, or None when the response holds none.
    if not isinstance(tool_response, dict):
        return None
    return tool_response.get("agentId")


def is_pinned_fork_event(event, state):
    # The /code fork is the code-fork agent in the session that /code pinned. A code-fork agent of another session,
    # or of a session /code did not pin, is not touched. The agent type is the only thing a hook event records about
    # the fork (its description is not in the event).
    session_id = event.get("session_id")
    pinned_session = state.get("sessionId")
    return event.get("agent_type") == FORK_AGENT_TYPE and bool(session_id) and session_id == pinned_session


def deny_early_fork_handback(cwd, state):
    # The fork's hand-back while a coder or review-loop is still out leaves that agent's report with nobody to read
    # it. Deny it once per dispatch and name the command that waits. True when it denied.
    standing = newest_dispatch_standing(cwd, state)
    already_denied = any(block.get("kind") == "handback-deny" for block in standing["blocks"])
    if already_denied or not is_dispatch_open(cwd, state):
        return False

    log_event(cwd, state["runId"], "fork-block", state.get("sessionId"), dispatch=standing["dispatch"]["id"],
              kind="handback-deny")
    reason = (f"A dispatched agent has not handed back yet. Do not hand back. Run `{own_path(INSTALLED_COMMAND)} "
              f"{RESUME_VERB}` with Bash timeout {BASH_TIMEOUT_MS}: it waits for the hand-back and "
              "prints the next action.")
    script_utils.pre_tool_use_deny(reason)
    return True


def log_handback_attempt(call):
    if call.state.get("stage") == "done":
        return

    log_event(call.repo, call.run_id, "handback-attempt", call.session_id, agent_id=call.event.get("agent_id"),
              agent_type=call.event.get("agent_type"), message=str(call.tool_input.get("message", "")))


def deny_handback_attempt(call):
    # Denies the pinned fork's early hand-back. True when it denied.
    event, state = call.event, call.state
    if state.get("stage") not in HOOK_STAGES or event.get("agent_type") != FORK_AGENT_TYPE:
        return False
    if not is_pinned_fork_event(event, state):
        return False

    return deny_early_fork_handback(call.repo, state)


def command_hook():
    # PreToolUse on SubagentHandback: every attempt is logged, then the pinned fork's early hand-back is denied once
    # per dispatch. Claude Code runs the hooks of one matcher side by side, so this one sees an attempt that the other
    # gates deny. Only a hand-back that went through (PostToolUse) ends a wait. One denial answers the call.
    try:
        calls = read_hook_calls()
        for call in calls:
            log_handback_attempt(call)

        for call in calls:
            if deny_handback_attempt(call):
                return
    except Exception as error:
        print(f"code-step hook: {error}", file=sys.stderr)


def log_launch(call):
    marker = dispatch_marker(call.tool_input.get("prompt"))
    if marker is None or marker[0] != call.run_id:
        return

    # A launch with no agent id is logged too: the dispatch counts as launched, and the wait stops on it.
    agent_id = tool_response_agent_id(call.event.get("tool_response"))
    log_event(call.repo, call.run_id, "launch", call.session_id, agent_id=agent_id, dispatch=marker[1])


def log_tool_call(call):
    tool_name = call.event.get("tool_name")
    if tool_name == "Agent":
        log_launch(call)
    elif tool_name == "SendMessage":
        log_event(call.repo, call.run_id, "resume", call.session_id, agent_id=call.tool_input.get("to"))
    elif tool_name == "SubagentHandback":
        message = str(call.tool_input.get("message", ""))
        log_event(call.repo, call.run_id, "handback", call.session_id, agent_id=call.event.get("agent_id"),
                  agent_type=call.event.get("agent_type"), message=message)


def command_log_hook():
    # PostToolUse on Agent, SubagentHandback and SendMessage: one event per call that went through. A hand-back that
    # the PreToolUse gates denied never reaches PostToolUse, so it is never logged.
    try:
        for call in read_hook_calls():
            if call.state.get("stage") != "done":
                log_tool_call(call)
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
        for call in read_hook_calls():
            if dispatch_denial(call):
                return
    except Exception as error:
        print(f"code-step dispatch-hook: {error}", file=sys.stderr)


def dispatch_denial(call):
    # Denies the Agent call when it breaks the pending dispatch of the call's run. True when it denied. A call that
    # carries the marker of another run belongs to that run.
    if call.event.get("tool_name") != "Agent" or call.state.get("stage") not in HOOK_STAGES:
        return False
    marker = dispatch_marker(call.tool_input.get("prompt"))
    if marker is not None and marker[0] != call.run_id:
        return False

    standing = dispatch_standing(read_events(call.repo, call.run_id))
    dispatch = standing["dispatch"]
    if dispatch is None or dispatch.get("stage") != call.state["stage"]:
        return False
    if time.time() - dispatch["ts"] > SAY_MAX_AGE_SECONDS:
        return False
    if call.tool_input.get("subagent_type") != dispatch.get("agent_type"):
        return False

    if standing["launched"] is not None:
        kind, reason = "relaunch", relaunch_denial(call, standing)
    else:
        kind, reason = "prompt-deny", prompt_denial(call, standing)
    if reason is None:
        return False

    log_event(call.repo, call.run_id, "fork-block", call.session_id, dispatch=dispatch["id"], kind=kind)
    script_utils.pre_tool_use_deny(reason)
    return True


def command_stop_hook():
    # SubagentStop: the fork ends its turn while a dispatch is open (it answered the Agent call's immediate return
    # instead of waiting). Block that stop and name the waiting command, at most FORK_STOP_BLOCK_LIMIT times per
    # dispatch. One block answers the stop.
    try:
        for call in read_hook_calls():
            if fork_stop_block(call):
                return
    except Exception as error:
        print(f"code-step stop-hook: {error}", file=sys.stderr)


def fork_stop_block(call):
    # Blocks the pinned fork's stop while the repo's dispatch is open. True when it blocked.
    repo, state = call.repo, call.state
    if state.get("stage") not in HOOK_STAGES:
        return False
    if not is_pinned_fork_event(call.event, state):
        return False

    standing = newest_dispatch_standing(repo, state)
    if standing["dispatch"] is None:
        return False

    stop_blocks = sum(1 for block in standing["blocks"] if block.get("kind") == "stop-block")
    if stop_blocks >= FORK_STOP_BLOCK_LIMIT or not is_dispatch_open(repo, state):
        return False

    log_event(repo, call.run_id, "fork-block", state.get("sessionId"), dispatch=standing["dispatch"]["id"],
              kind="stop-block")
    reason = (f"The dispatched {expected_agent(state)} has not handed back. Do not stop. Run "
              f"`{own_path(INSTALLED_COMMAND)} {RESUME_VERB}` with Bash timeout {BASH_TIMEOUT_MS}: "
              "it waits for the hand-back and prints the next action.")
    print(json.dumps({"decision": "block", "reason": reason}))
    return True


def command_plan_hook():
    # PostToolUse on a write to the plan file: a plan that does not parse, or whose Manual or Automated Verification
    # items cannot run, exits 2 with the lines to fix.
    try:
        event = json.load(sys.stdin)
        if not isinstance(event, dict):
            return
        tool_input = event.get("tool_input") or {}
        edited_path = tool_input.get("file_path") if isinstance(tool_input, dict) else None
        if not isinstance(event.get("cwd") or ".", str) or not isinstance(edited_path, str) or not edited_path:
            return

        for repo, state in hook_repo_states(event):
            if not state.get("plan"):
                continue
            plan_path = pathlib.Path(repo) / state["plan"]
            if pathlib.Path(edited_path).resolve() != plan_path.resolve():
                continue

            plan_lines = plan_path.read_text().splitlines()
            plan = plan_format.parse_plan_with_closing_phases(plan_lines)
            failure = plan_write_failure(plan, plan_lines, state["plan"], pathlib.Path(repo))
            if failure:
                print(failure, file=sys.stderr)
                sys.exit(2)
            return
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
    # Stop hook: print the saved user-facing text of the cwd's and the session's repos as one systemMessage, keep a copy
    # in each say.log, empty each say.md.
    try:
        event = json.loads(sys.stdin.read() or "{}")
        event.setdefault("cwd", os.getcwd())
        texts = [text for _, directory in hook_repo_dirs(event) if (text := take_say_text(directory))]
        if texts:
            print(json.dumps({"systemMessage": "\n\n".join(texts)}))
    except Exception as error:
        print(f"code-step say-hook: {error}", file=sys.stderr)


def take_say_text(directory):
    # The fresh text in the folder's say.md, logged to say.log, or None. Empties say.md either way.
    say_path = say_file_in(directory)
    if not say_path.exists():
        return None
    is_stale = time.time() - say_path.stat().st_mtime > SAY_MAX_AGE_SECONDS
    text = say_path.read_text().strip()
    say_path.write_text("")
    if not text or is_stale:
        return None

    with open(directory / "say.log", "a") as log_file:
        log_file.write(f"--- {datetime.datetime.now().isoformat()}\n{text}\n")
    return text
