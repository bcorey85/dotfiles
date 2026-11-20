#!/usr/bin/env python3
"""Run the live review loop script for /code.

    python3 ~/.claude/scripts/code/code_review_start.py <lane> <plan> <phase> <handoff file>
        --base <phase start sha> [--dry-run | --detach]

The base may be the start record's head (the base `phase_start.py --resume` prints), an ancestor of it (a
merge-base), or the current HEAD when the record's head is an ancestor of it. When base..HEAD holds a merge commit,
the loop's base is a synthetic commit (no ref) with each merged-in parent folded in, so the review diff leaves out
what the merge brought; a merge that conflicts
stops the run, naming it. The loop's base goes in the prompt's `base:` line. The loop folder is recorded
in <git dir>/code-phase/run.json, where `code_wait.py review` checks it.

The prompt header is: lane, repo, plan, phase, later-phase files and held files (dirty at the run start per
phase_start.py's record, same bytes now, while a live session other than this run's works in the repo; the held-by
line names each holder), then the handoff block and the repo's gate env.
A <plan> of `-` means the run has no plan file: the header leaves out the plan, phase and later-phase lines, and the
gate commands come from the handoff block's files.
The loop's state folder is <git dir>/code-step. The pid goes in <git dir>/code-phase/pid, where `code_wait.py review`
looks, so the session can end its turn while the loop runs. The loop runs with `--reviewers main`: the fork dispatches
each round's reviewers as its own subagents, and <git dir>/code-phase/loop-dir names the folder that holds the
requests. Prints the hand-back packet when the loop ends, then the defer ACTION when the packet holds a plan impact
that waits for a ruling.
A live run stops when the handoff file holds the same text an earlier phase's review read: the fork wrote this phase's
handoff somewhere else. A missing handoff file stops the run with its path: phase_start.py moved the last phase's
handoff aside, so write this phase's there first.
"""

import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
from typing import NamedTuple

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path[:0] = [str(SCRIPTS_DIR / folder) for folder in ("lib", "review", "code")]

import code_wait
import coder_gate
import expected_red
import gate_commands
import gate_env
import handback
import handback_hook
import handoff_files
import merge_free_base
import phase_start
import plan_format
import review_fix
import reviewer_dispatch
import script_utils
import session_registry
from code_wait import HANDOFF_FILE, LOOP_DIR_FILE, PID_FILE, REVIEW_OUTPUT, loop_dir, phase_dir, running_review_pid
from review_fix_state import REVIEW_FIX_COMMAND
from review_loop_prompt_file import (
    BASE_KEY,
    HELD_BY_KEY,
    HELD_FILES_KEY,
    LIST_SEPARATOR,
    REVIEWERS_MAIN,
    holder_row,
    loop_script_command,
    write_script_prompt,
)

LOOP_SCRIPT = SCRIPTS_DIR / "review/review_loop_script.py"
WAIT_COMMAND = "python3 ~/.claude/scripts/code/code_wait.py review"
DEFER_COMMAND = f"{REVIEW_FIX_COMMAND} defer"
AGENT_PREFIX = "loop-script-"
NO_PLAN = gate_commands.NO_PLAN
HANDOFF_PHASES_FILE = "handoff-phases.json"


HANDOFF_FILE_PATH = re.compile(r"^\s*-\s*path:\s*(\S+)", re.M)


HANDOFF_FILES_LINE = "  files:"
HANDOFF_WHY_LINE = re.compile(r"^\s{6}why:")


def coder_why_blocks(entry_lines):
    # {path: the entry's `why:` lines} of the coder's files entries. Only the why lines are kept.
    why_by_path = {}
    path = None
    in_why = False
    for line in entry_lines:
        entry = HANDOFF_FILE_PATH.match(line)
        if entry:
            path = entry.group(1)
            in_why = False
            continue
        if path and HANDOFF_WHY_LINE.match(line):
            in_why = True
        if path and in_why:
            why_by_path.setdefault(path, []).append(line)
    return why_by_path


