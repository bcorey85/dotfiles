#!/usr/bin/env python3
"""Run the live review loop script for /code.

    python3 ~/.claude/scripts/code/code_review_start.py <lane> <plan> <phase> <handoff file>
        --base <phase start sha> [--coder-model <model>] [--ci-gate <CI run>] [--dry-run | --detach]

`--coder-model` runs the loop's fix coder on that model: the prompt gets a `coder-model:` line, and a detached run
keeps the option for its child. `--ci-gate` names the CI run the caller ruled to be the test gate: the prompt gets a
`ci-gate:` line, the loop runs no local full check, and a detached run keeps the option for its child.

The base may be the start record's head (the base `phase_start.py --resume` prints), an ancestor of it (a
merge-base), or the current HEAD when the record's head is an ancestor of it. A --base that is no ancestor of HEAD is
replaced by `git merge-base HEAD <base>` before the merge fold, and a base with no shared history stops the run.
When base..HEAD holds a merge commit,
the loop's base is a synthetic commit (no ref) with each merged-in parent folded in, so the review diff leaves out
what the merge brought; a merge that conflicts
stops the run, naming it. The loop's base goes in the prompt's `base:` line. The loop folder is recorded
in <git dir>/code-phase/run.json, where `code_wait.py review` checks it.

The prompt header is: lane, repo, plan, phase, later-phase files and held files (with a holder recorded in
phase_start.py's record, every file dirty at the run start, whatever its bytes now; with no holder recorded, a
same-bytes file while a live session other than this run's works in the repo; and, with a recorded holder or while
such a session is live, every untracked file no recorded coder of the run wrote and no earlier or current phase
section names, outside the plan folder and the start record's dirty map; the held-by line names each holder), a
`tool fault:` line when a held file changed since the run start, a `held files this phase names:` line for held files
the phase's plan section names, a `given-base:` line when the base line is not the commit --base names, then the
handoff block and the repo's gate env.
A <plan> of `-` means the run has no plan file: the header leaves out the plan, phase and later-phase lines, and the
gate commands come from the handoff block's files.
The loop's state folder is <git dir>/code-step. The pid goes in <git dir>/code-phase/pid, where `code_wait.py review`
looks, so the session can end its turn while the loop runs. The loop runs with `--reviewers main`: the fork dispatches
each round's reviewers as its own subagents, and <git dir>/code-phase/loop-dir names the folder that holds the
requests. Prints the hand-back packet when the loop ends.
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
import fix_coder_written
import gate_commands
import gate_env
import handback_hook
import handoff_files
import loop_transcript
import merge_free_base
import phase_start
import plan_format
import reviewer_dispatch
import script_utils
import session_registry
import stop_file_names
from code_wait import (
    HANDOFF_FILE,
    PID_FILE,
    REVIEW_OUTPUT,
    SCOPE_FILE,
    loop_dir,
    phase_dir,
    running_review_pid,
)
from review_loop_prompt_file import (
    BASE_KEY,
    CI_GATE_KEY,
    CODER_MODEL_KEY,
    GIVEN_BASE_KEY,
    HELD_BY_KEY,
    HELD_FILES_KEY,
    LIST_SEPARATOR,
    PLAN_KEY,
    REPO_KEY,
    REVIEWERS_MAIN,
    holder_row,
    loop_script_command,
    write_script_prompt,
)

LOOP_SCRIPT = SCRIPTS_DIR / "review/review_loop_script.py"
WAIT_COMMAND = code_wait.REVIEW_COMMAND
AGENT_PREFIX = "loop-script-"
NO_PLAN = gate_commands.NO_PLAN
HANDOFF_PHASES_FILE = "handoff-phases.json"
# The origins a holder row's claim names, and the two prompt header lines the loop stores and ignores.
DIRTY_UNCHANGED = "dirty at the run start, unchanged now"
DIRTY_CHANGED = "dirty at the run start, changed since"
UNTRACKED_UNATTRIBUTED = "untracked, written by no recorded coder of this run"
TOOL_FAULT_KEY = "tool fault"
HELD_TARGETED_KEY = "held files this phase names"


def held_claim(origin, cwd):
    """The claim text of a holder row: why the file is held, and where the holder's session works."""
    return f"{origin}; session in {cwd}"


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


