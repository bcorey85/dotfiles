#!/usr/bin/env python3
"""fork_children.py — the live children of a /code code-fork, and the PreToolUse hook that refuses a TaskStop of a
code-fork that still has some.

`fork_children.py <fork id> [--repo PATH]` prints one JSON object: the code-fork's id, the agent ids of the coders and
reviewers it started that have not finished or been stopped, the launches whose result names no agent id yet, and
what became of the repo's detached review loop (stopped only when its process is this code-fork's own review start).
Exit 0 with the report; exit 2 for a usage error, a missing transcript, an id that is not a code-fork or a repo
outside a git checkout. A traceback exit follows when `process_group.terminate_group` raises OSError (for example, a
missing permission).

`fork_children.py hook` reads a PreToolUse event on stdin. It denies, once per code-fork and session, a TaskStop of a
code-fork that has a live child or an unresolved launch, and names them. Any other call passes. Any error passes and
says why on stderr (fail open): the cancel must never be blocked by a broken gate.
"""
import argparse
import json
import os
import pathlib
import sys

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path[:0] = [str(SCRIPTS_DIR / folder) for folder in ("lib", "review", "code")]

import code_wait
import handback_store
import loop_transcript
import open_child_gate
import process_group
import script_utils

KIND_TASKSTOP_DENIED = "taskstop_denied"
HOOK_VERB = "hook"
REVIEW_START_SCRIPT = "code_review_start.py"
LOOP_NONE = "none"
LOOP_STOPPED = "stopped"
LOOP_GONE = "gone"
LOOP_NOT_THIS_RUN = "not_this_run"
LOOP_NOT_REVIEW_LOOP = "not_review_loop"
DENY_REASON = ("code-fork {fork} has live children: {ids}. Run python3 {script} "
               "{fork}, TaskStop each id it names, then TaskStop the code-fork.")
UNRESOLVED_LAUNCH = "launch {launch} (no agent id yet)"


def children_named_by_meta(fork_transcript, fork_id):
    """The agent ids of the sibling transcripts whose meta names the code-fork as parent."""
    child_ids_found = []
    meta_pattern = script_utils.subagent_meta_name("*")
    for meta_path in sorted(pathlib.Path(fork_transcript).parent.glob(meta_pattern)):
        if script_utils.read_json_object(meta_path).get("parentAgentId") == fork_id:
            child_ids_found.append(script_utils.subagent_id_from_meta_name(meta_path.name))
    return child_ids_found


def is_live_agent(fork_transcript, agent_id):
    """False once the agent's meta file or transcript shows it finished, or its transcript shows it stopped."""
    transcript = script_utils.sibling_transcript_path(fork_transcript, agent_id)
    return not (loop_transcript.agent_finished(transcript) or loop_transcript.agent_interrupted(transcript))


def is_code_fork(transcript):
    """Whether the agent whose transcript this is was started as a code-fork."""
    return loop_transcript.agent_meta(transcript).get("agentType") == open_child_gate.CODE_FORK


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


def stop_loop(repo, fork_transcript):
    """Stop the repo's detached review loop when it is this code-fork's: its pid is alive, its command line holds the
    review start script, and the code-fork's own Bash commands ran that script."""
    pid = code_wait.running_review_pid(repo)
    if pid is None:
        return loop_report(None, False, LOOP_NONE)

    try:
        command = process_group.command_line(pid)
    except process_group.ProcessQueryError as error:
        print(f"fork_children: {error}", file=sys.stderr)
        return loop_report(pid, False, LOOP_NOT_REVIEW_LOOP)
    if not command:  # the process died after running_review_pid saw it alive
        return loop_report(pid, False, LOOP_GONE)
    if REVIEW_START_SCRIPT not in command:
        return loop_report(pid, False, LOOP_NOT_REVIEW_LOOP)

    fork_commands = script_utils.bash_commands(fork_transcript)
    if not any(REVIEW_START_SCRIPT in fork_command for fork_command in fork_commands):
        return loop_report(pid, False, LOOP_NOT_THIS_RUN)

    if not process_group.terminate_group(pid):
        return loop_report(pid, False, LOOP_GONE)
    return loop_report(pid, True, LOOP_STOPPED)


def taskstop_deny_reason(hook):
    """The deny text when the hook is a TaskStop of a code-fork with a live child, not denied before, else None."""
    if hook.get("tool_name") != "TaskStop":
        return None
    task_id = (hook.get("tool_input") or {}).get("task_id")
    if not isinstance(task_id, str) or not code_wait.AGENT_ID.fullmatch(task_id):
        return None

    transcript = code_wait.agent_transcript(task_id)
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


def run_report(parser, fork_id, repo):
    if not code_wait.AGENT_ID.fullmatch(fork_id):
        parser.error(f"{fork_id!r} is not an agent id: {code_wait.AGENT_ID_FORM}")
    transcript = code_wait.agent_transcript(fork_id)
    if transcript is None:
        parser.error(f"no transcript found for agent {fork_id}")
    if not is_code_fork(transcript):
        parser.error(f"agent {fork_id} is not a {open_child_gate.CODE_FORK}")
    if code_wait.phase_dir_or_none(repo) is None:
        parser.error(f"{repo} is not inside a git checkout")

    children, unresolved = child_ids(transcript, fork_id)
    report = {"fork": fork_id, "children": children, "unresolved_launches": unresolved,
              "loop": stop_loop(repo, transcript)}
    print(json.dumps(report))


def main():
    parser = argparse.ArgumentParser(description="Name a code-fork's live children and stop its review loop.")
    parser.add_argument("target", help=f"`{HOOK_VERB}` (PreToolUse hook, event on stdin) or a code-fork's agent id")
    parser.add_argument("--repo", default=os.getcwd(), help="the repo whose review loop to stop (default: cwd)")
    args = parser.parse_args()
    if args.target == HOOK_VERB:
        run_hook_verb()
        return
    run_report(parser, args.target, args.repo)


if __name__ == "__main__":
    main()