def handoff_with_git_files(repo, base_commit, handoff, held=()):
    # The handoff's `files:` list is the files git shows changed since base (tracked changes plus untracked files),
    # less the held files. The coder's own list is dropped; only its `why:` lines are kept, under the matching path.
    lines = handoff.splitlines()
    starts = [at for at, line in enumerate(lines) if line.rstrip() == HANDOFF_FILES_LINE]
    if not starts:
        return handoff

    start = starts[0]
    end = len(lines)
    for at in range(start + 1, len(lines)):
        if lines[at].strip() and not lines[at].startswith("    "):
            end = at
            break

    why_by_path = coder_why_blocks(lines[start + 1:end])
    changed = script_utils.without_paths(coder_gate.changed_files(repo, base_commit), held)
    if not changed:
        return "\n".join([*lines[:start], f"{HANDOFF_FILES_LINE} []", *lines[end:]]) + "\n"

    files_lines = [HANDOFF_FILES_LINE, *handoff_files.file_entry_lines(changed, {}, "changed since the phase base",
                                                                        why_by_path)]
    return "\n".join([*lines[:start], *files_lines, *lines[end:]]) + "\n"


def phase_changed_files(repo, base_commit, held=()):
    """The files git shows changed since the phase base, less the held files."""
    return script_utils.without_paths(script_utils.changed_files(repo, base_commit), held)


def earlier_phase_files(repo, plan, phase):
    """The files the plan gives to the phases before this one: the run's own, never held. [] with no plan."""
    if plan == NO_PLAN:
        return []
    plan_lines = (repo / plan).read_text().splitlines()
    return expected_red.earlier_phase_paths(plan_lines, phase)


def held_note(notes, message):
    """Prints `message` on stderr and adds it to `notes` (a list, or None), which a dry run prints on stdout."""
    print(message, file=sys.stderr)
    if notes is not None:
        notes.append(message)


def phase_held_files(repo, base_commit, plan=NO_PLAN, phase="", notes=None):
    """The holder rows {"path", "session", "claim"} of the files another session holds: dirty at the run start
    (phase_start.py's record) with the same bytes now, while a live session other than this run's works inside the
    repo. With no such session the files are the run's own. A file an earlier phase of the plan names is the run's
    own too. No record holds none; the missing record is noted on stderr and in `notes`."""
    try:
        unchanged = phase_start.unchanged_dirty_files(repo, base_commit)
    except phase_start.StartRecordError as error:
        sys.exit(f"code_review_start: {error}")
    if unchanged is None:
        held_note(notes, "code_review_start: no phase start record, so files another session left dirty are reviewed "
                         f"as this phase's own. Run `{phase_start.COMMAND}` before each phase's coder dispatch.")
        return []

    candidates = script_utils.without_paths(unchanged, earlier_phase_files(repo, plan, phase))
    if not candidates:
        return []

    own_session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    if not own_session_id:
        held_note(notes, "code_review_start: CLAUDE_CODE_SESSION_ID is not set, so the run's own session cannot be "
                         "told from a holder and no file is held; run it from the session's Bash")
        return []
    holder = session_registry.other_live_session_in(repo, own_session_id)
    if holder is None:
        return []

    session = session_registry.holder_label(holder)
    claim = f"dirty at the run start, unchanged now; live session in {holder['cwd']}"
    return [holder_row(path, session, claim) for path in candidates]


class ReviewScope(NamedTuple):
    """What a review covers: the holder rows of the held files, the handoff with its files from git, the files
    changed since the phase base, and the commit the loop diffs against (None when --base is no commit). `notes` are
    the lines a dry run prints on stdout about what the scope left out."""
    holders: list
    handoff: str
    phase_changed: list
    review_base: str | None
    notes: tuple = ()


SCOPE_FILE_FLAG = "--scope-file"
SCOPE_FILE = "review-scope.json"


def read_scope(scope_file):
    """The ReviewScope a detached run's parent wrote to `scope_file`. Stops on a file that is not one."""
    try:
        return ReviewScope(**json.loads(pathlib.Path(scope_file).read_text()))
    except (OSError, ValueError, TypeError) as error:
        sys.exit(f"code_review_start: {SCOPE_FILE_FLAG} {scope_file} is not a review scope file ({error}). Expected "
                 f"the JSON object of {', '.join(ReviewScope._fields)}. Run this step again without {SCOPE_FILE_FLAG}.")