def handoff_with_git_files(repo, base_commit, handoff, held=(), plan=NO_PLAN):
    # The handoff's `files:` list is the files git shows changed since base (tracked changes plus untracked files),
    # less the held files and the files under the plan's folder, which are plan documents and not the change. The
    # coder's own list is dropped; only its `why:` lines are kept, under the matching path.
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
    not_held = script_utils.without_paths(coder_gate.changed_files(repo, base_commit), held)
    changed = plan_format.outside_plan_folder(not_held, plan)
    if not changed:
        return "\n".join([*lines[:start], f"{HANDOFF_FILES_LINE} []", *lines[end:]]) + "\n"

    files_lines = [HANDOFF_FILES_LINE, *handoff_files.file_entry_lines(changed, {}, "changed since the phase base",
                                                                        why_by_path)]
    return "\n".join([*lines[:start], *files_lines, *lines[end:]]) + "\n"


def phase_changed_files(repo, base_commit, held=()):
    """The files git shows changed since the phase base, less the held files."""
    return script_utils.without_paths(script_utils.changed_files(repo, base_commit), held)


class PlanFiles(NamedTuple):
    """The files the plan names: those of the phases before this one (the run's own, never held) and those of this
    phase's section."""
    earlier: list
    this: list


def plan_files(repo, plan, phase):
    """The PlanFiles of a phase; both lists are empty with no plan. The plan is read and parsed once."""
    if plan == NO_PLAN:
        return PlanFiles([], [])
    plan_lines = (repo / plan).read_text().splitlines()
    paths = expected_red.plan_phase_paths(plan_lines, phase)
    return PlanFiles(paths.earlier, paths.own)


def held_note(notes, message):
    """Prints `message` on stderr and adds it to `notes` (a list, or None), which a dry run prints on stdout."""
    print(message, file=sys.stderr)
    if notes is not None:
        notes.append(message)


def checked_start_record(repo, base_commit):
    """The start record of the run, None when phase_start.py wrote none. Stops on a record that does not parse or whose
    head does not relate to the base."""
    try:
        record = phase_start.read_start_record(repo)
        if record is not None:
            phase_start.check_record_base(repo, base_commit, record)
    except phase_start.StartRecordError as error:
        sys.exit(f"code_review_start: {error}")
    return record


def review_holder(repo, record, own_session_id):
    """The holder of the files this run leaves out: the recorded one, else the other session live in the repo now,
    else None. A holder is {"session", "cwd"}."""
    return record["holder"] or phase_start.current_holder(repo, own_session_id)


class HeldScope(NamedTuple):
    """The files a review leaves out. `dirty` and `untracked` are holder rows of the held dirty and untracked files,
    `changed` the held paths whose bytes changed since the run start, `released` the dirty paths whose change a coder
    of the run wrote, which review reads."""
    dirty: list
    changed: list
    untracked: list
    released: list


NO_HELD_FILES = HeldScope([], [], [], [])


def held_scope(repo, base_commit, plan=NO_PLAN, phase="", notes=None, named_files=None):
    """The HeldScope of a phase. A holder recorded at the phase start is honored whether or not this session's id is
    set. With no holder recorded, the live-holder fallback needs the id. No record, or no holder by either route,
    holds none (the no-holder route); the reason is noted on stderr and in `notes`. `named_files` is the phase's
    PlanFiles when the caller has them, else they are read from the plan here."""
    if named_files is None:
        named_files = plan_files(repo, plan, phase)
    record = checked_start_record(repo, base_commit)
    if record is None:
        held_note(notes, "code_review_start: no phase start record, so files another session left dirty are reviewed "
                         f"as this phase's own. Run `{phase_start.COMMAND}` before each phase's coder dispatch.")
        return NO_HELD_FILES

    own_session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    holder = review_holder(repo, record, own_session_id)
    if holder is None and not own_session_id:
        held_note(notes, "code_review_start: CLAUDE_CODE_SESSION_ID is not set and the start record names no holder, "
                         "so the run's own session cannot be told from a holder and no file is held; run it from the "
                         "session's Bash")
    if holder is None and own_session_id:
        held_note(notes, "code_review_start: the start record names no holder and no other session is live in the "
                         "repo, so no file is held.")
    if holder is None:
        return NO_HELD_FILES

    own_files = [*named_files.earlier, *fix_coder_written.recorded(repo)]
    dirty_rows, held_changed = phase_held_files(repo, record, holder, own_files)
    released = coder_rewritten(repo, record, held_changed, notes)
    if released:
        held_note(notes, "code_review_start: " + code_wait.held_released_text(released))
    dirty_rows = [row for row in dirty_rows if row["path"] not in released]
    held_changed = [path for path in held_changed if path not in released]
    if held_changed:
        held_note(notes, "Tool fault: " + code_wait.held_fault_text(held_changed))
    untracked_rows = foreign_untracked(repo, record, holder, named_files, plan, notes)
    return HeldScope(dirty_rows, held_changed, untracked_rows, released)


