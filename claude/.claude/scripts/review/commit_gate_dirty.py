"""commit_gate_dirty.py: when a session's work made a repo dirty, for the review commit gate. The state events the gate
keeps per session (a coder dispatch, a dirty mark), the repos a coder agent edited, read from its transcript, and the
latest time each repo was dirtied."""
import json
import os
import pathlib
import re
import time

import hook_input
import script_utils

AGENT_ID = re.compile(r"[A-Za-z0-9_-]+")
GIT_TIMEOUT_SECONDS = 3
# The input key that names the edited file, for each tool a coder edits with.
EDIT_TOOL_PATH_KEYS = {"Edit": "file_path", "MultiEdit": "file_path", "Write": "file_path",
                       "NotebookEdit": "notebook_path"}


def gate_events(state_file):
    """The state events, oldest first. A plain `dirty` line, and a line the gate cannot read, become a dirty event at
    the file's last change. A leftover plain `clean` line is no event."""
    try:
        with open(state_file, "rb") as handle:
            lines = handle.read().decode("utf-8", "replace").splitlines()
        changed_at = os.path.getmtime(state_file)
    except OSError:
        return []

    events = []
    for line in lines:
        if line.strip() == "clean":
            continue
        try:
            event = json.loads(line)
        except ValueError:
            event = None
        if not isinstance(event, dict) or not isinstance(event.get("ts"), (int, float)):
            event = {"kind": "dirty", "ts": changed_at}
        events.append(event)
    return events


def subagent_transcript(transcript_path, agent_id):
    """The transcript of the session's subagent agent_id: Claude Code keeps every subagent's, nested ones too, in
    `<session transcript without .jsonl>/subagents/agent-<id>.jsonl`. None without a transcript or an id."""
    if not transcript_path or not isinstance(agent_id, str) or not AGENT_ID.fullmatch(agent_id):
        return None
    return script_utils.subagent_transcript_path(transcript_path, agent_id)


def worked_until(transcript_path, agent_id):
    """The last change to a coder agent's transcript, or 0 when it has none."""
    agent_transcript = subagent_transcript(transcript_path, agent_id)
    try:
        return os.path.getmtime(agent_transcript) if agent_transcript else 0
    except OSError:
        return 0


def folder_repo_top(folder):
    """The top level of the work tree that holds folder (its nearest existing ancestor when it is gone), as a
    string; "" when it lies outside every work tree: in a git dir, or with no `.git` in it or above it; None when
    git cannot tell, so the caller fails closed."""
    existing = pathlib.Path(folder)
    while not existing.is_dir() and existing != existing.parent:
        existing = existing.parent
    top = script_utils.repo_root(str(existing), timeout=GIT_TIMEOUT_SECONDS)
    if top:
        return str(top)
    if ".git" in existing.parts:
        return ""
    has_git_above = any((ancestor / ".git").exists() for ancestor in (existing, *existing.parents))
    return None if has_git_above else ""


def edited_repos(transcript_path, agent_id, top_by_dir):
    """The top levels of the repos a coder agent edited through the EDIT_TOOL_PATH_KEYS tools, read from its
    transcript: an empty set when no edited file lies in a work tree, None when the transcript cannot be read or git
    cannot place an edited folder. top_by_dir caches each folder's repo top, shared across agents. Fail-open on a
    readable transcript with no work-tree edit: the shell-write-gate keeps coder shell writes out of tracked files,
    so the edit tools are the record of coder writes."""
    agent_transcript = subagent_transcript(transcript_path, agent_id)
    if agent_transcript is None:
        return None
    edited_dirs = set()
    try:
        with open(agent_transcript, encoding="utf-8", errors="replace") as handle:
            for line in handle:
                edited_dirs.update(edited_dirs_in(line))
    except OSError:
        return None

    for folder in edited_dirs:
        if folder not in top_by_dir:
            top_by_dir[folder] = folder_repo_top(folder)

    repo_tops = {top_by_dir[folder] for folder in edited_dirs}
    if None in repo_tops:
        return None
    repo_tops.discard("")
    return repo_tops