def diff_base(repo, base_commit):
    """The commit the review diffs against: `base_commit`, or a synthetic base that leaves out what merge commits of
    base..HEAD brought in. A merge that does not merge cleanly stops the run, naming the merge."""
    try:
        return merge_free_base.merge_free_base(repo, base_commit)
    except merge_free_base.MergeConflictError as error:
        sys.exit(f"code_review_start: {error}. Resolve or revert merge {error.merge}, or pass a --base after it, "
                 "then run this step again.")
    except merge_free_base.MergeBaseGitError as error:
        sys.exit(f"code_review_start: the review base could not be built: {error}")


def review_scope(repo, base, coder_handoff, plan=NO_PLAN, phase=""):
    """The ReviewScope of a phase. A base that is no commit holds nothing and keeps the coder's handoff, unless the
    handoff has a files list, which only git fills. The held files come from the start record against the base as
    given; the changed files and the loop's base come from the base with merge commits left out."""
    base_commit = script_utils.git_output(repo, "rev-parse", "--verify", f"{base}^{{commit}}")
    if base_commit is None:
        if any(line.rstrip() == HANDOFF_FILES_LINE for line in coder_handoff.splitlines()):
            sys.exit(f"code_review_start: --base {base} is not a commit in {repo}; the handoff's files come from git")
        return ReviewScope([], coder_handoff, [], None)

    notes = []
    holders = phase_held_files(repo, base_commit, plan, phase, notes)
    held_paths = [holder["path"] for holder in holders]
    review_base = diff_base(repo, base_commit)
    handoff = handoff_with_git_files(repo, review_base, coder_handoff, held_paths)
    phase_changed = phase_changed_files(repo, review_base, held_paths)
    return ReviewScope(holders, handoff, phase_changed, review_base, notes)


def review_prompt(repo, lane, plan, phase, handoff, phase_changed=(), holders=(), review_base=None):
    """A later phase's file that this phase's diff already changed stays the phase's own, so a fix pass may edit the
    lines the phase wrote there. A held file is another session's, so the loop neither reviews nor edits it; the
    held-by line carries the holder rows that prove it. The base line makes the loop review the commits since the
    base too, so a phase the user committed before a resume is still reviewed."""
    header = ["mode: review-first", "caller: code", f"lane: {lane}", f"repo: {repo}"]
    if review_base is not None:
        header.append(f"{BASE_KEY}: {review_base}")

    if plan != NO_PLAN:
        header += [f"plan: {plan}", f"phase: {phase}"]
        plan_lines = (repo / plan).read_text().splitlines()
        later_paths = expected_red.later_phase_paths(plan_lines, phase)
        later_files = script_utils.without_paths(later_paths, phase_changed)
        if later_files:
            header.append(f"later-phase files: {', '.join(later_files)}")
    if holders:
        header.append(f"{HELD_FILES_KEY}: {LIST_SEPARATOR.join(holder['path'] for holder in holders)}")
        header.append(f"{HELD_BY_KEY}: {json.dumps(list(holders))}")

    prompt = "\n".join(header) + "\n\n" + handoff.strip()
    assignments = gate_env.repo_gate_env(repo, None if plan == NO_PLAN else plan)
    gate_env_text = plan_format.gate_env_text(assignments)
    return f"{prompt}\n\n{gate_env_text}\n" if gate_env_text else prompt + "\n"


def phase_gate_commands(repo, plan, phase, base, handoff=""):
    # The plan phase names the files and Automated Verification commands; a plan with no entry for the phase gives
    # the whole plan. The stale-prose pass runs only for a phase the plan has an entry for.
    # With no plan, the files come from the handoff block.
    if plan == NO_PLAN:
        handoff_files = HANDOFF_FILE_PATH.findall(handoff)
        handoff_text = "\n".join(f"`{path}`" for path in handoff_files)
        return gate_commands.derive_gate_commands(repo, handoff_text)

    commands, has_section = gate_commands.plan_gate_commands(repo, plan, phase)
    if not has_section:
        return commands

    stale_prose_script = pathlib.Path(__file__).resolve().parent / coder_gate.STALE_PROSE_SCRIPT
    return [*commands, f"python3 {stale_prose_script} --base {base}"]