def coder_rewritten(repo, record, held_changed, notes):
    """The held changed paths a coder of the recorded sessions wrote during the run: the run's own change, so review
    reads them. A record with no session attributes none; foreign_untracked notes that once."""
    if not held_changed or not record["sessions"]:
        return []
    written = coder_written_paths(repo, record, notes)
    return [path for path in held_changed if path in written]


def phase_held_files(repo, record, holder, own_files=()):
    """(holder rows {"path", "session", "claim"} of the held dirty files, the held paths whose bytes changed since the
    run start). With a holder recorded at a phase start (phase_start.py's record), every file dirty then is held for
    the whole phase, less `own_files`, the files an earlier phase of the plan names and the files the review loop's
    fix coder wrote (fix_coder_written), which are the run's own. With no holder recorded, only a same-bytes file is
    held, for the live session `holder`."""
    candidates = script_utils.without_paths(sorted(record["dirty"]), own_files)
    if not candidates:
        return [], []
    if record["holder"] is not None:
        return recorded_holder_rows(repo, record, holder, candidates)
    return live_holder_rows(repo, record, holder, candidates)


def recorded_holder_rows(repo, record, recorded_holder, candidates):
    """(rows, changed paths) holding every candidate for the recorded holder, claimed changed or unchanged."""
    changed = set(phase_start.changed_dirty_files(repo, record))
    rows = []
    for path in candidates:
        origin = DIRTY_CHANGED if path in changed else DIRTY_UNCHANGED
        rows.append(holder_row(path, recorded_holder["session"], held_claim(origin, recorded_holder["cwd"])))
    return rows, [path for path in candidates if path in changed]


def live_holder_rows(repo, record, holder, candidates):
    """(rows, []) holding the candidates whose bytes are unchanged, for the session live in the repo now."""
    changed = set(phase_start.changed_dirty_files(repo, record))
    claim = held_claim(DIRTY_UNCHANGED, holder["cwd"])
    return [holder_row(path, holder["session"], claim) for path in candidates if path not in changed], []


def targeted_held_files(named_files, held_paths):
    """The held paths this phase's plan section names; [] with no plan."""
    own_paths = set(named_files.this)
    return [path for path in held_paths if path in own_paths]


def coder_written_paths(repo, record, notes):
    """The repo-relative paths the recorded sessions' coder subagents wrote during the run (transcripts at or after
    the record's started_at). A session with no subagents folder is named in `notes`, and so is a record with no
    session."""
    root = pathlib.Path(repo).resolve()
    if not record["sessions"]:
        held_note(notes, "code_review_start: start.json records no session (CLAUDE_CODE_SESSION_ID was unset at phase "
                         "start), so no coder write can be attributed and every untracked file is held; run "
                         "phase_start.py from the session's Bash")
    written = set()
    for session_id in record["sessions"]:
        folder = session_registry.session_subagents_dir(session_id)
        if folder is None:
            held_note(notes, f"code_review_start: no coder transcripts found for session {session_id}")
            continue
        written |= folder_written_paths(root, folder, record["started_at"])
    return written


def folder_written_paths(root, folder, started_at):
    """The repo-relative paths the coder transcripts of a subagents `folder` wrote; `root` is the resolved repo."""
    written = set()
    for _agent_id, transcript, _meta in loop_transcript.subagent_entries(folder):
        if not coder_transcript_in_run(transcript, started_at):
            continue
        written |= transcript_repo_paths(root, transcript)
    return written


def transcript_repo_paths(root, transcript):
    """The repo-relative paths one coder `transcript` wrote; `root` is the resolved repo."""
    written = set()
    for name in loop_transcript.written_paths(transcript):
        relative = script_utils.repo_relative(root, name)
        if relative is not None:
            written.add(relative)
    return written


def coder_transcript_in_run(transcript, started_at):
    """Whether `transcript` exists, was written at or after `started_at`, and its meta file names a coder agent."""
    agent_type = loop_transcript.agent_meta(transcript).get("agentType")
    if not isinstance(agent_type, str) or not script_utils.CODERS.match(agent_type):
        return False
    if not transcript.is_file():
        return False
    return started_at is None or transcript.stat().st_mtime >= started_at


