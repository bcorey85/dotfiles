#!/usr/bin/env python3
"""fork_children.py — the live children of a /code code-fork, and the PreToolUse hook that refuses a TaskStop of a
code-fork that still has some.

`fork_children.py <fork id> [--repo PATH]` prints one JSON object: the code-fork's id, the agent ids of the coders and
reviewers it started that have not finished or been stopped, the launches whose result names no agent id yet, and
what became of the repo's detached /code review loop (stopped only when its process is this code-fork's own review
start, begun inside the code-fork's lifetime; the review-fix loop of a /review or /fix fork is never stopped here and
reads `not_code_phase`). The loop reads `stopped` once its process group exited within two seconds of the SIGTERM and
`signalled` when a process of the group is still alive then (the leader may have exited while a child lives on);
`query_failed` when `ps` could not answer.
The repo is `--repo`, else the git top level of the `cwd` of the code-fork transcript's last record, else the current
folder; with none inside a git checkout the loop reads `no_repo`. Exit 0 with the report; exit 2 for a usage error, a
missing transcript or an id that is not a code-fork; exit 1 with a `fork_children: could not signal ...` line when
`process_group.terminate_group` raises OSError (for example, a missing permission).

`fork_children.py hook` reads a PreToolUse event on stdin. It denies, once per code-fork and session, a TaskStop of a
code-fork that has a live child or an unresolved launch, and names them. Any other call passes. Any error passes and
says why on stderr (fail open): the cancel must never be blocked by a broken gate.
"""
import argparse
import json
import os
import pathlib
import sys
from typing import NamedTuple

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path[:0] = [str(SCRIPTS_DIR / folder) for folder in ("lib", "review", "code")]

import code_wait
import handback_store
import human_turn_lookup
import loop_transcript
import open_child_gate
import process_group
import script_utils

KIND_TASKSTOP_DENIED = "taskstop_children_denied"
HOOK_VERB = "hook"
REVIEW_START_SCRIPT = "code_review_start.py"
LOOP_NONE = "none"
LOOP_STOPPED = "stopped"
LOOP_GONE = "gone"
LOOP_SIGNALLED = "signalled"
LOOP_NOT_THIS_RUN = "not_this_run"
LOOP_NOT_REVIEW_LOOP = "not_review_loop"
LOOP_NOT_CODE_PHASE = "not_code_phase"
LOOP_UNKNOWN = "query_failed"
LOOP_NO_REPO = "no_repo"
REVIEW_FIX_LAUNCH = "review_fix.py launch"
STOP_WAIT_SECONDS = 2  # review/review_launch.py wait_for_exit is the sibling wait (5 s) to consolidate with
DENY_REASON = ("code fork {fork} has live children: {ids}. Run python3 {script} {fork}: TaskStop each agent id it "
               "names; for a launch with no agent id yet, rerun it once the launch result names one. It stops a /code "
               "review loop only, never a /review or /fix loop. Then TaskStop the fork.")
UNRESOLVED_LAUNCH = "launch {launch} (no agent id yet)"


def children_named_by_meta(fork_transcript, fork_id):
    """The agent ids of the sibling transcripts whose meta names the code-fork as parent."""
    folder = pathlib.Path(fork_transcript).parent
    entries = loop_transcript.subagent_entries(folder, report_torn=True)
    return [agent_id for agent_id, _transcript, meta in entries if meta.get("parentAgentId") == fork_id]


def is_live_agent(fork_transcript, agent_id):
    """False once the agent's meta file or transcript shows it finished, or its transcript shows it stopped."""
    transcript = script_utils.sibling_transcript_path(fork_transcript, agent_id)
    return not (loop_transcript.agent_finished(transcript) or loop_transcript.agent_interrupted(transcript))


def is_code_fork(transcript):
    """Whether the agent whose transcript this is was started as a code-fork."""
    return loop_transcript.agent_meta(transcript, report_torn=True).get("agentType") == open_child_gate.CODE_FORK


def child_ids(fork_transcript, fork_id):
    """(the sorted agent ids of the code-fork's live children, the sorted tool_use_ids of its launches that name no
    agent id yet). A child comes from a launch result in the code-fork's transcript or from a meta file that names the
    code-fork as parent."""
    launched = open_child_gate.live_children(loop_transcript.LoopTranscript(fork_transcript))
    unresolved = sorted(name for name in launched if not code_wait.AGENT_ID.fullmatch(name))
    launched_ids = {name for name in launched if code_wait.AGENT_ID.fullmatch(name)}
    # open_child_gate.live_children already dropped the launched ids that finished, so only the interrupt is read.
    live_launched = set()
    for agent_id in launched_ids:
        agent_transcript = script_utils.sibling_transcript_path(fork_transcript, agent_id)
        if not loop_transcript.agent_interrupted(agent_transcript):
            live_launched.add(agent_id)
    named_by_meta = set(children_named_by_meta(fork_transcript, fork_id)) - launched_ids
    live_named = {agent_id for agent_id in named_by_meta if is_live_agent(fork_transcript, agent_id)}
    return sorted(live_launched | live_named), unresolved