def detach(repo, argv, scope):
    # The fork's Bash call times out at 600 s and a review can run longer, so the loop runs on in its own session and
    # `code_wait.py review` waits for it. The pid file is written here too, before the waiter can look. The child
    # reads the scope from a file, so the held files and the diff base are computed once.
    folder = phase_dir(repo)
    folder.mkdir(exist_ok=True)
    pid_file = folder / PID_FILE
    # Fail closed: a second loop would overwrite the running loop's pid and output, which both runs then misread.
    running_pid = running_review_pid(repo)
    if running_pid is not None:
        sys.exit(f"code_review_start: another review loop of this repo still runs (pid {running_pid}, loop folder "
                 f"{loop_dir(repo)}). Wait for it with `{WAIT_COMMAND}`, or run this phase in its own worktree.")
    review_output = folder / REVIEW_OUTPUT
    # A folder left by an earlier phase's loop would show its unanswered requests as this loop's.
    (folder / LOOP_DIR_FILE).unlink(missing_ok=True)
    scope_file = folder / SCOPE_FILE
    script_utils.write_text_atomically(scope_file, json.dumps(scope._asdict()) + "\n")
    child_args = [arg for arg in argv[1:] if arg != "--detach"]
    command = [sys.executable, __file__, *child_args, SCOPE_FILE_FLAG, str(scope_file)]
    with review_output.open("w") as output:
        loop = subprocess.Popen(command, cwd=repo, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
                                start_new_session=True)
    pid_file.write_text(str(loop.pid))
    print(f"The review loop is running. Run {WAIT_COMMAND} with the Bash timeout set to 600000.")
    return 0


def read_handoff_phases(phases_file):
    """The {digest: "<plan>#<phase>"} map in `phases_file`, {} when the file is absent. Stops on any other shape."""
    if not phases_file.exists():
        return {}
    problem = None
    try:
        phases = json.loads(phases_file.read_text())
    except ValueError as error:
        problem = str(error)
    else:
        is_text_map = isinstance(phases, dict) and all(
            isinstance(key, str) and isinstance(value, str) for key, value in phases.items())
        if not is_text_map:
            problem = "not an object of text keys and text values"
    if problem is not None:
        sys.exit(f"code_review_start: {phases_file} is unreadable: {problem}. Expected "
                 f'{{"<sha256>": "<plan>#<phase>"}}. Delete it and run this step again.')
    return phases


def record_handoff_phase(repo, plan, phase, handoff_text):
    """Record which plan and phase's review reads this handoff text, as "<plan>#<phase>" per text digest, in
    <git dir>/code-phase/HANDOFF_PHASES_FILE. Returns the earlier phase when the same text was already read for
    another phase of the same plan, else None. A rerun of one phase passes, and so does the same text under another
    plan."""
    folder = phase_dir(repo)
    folder.mkdir(exist_ok=True)
    phases_file = folder / HANDOFF_PHASES_FILE
    phases = read_handoff_phases(phases_file)
    digest = hashlib.sha256(handoff_text.encode()).hexdigest()
    earlier_plan, _separator, earlier_phase = phases.get(digest, "").rpartition("#")
    if earlier_plan == plan and earlier_phase != phase:
        return earlier_phase

    phases[digest] = f"{plan}#{phase}"
    script_utils.write_text_atomically(phases_file, json.dumps(phases, indent=1) + "\n")
    return None


def base_option(argv):
    # The phase start commit, which the stale-prose pass diffs against; the loop cannot find it from the repo alone.
    if "--base" not in argv or argv.index("--base") + 1 >= len(argv):
        sys.exit(__doc__)
    return argv[argv.index("--base") + 1]


def run_scope(argv, repo, base, coder_handoff, plan, phase):
    """The scope a detached parent saved (`--scope-file`), else the one this call computes."""
    if SCOPE_FILE_FLAG in argv and argv.index(SCOPE_FILE_FLAG) + 1 < len(argv):
        return read_scope(argv[argv.index(SCOPE_FILE_FLAG) + 1])
    return review_scope(repo, base, coder_handoff, plan, phase)