def foreign_untracked(repo, record, holder, named_files, plan, notes):
    """The holder rows of the untracked files no recorded coder of the run wrote, held for `holder` ({"session",
    "cwd"}); each file on its own, never a folder. Files in the record's `dirty`, the files an earlier phase names, the
    files this phase's plan section names (the phase's own new files) and the files under the plan's folder are left
    out."""
    untracked = script_utils.untracked_paths(pathlib.Path(repo))
    if untracked is None:
        sys.exit(f"code_review_start: git could not list the untracked files of {repo}, so none can be held. Fix the "
                 "repo, then run this step again.")
    plan_named = [*named_files.earlier, *named_files.this]
    own_files = [*plan_named, *fix_coder_written.recorded(repo)]
    candidates = script_utils.without_paths(untracked, [*record["dirty"], *own_files])
    candidates = plan_format.outside_plan_folder(candidates, plan)
    if not candidates:
        return []

    own = coder_written_paths(repo, record, notes)
    foreign = sorted(script_utils.without_paths(candidates, own))
    if not foreign:
        return []

    held_note(notes, "code_review_start: held untracked files no recorded coder of this run wrote (a file an earlier "
                     "review round's fix coder made is among them until the loop records its writes): "
                     f"{', '.join(foreign)}")
    claim = held_claim(UNTRACKED_UNATTRIBUTED, holder["cwd"])
    return [holder_row(path, holder["session"], claim) for path in foreign]


class ReviewScope(NamedTuple):
    """What a review covers: the holder rows of the held files, the handoff with its files from git, the files
    changed since the phase base, and the commit the loop diffs against (None when --base is no commit). `notes` are
    the lines a dry run prints on stdout about what the scope left out. `held_changed` are the held files whose bytes
    changed since the run start, `held_targeted` the held files this phase's section names, `held_released` the
    files dirty at the run start whose change a coder of the run wrote, which review reads. `given_base` is the
    --base as given, set only when the review base is not the commit --base names: its merge base with HEAD, or a
    commit with merged-in changes folded in."""
    holders: list
    handoff: str
    phase_changed: list
    review_base: str | None
    notes: tuple = ()
    held_changed: tuple = ()
    held_targeted: tuple = ()
    held_released: tuple = ()
    given_base: str | None = None


SCOPE_FILE_FLAG = "--scope-file"
# Each flag below, when absent, reads as "": the coder runs on its agent's own model (--coder-model),
# and the loop runs the local full check (--ci-gate).
CODER_MODEL_FLAG = "--coder-model"
CI_GATE_FLAG = "--ci-gate"


def read_scope(scope_file):
    """The ReviewScope a detached run's parent wrote to `scope_file`. Stops on a file that is not one."""
    try:
        return ReviewScope(**json.loads(pathlib.Path(scope_file).read_text()))
    except (OSError, ValueError, TypeError) as error:
        sys.exit(f"code_review_start: {SCOPE_FILE_FLAG} {scope_file} is not a review scope file ({error}). Expected "
                 f"the JSON object of {', '.join(ReviewScope._fields)}. Run this step again without {SCOPE_FILE_FLAG}.")


def diff_base(repo, base_commit, base):
    """The commit the review diffs against: `base_commit`, or its merge base with HEAD when it is no ancestor of HEAD,
    then a synthetic base that leaves out what merge commits of base..HEAD brought in. A base with no merge base, or a
    merge that does not merge cleanly, stops the run."""
    try:
        resolved = merge_free_base.resolve_base(repo, base_commit, base)
        return merge_free_base.merge_free_base(repo, resolved.used)
    except merge_free_base.NoMergeBaseError as error:
        sys.exit(f"code_review_start: {error}")
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
    named_files = plan_files(repo, plan, phase)
    held = held_scope(repo, base_commit, plan, phase, notes, named_files)
    holders = [*held.dirty, *held.untracked]
    held_paths = [holder["path"] for holder in holders]
    held_targeted = targeted_held_files(named_files, held_paths)
    if held_targeted:
        held_note(notes, "code_review_start: this phase's plan names held files, which stay held, so the phase's "
                         f"change to them is not reviewed: {', '.join(held_targeted)}")
    review_base = diff_base(repo, base_commit, base)
    handoff = handoff_with_git_files(repo, review_base, coder_handoff, held_paths, plan)
    phase_changed = phase_changed_files(repo, review_base, held_paths)
    return ReviewScope(holders, handoff, phase_changed, review_base, notes, held.changed, held_targeted,
                       held.released, base if review_base != base_commit else None)