def loop_report(pid, stopped, reason):
    return {"pid": pid, "stopped": stopped, "reason": reason}


class ForkCommands(NamedTuple):
    """What one pass over the code-fork's Bash commands found."""
    ran_review_start: bool
    first_start_timestamp: object  # the `timestamp` of the record of the first review start; None when it has none
    ran_review_fix: bool
    ends_on_review_start: bool  # the last record is a Bash call that runs the review start script


def scan_fork_commands(fork_transcript):
    """The ForkCommands of the code-fork's transcript, read once; None when the transcript cannot be read (named on
    stderr)."""
    ran_review_start = False
    first_start_timestamp = None
    ran_review_fix = False
    ends_on_review_start = False
    try:
        with open(fork_transcript, encoding="utf-8", errors="replace") as transcript:
            for line in transcript:
                if not line.strip():
                    continue
                calls = script_utils.tool_use_calls(line)
                commands = [tool_input.get("command") for name, tool_input in calls if name == "Bash"]
                commands = [command for command in commands if isinstance(command, str)]
                starts_review = any(REVIEW_START_SCRIPT in command for command in commands)
                ran_review_fix = ran_review_fix or any(REVIEW_FIX_LAUNCH in command for command in commands)
                ends_on_review_start = starts_review
                if starts_review and not ran_review_start:
                    ran_review_start = True
                    first_start_timestamp = json.loads(line).get("timestamp")
    except OSError as error:
        print(f"fork_children: could not read {fork_transcript}: {type(error).__name__}: {error}", file=sys.stderr)
        return None
    return ForkCommands(ran_review_start, first_start_timestamp, ran_review_fix, ends_on_review_start)


def fork_run_window(fork_transcript, commands):
    """(epoch of the code-fork's first review start, epoch of its last record) from its ForkCommands, or None when a
    time is missing or unreadable (named on stderr). The end is None, an open window, when the last record is the Bash
    call that runs the review start script: the loop's pid file is written after that record, and the code-fork's next
    record is not written yet."""
    try:
        first_start = human_turn_lookup.epoch_of_timestamp(commands.first_start_timestamp)
        if commands.ends_on_review_start:
            return first_start, None
        last_record = script_utils.last_transcript_record(fork_transcript) or {}
        return first_start, human_turn_lookup.epoch_of_timestamp(last_record.get("timestamp"))
    except (AttributeError, ValueError) as error:
        print(f"fork_children: {fork_transcript} has no readable record time for the review start: {error}",
              file=sys.stderr)
        return None


def started_inside_fork_run(repo, fork_transcript, commands):
    """Whether the loop's pid file was written between the code-fork's first review start and its last record."""
    window = fork_run_window(fork_transcript, commands)
    if window is None:
        return False
    pid_file = code_wait.phase_dir(repo) / code_wait.PID_FILE
    try:
        written = pid_file.stat().st_mtime
    except OSError as error:
        print(f"fork_children: could not stat {pid_file}: {error}", file=sys.stderr)
        return False
    first_start, last_record = window
    if last_record is None:
        return first_start <= written
    return first_start <= written <= last_record


def loop_not_linked_reason(pid, repo, fork_transcript):
    """Why the loop with this pid is not this code-fork's /code review loop, or None when it is."""
    commands = scan_fork_commands(fork_transcript)
    if commands is None:
        return LOOP_NOT_THIS_RUN
    if not commands.ran_review_start and commands.ran_review_fix:
        return LOOP_NOT_CODE_PHASE

    try:
        command = process_group.command_line(pid)
    except process_group.ProcessQueryError as error:
        print(f"fork_children: {error}", file=sys.stderr)
        return LOOP_UNKNOWN
    if not command:  # the process died after running_review_pid saw it alive
        return LOOP_GONE
    if REVIEW_START_SCRIPT not in command:
        return LOOP_NOT_REVIEW_LOOP
    if not commands.ran_review_start:
        return LOOP_NOT_THIS_RUN
    if not started_inside_fork_run(repo, fork_transcript, commands):
        return LOOP_NOT_THIS_RUN
    return None