def main(argv):
    if len(argv) < 5:
        sys.exit(__doc__)
    lane, plan, phase, handoff_file = argv[1:5]
    base = base_option(argv)
    repo = pathlib.Path.cwd().resolve()
    handoff_path = pathlib.Path(handoff_file)
    if not handoff_path.is_file():
        sys.exit(f"code_review_start: no hand-off file at {handoff_path.resolve()}. Write this phase's hand-off block "
                 "there with Write, then run this step again.")
    coder_handoff = handoff_path.read_text()
    scope = run_scope(argv, repo, base, coder_handoff, plan, phase)
    handoff = scope.handoff
    prompt = review_prompt(repo, lane, plan, phase, handoff, scope.phase_changed, scope.holders, scope.review_base)
    if "--dry-run" in argv:
        print(prompt)
        for note in scope.notes:
            print(note)
        return 0

    stale_phase = record_handoff_phase(repo, plan, phase, coder_handoff)
    if stale_phase is not None:
        run_folder = phase_dir(repo)
        sys.exit(f"code_review_start: {handoff_file} holds the handoff Phase {stale_phase}'s review read, not one for "
                 f"Phase {phase}. Write this phase's handoff to {run_folder / HANDOFF_FILE} with Write, then run "
                 f"this step again with that path. When the text really is this phase's handoff, delete "
                 f"{run_folder / HANDOFF_PHASES_FILE} and run this step again.")

    if "--detach" in argv:
        return detach(repo, argv, scope)

    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    if not session_id:
        sys.exit("code_review_start: CLAUDE_CODE_SESSION_ID is not set; run it from the session's Bash")
    run_id = script_utils.sortable_unique_id()
    agent_id = f"{AGENT_PREFIX}{run_id}"
    state_dir = script_utils.git_path(repo, "code-step")
    if state_dir is None:
        sys.exit(f"code_review_start: {repo} is not inside a git checkout")
    folder = phase_dir(repo)
    folder.mkdir(exist_ok=True)
    (folder / PID_FILE).write_text(str(os.getpid()))

    handback_hook.record_script_dispatch(session_id, repo)
    prompt_file, log_path = write_script_prompt(state_dir, agent_id, prompt)
    commands = phase_gate_commands(repo, plan, phase, scope.review_base or base, handoff)
    # The fork runs the reviewers as its own subagents; `code_wait.py review` finds their requests in this folder.
    command = loop_script_command(LOOP_SCRIPT, repo, state_dir, session_id, agent_id, prompt_file, commands,
                                  reviewers=REVIEWERS_MAIN)
    # After detach's running-loop refusal, so a refused start leaves the running loop's record as it was. The run
    # record names the loop folder before loop-dir does, so a waiter never sees a folder the record lacks.
    code_wait.write_phase_run(repo, lane, phase, prompt_file.parent)
    script_utils.write_text_atomically(folder / LOOP_DIR_FILE, f"{prompt_file.parent}\n")
    with log_path.open("w") as log:
        finished = subprocess.run(command, cwd=repo, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)

    print(f"The review loop script exited {finished.returncode}.")
    packet_file = prompt_file.parent / reviewer_dispatch.PACKET_FILE
    if not packet_file.exists():
        print(f"No packet. Log: {log_path}")
        return 0

    packet_text = packet_file.read_text()
    print(packet_text)
    print("\n".join(held_impact_lines(packet_text, handoff_file)))
    return 0


def held_impact_lines(packet_text, handoff_file):
    """The ACTION lines for the packet's held plan impacts: the commit gate counts the review as dirty until the
    session defers them, whatever the packet's status says. [] when none is held."""
    try:
        packet = handback.load(packet_text)
    except handback.PacketError as error:
        return [f"code_review_start: the packet does not parse, so its held plan impacts are unknown: {error}"]

    held = handback.held_plan_impacts(packet)
    if not held:
        return []
    return [f"ACTION: defer-plan-impacts. {len(held)} plan impact(s) wait for a ruling, so the commit gate counts this "
            f"review as dirty. Before any commit, set `plan_impact` in {handoff_file} to the one line "
            f"`{review_fix.DEFER_LINE.removeprefix('plan_impact: ')}` and run "
            f"`{DEFER_COMMAND} {handoff_file}`."]


if __name__ == "__main__":
    sys.exit(main(sys.argv))