def review_prompt(repo, lane, plan, phase, handoff, phase_changed=(), holders=(), review_base=None, coder_model="",
                  held_changed=(), held_targeted=(), given_base=None, ci_run=""):
    """A later phase's file that this phase's diff already changed stays the phase's own, so a fix pass may edit the
    lines the phase wrote there. A held file is another session's, so the loop neither reviews nor edits it; the
    held-by line carries the holder rows that prove it. The base line makes the loop review the commits since the
    base too, so a phase the user committed before a resume is still reviewed. A `coder_model` adds the line that
    runs the fix coder on it. A `ci_run` adds the line that makes the loop run no local full check."""
    header = ["mode: review-first", "caller: code", f"lane: {lane}", f"{REPO_KEY}: {repo}"]
    if review_base is not None:
        header.append(f"{BASE_KEY}: {review_base}")
    if given_base:
        header.append(f"{GIVEN_BASE_KEY}: {given_base}")

    if plan != NO_PLAN:
        header += [f"{PLAN_KEY}: {plan}", f"phase: {phase}"]
        plan_lines = (repo / plan).read_text().splitlines()
        later_paths = expected_red.later_phase_paths(plan_lines, phase)
        later_files = script_utils.without_paths(later_paths, phase_changed)
        if later_files:
            header.append(f"later-phase files: {', '.join(later_files)}")
    if holders:
        header.append(f"{HELD_FILES_KEY}: {LIST_SEPARATOR.join(holder['path'] for holder in holders)}")
        header.append(f"{HELD_BY_KEY}: {json.dumps(list(holders))}")
    if held_changed:
        header.append(f"{TOOL_FAULT_KEY}: {code_wait.held_fault_text(held_changed)}")
    if held_targeted:
        header.append(f"{HELD_TARGETED_KEY}: {LIST_SEPARATOR.join(held_targeted)}")
    if coder_model:
        header.append(f"{CODER_MODEL_KEY}: {coder_model}")
    if ci_run:
        header.append(f"{CI_GATE_KEY}: {ci_run}")

    prompt = "\n".join(header) + "\n\n" + handoff.strip()
    assignments = gate_env.repo_gate_env(repo, plan_or_none(plan))
    gate_env_text = plan_format.gate_env_text(assignments)
    return f"{prompt}\n\n{gate_env_text}\n" if gate_env_text else prompt + "\n"


def plan_or_none(plan):
    """The plan path, or None for the no-plan word."""
    if plan == NO_PLAN:
        return None
    return plan


def recorded_plan_path(repo, plan):
    """The plan path to record in the run record, or None for the no-plan word."""
    plan = plan_or_none(plan)
    if plan is None:
        return None
    return str((pathlib.Path(repo) / plan).resolve())


def phase_gate_commands(repo, plan, phase, base, handoff=""):
    # The plan phase names the files and Automated Verification commands; a plan with no entry for the phase gives
    # the whole plan. The stale-prose pass runs only for a phase the plan has an entry for.
    # With no plan, the files come from the handoff block.
    # The checks run with the gate assignments, so the runner is picked from that same environment.
    assignments = gate_env.repo_gate_env(repo, plan_or_none(plan))
    check_environment = {**os.environ, **script_utils.environment_from_assignments(assignments)}
    if plan == NO_PLAN:
        handoff_files = HANDOFF_FILE_PATH.findall(handoff)
        handoff_text = "\n".join(f"`{path}`" for path in handoff_files)
        return gate_commands.derive_gate_commands(repo, handoff_text, check_environment)

    commands, has_section = gate_commands.plan_gate_commands(repo, plan, phase, check_environment)
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
    (folder / stop_file_names.LOOP_DIR_FILE).unlink(missing_ok=True)
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


def option_value(argv, flag):
    """The value `flag` names, or "" when the flag is absent. A flag with no value, or one that starts with `-`,
    exits with the usage."""
    _rest, value = script_utils.pop_option(argv, flag)
    if value is None:
        return ""
    if not value or value.startswith("-"):
        sys.exit(__doc__)
    return value


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
    coder_model = option_value(argv, CODER_MODEL_FLAG)
    ci_run = option_value(argv, CI_GATE_FLAG)
    prompt = review_prompt(repo, lane, plan, phase, handoff, scope.phase_changed, scope.holders, scope.review_base,
                           coder_model, scope.held_changed, scope.held_targeted, scope.given_base, ci_run)
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
    # Absolute, because the wait that reads it runs from the repo top, not from the folder this start ran in.
    code_wait.write_phase_run(repo, lane, phase, prompt_file.parent, plan=recorded_plan_path(repo, plan))
    script_utils.write_text_atomically(folder / stop_file_names.LOOP_DIR_FILE, f"{prompt_file.parent}\n")
    with log_path.open("w") as log:
        finished = subprocess.run(command, cwd=repo, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)

    print(f"The review loop script exited {finished.returncode}.")
    packet_file = prompt_file.parent / reviewer_dispatch.PACKET_FILE
    if not packet_file.exists():
        print(f"No packet. Log: {log_path}")
        return 0

    packet_text = packet_file.read_text()
    print(packet_text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