def stop_fork_loop(repo, fork_transcript):
    """Stop the repo's detached /code review loop when it is this code-fork's: its pid is alive, its command line holds
    the review start script, the code-fork's own Bash commands ran that script, and the loop started inside the
    code-fork's lifetime. Reports `stopped` once every process of the loop's group exited, `signalled` when one is
    still alive after STOP_WAIT_SECONDS. The review-fix loop of a /review or /fix fork is not stopped. Exits with a
    named error line when the signal raises OSError."""
    pid = code_wait.running_review_pid(repo)
    if pid is None:
        return loop_report(None, False, LOOP_NONE)

    not_linked = loop_not_linked_reason(pid, repo, fork_transcript)
    if not_linked:
        return loop_report(pid, False, not_linked)
    # The leader's group id is read before the signal: a leader that exits no longer names its group.
    group = process_group.group_id(pid)
    try:
        signalled = process_group.terminate_group(pid)
    except OSError as error:
        sys.exit(f"fork_children: could not signal the review loop of {repo}: {type(error).__name__}: {error}")
    if group is None or not signalled:
        return loop_report(pid, False, LOOP_GONE)
    if not process_group.wait_until_group_gone(group, STOP_WAIT_SECONDS):
        return loop_report(pid, False, LOOP_SIGNALLED)
    return loop_report(pid, True, LOOP_STOPPED)


def hook_agent_transcript(hook, agent_id):
    """The transcript of agent `agent_id`: the one beside the hook event's session transcript when it exists, else the
    newest one under any session of the projects folder (None when there is none)."""
    session_transcript = hook.get("transcript_path")
    if isinstance(session_transcript, str) and session_transcript:
        sibling = pathlib.Path(script_utils.subagent_transcript_path(session_transcript, agent_id))
        if sibling.is_file():
            return sibling
    return code_wait.agent_transcript(agent_id)


def taskstop_deny_reason(hook):
    """The deny text when the hook is a TaskStop of a code-fork with a live child, not denied before, else None."""
    if hook.get("tool_name") != "TaskStop":
        return None
    task_id = (hook.get("tool_input") or {}).get("task_id")
    if not isinstance(task_id, str) or not code_wait.AGENT_ID.fullmatch(task_id):
        return None

    transcript = hook_agent_transcript(hook, task_id)
    if transcript is None or not is_code_fork(transcript):
        return None
    children, unresolved = child_ids(transcript, task_id)
    if not (children or unresolved):
        return None

    session_id = hook.get("session_id")
    if not session_id or handback_store.was_recorded(session_id, task_id, KIND_TASKSTOP_DENIED):
        return None
    handback_store.record(session_id, KIND_TASKSTOP_DENIED, agent_id=task_id, children=children,
                          unresolved_launches=unresolved)
    names = [*children, *(UNRESOLVED_LAUNCH.format(launch=launch) for launch in unresolved)]
    return DENY_REASON.format(fork=task_id, ids=", ".join(names), script=pathlib.Path(__file__).resolve())


def run_hook_verb():
    if os.environ.get("CLAUDE_SKIP_HOOKS"):
        return
    try:
        hook = json.load(sys.stdin)
        reason = taskstop_deny_reason(hook)
    except Exception as error:  # fail open, visibly: a broken gate must not block the cancel
        print(f"fork-children-hook: skipped, {type(error).__name__}: {error}", file=sys.stderr)
        return
    if reason:
        script_utils.pre_tool_use_deny(reason)


def fork_repo(fork_transcript):
    """The git top level of the cwd the code-fork's transcript last recorded; the current folder's when the transcript
    records none. None outside a git checkout."""
    last_record = script_utils.last_transcript_record(fork_transcript) or {}
    cwd = last_record.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        cwd = os.getcwd()
    return script_utils.work_tree_top(cwd)


def run_report(parser, fork_id, repo):
    if not code_wait.AGENT_ID.fullmatch(fork_id):
        parser.error(f"{fork_id!r} is not an agent id: {code_wait.AGENT_ID_FORM}")
    transcript = code_wait.agent_transcript(fork_id)
    if transcript is None:
        parser.error(f"no transcript found for agent {fork_id}")
    if not is_code_fork(transcript):
        parser.error(f"agent {fork_id} is not a {open_child_gate.CODE_FORK}")

    children, unresolved = child_ids(transcript, fork_id)
    repo = repo or fork_repo(transcript)
    if repo is None or code_wait.phase_dir_or_none(repo) is None:
        loop = loop_report(None, False, LOOP_NO_REPO)
    else:
        loop = stop_fork_loop(repo, transcript)
    print(json.dumps({"fork": fork_id, "children": children, "unresolved_launches": unresolved, "loop": loop}))


def main():
    parser = argparse.ArgumentParser(description="Name a code-fork's live children and stop its review loop.")
    parser.add_argument("target", help=f"`{HOOK_VERB}` (PreToolUse hook, event on stdin) or a code-fork's agent id")
    parser.add_argument("--repo", help="the repo whose review loop to stop (default: the code-fork's last cwd)")
    args = parser.parse_args()
    if args.target == HOOK_VERB:
        run_hook_verb()
        return
    run_report(parser, args.target, args.repo)


if __name__ == "__main__":
    main()