def edited_dirs_in(line):
    """The folders of the files one transcript line's calls to the EDIT_TOOL_PATH_KEYS tools name."""
    edited_dirs = set()
    for tool_name, tool_input in script_utils.tool_use_calls(line):
        path_key = EDIT_TOOL_PATH_KEYS.get(tool_name)
        edited = tool_input.get(path_key) if path_key else None
        if isinstance(edited, str) and os.path.isabs(edited):
            edited_dirs.add(os.path.dirname(edited))
    return edited_dirs


def dispatch_agent_id(event):
    """The agent id of a dispatch event when it is a non-empty string, else None."""
    if event.get("kind") != "dispatch":
        return None
    agent_id = event.get("agent")
    if isinstance(agent_id, str) and agent_id:
        return agent_id
    return None


def edited_repos_by_agent(events, transcript_path):
    """edited_repos for each coder agent id the dispatch events name, read once."""
    top_by_dir = {}
    agent_ids = [dispatch_agent_id(event) for event in events]
    return {agent_id: edited_repos(transcript_path, agent_id, top_by_dir) for agent_id in agent_ids
            if agent_id is not None}


def dirty_since(events, transcript_path, repo_top, edited_by_agent):
    """When the work in repo_top became dirty: the latest dirty event, or coder dispatch that edited repo_top, or None
    when none did. A dirty event stands for every repo. A coder counts for the repos its transcript shows it edited
    (none when it edited no work tree), and for every repo when edited_repos is None. It counts from its dispatch or
    its transcript's last change, whichever is later, since a background coder edits after its dispatch is recorded.
    A coder with no agent id on record counts as dirty now, in every repo, since its edits cannot be read."""
    dirty_times = []
    for event in events:
        if event.get("kind") != "dispatch":
            dirty_times.append(event["ts"])
            continue
        agent_id = dispatch_agent_id(event)
        if agent_id is None:
            dirty_times.append(time.time())
            continue
        edited = edited_by_agent[agent_id]
        if repo_top is not None and edited is not None and repo_top not in edited:
            continue
        dirty_times.append(max(event["ts"], worked_until(transcript_path, agent_id)))
    return max(dirty_times, default=None)


def is_session_scratch_repo(repo_top, session, edited_by_agent, events):
    """True when repo_top and its git common dir (where commits and refs go) both lie under
    `<root>/<project slug>/<session>/` for a session temp root (the session's own scratchpad: a throwaway repo it made
    for a test), and no coder dispatch's edited repos name it. A coder whose edited repos could not be read (None), or
    whose dispatch has no agent id, may have edited it, so the repo is no scratch repo then (fail closed).
    edited_by_agent is edited_repos_by_agent's map."""
    if repo_top is None:
        return False
    for event in events:
        if event.get("kind") == "dispatch" and dispatch_agent_id(event) is None:
            return False
    for edited in edited_by_agent.values():
        if edited is None or repo_top in edited:
            return False
    if not hook_input.is_in_session_scratchpad(repo_top, session):
        return False

    # A linked worktree of a real repo sits in the scratchpad, but its commits land in that repo.
    common_dir = script_utils.git_output(repo_top, "rev-parse", "--path-format=absolute", "--git-common-dir",
                                         timeout=GIT_TIMEOUT_SECONDS)
    if not common_dir:
        # Fail closed: with no common dir, the empty path would resolve to the hook's cwd.
        return False
    if not hook_input.is_in_session_scratchpad(common_dir, session):
        return False

    # A clone of a real repo keeps its origin and could push; a throwaway repo has no remote.
    # Fail closed: git failing (None) is not scratch.
    remotes = script_utils.git_output(repo_top, "remote", timeout=GIT_TIMEOUT_SECONDS)
    return remotes == ""
