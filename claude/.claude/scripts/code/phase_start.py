#!/usr/bin/env python3
"""Record the tree a /code run starts from (kept across the run's phases at one HEAD), and print the phase base (HEAD,
or the kept record's head under --resume).

    python3 ~/.claude/scripts/code/phase_start.py [--new-run | --resume]

Run from the repo root before the phase's coder dispatch. Writes <git dir>/code-phase/start.json, once per call:
{"head": <sha>, "dirty": {<path>: <sha-256 of its bytes, or null when gone>}, "holder": {"session", "cwd"} | null,
"sessions": [<session id>, ...], "started_at": <epoch seconds> | null, "own": [<path>]}. `dirty` lists every file
dirty or untracked now; `holder` is the live session other than the run's that works in the repo now; `sessions` are
the run's session ids (a kept record adds the current session id); `own` lists the files earlier phases of the run
named in their hand-offs. code_review_start.py reads it: with a holder recorded, every file dirty here is held for
the whole phase, and one whose bytes changed is named as a tool fault; with no holder, a file dirty here that holds
the same bytes at review time is held while another live session works in the repo.
The record is of the run's start, not of each phase: `--new-run` replaces it. Without the flag an existing record
whose head is the current HEAD is kept, so the files an earlier phase of the run left dirty stay the run's own; a file
dirty now that the record lacks, and that no earlier phase's hand-off names, is added to it (another session's edit
first seen at a later phase start). A missing record, or one for another HEAD, is replaced either way. Prints the
HEAD sha, except under --resume (below).
`--resume` is for a run that went on after a stop, where the user may have committed the phase since: when the
kept record's head is an ancestor of HEAD, the record is kept, with the same additions as a same-HEAD start (later
dirty files, handed-off files as own), and its head is printed as the phase base. When a commit since that head ticked
a phase in the `## Phase Status` of a `.md` file (done at HEAD, not done at the kept head), the phase was finished: a
stderr line names the file and the phase number, a new record is written at HEAD, and HEAD is printed. With no record,
or a head that is not an ancestor, it prints HEAD as without the flag and says so on stderr. `--resume` also writes
<run folder>/resume.json (resume_review_gate.record_resume), which the code-fork's stop.md Write reads; a start
without `--resume` removes it.
`--new-run` first checks the lane file of the worktree it runs in (lib/lane_entries.py): when the lane's `reports_to`
session is not a live registry name, it exits non-zero before writing anything and lists the live names. No lane
file, an empty `reports_to`, a name that fits a live auto-named session (`nameSource` derived, `<cwd folder>-<2 hex>`;
the registry stores another suffix than ListAgents shows) or an unreadable lane file passes (the last with a
stderr note).
Before anything is moved, `--resume` exits non-zero when this repo's run folder holds no stop.md and no stop.prev.md
newer than the session's last relayed stop (lib/code_stop_record.py), and that stop is in another run folder: it
names both and the stop's recorded `To go on:` line (`/code resume <repo top>` for a finished stop).
An existing <git dir>/code-phase/stop.md is renamed to stop.prev.md first (review-stop.md stays), and an existing
handoff.txt to handoff.prev.txt, so a review start never reads an earlier phase's hand-off as this phase's; loop-dir
goes to loop-dir.prev, so a wait never returns an earlier phase's packet before this phase's review starts.
"""
import json
import os
import pathlib
import re
import sys
import time

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path[:0] = [str(SCRIPTS_DIR / folder) for folder in ("lib", "code")]

import code_stop_record
import code_wait
import fix_coder_written
import handoff_files
import lane_entries
import plan_format
import resume_review_gate
import script_utils
import session_registry
import stop_file_names
import worktree_snapshot

START_FILE = "start.json"
COMMAND = "python3 ~/.claude/scripts/code/phase_start.py"


class StartRecordError(ValueError):
    """A start record that is missing a field or names another phase base."""


RECORD_SHAPE = ('{"head": <sha>, "dirty": {<path>: <hash>}, "holder": {"session": <text>, "cwd": <text>} | null, '
                '"sessions": [<session id>], "started_at": <epoch seconds> | null, "own": [<path>]}')


def current_holder(repo, own_session_id):
    """{"session", "cwd"} of the live session other than `own_session_id` that works in the repo now; None when there
    is none or the run's own session id is unknown."""
    if not own_session_id:
        return None
    row = session_registry.other_live_session_in(repo, own_session_id)
    if row is None:
        return None
    return {"session": session_registry.holder_label(row), "cwd": row["cwd"]}


def start_record(repo, own_session_id=""):
    """The start record of the repo now: head, dirty, holder, sessions and started_at."""
    head = script_utils.head_commit(repo)
    if head is None:
        raise StartRecordError(f"{repo} has no HEAD commit, so the phase has no base")

    root = pathlib.Path(repo)
    codes = worktree_snapshot.status_codes(root)
    dirty = {path: worktree_snapshot.file_hash(root, path) for path in sorted(codes)}
    return {"head": head, "dirty": dirty, "holder": current_holder(repo, own_session_id),
            "sessions": [own_session_id] if own_session_id else [], "started_at": time.time(), "own": []}


def checked_record(record):
    """The six keys of a parsed record, with the defaults of a record written before holder, sessions, started_at and
    own existed. A key of the wrong type raises TypeError."""
    holder = record.get("holder")
    sessions = record.get("sessions", [])
    started_at = record.get("started_at")
    own = record.get("own", [])
    holder_ok = holder is None or (isinstance(holder, dict) and isinstance(holder.get("session"), str)
                                   and isinstance(holder.get("cwd"), str))
    started_ok = started_at is None or (isinstance(started_at, (int, float)) and not isinstance(started_at, bool))
    if not isinstance(record["dirty"], dict):
        raise TypeError("dirty is not an object")
    if not holder_ok:
        raise TypeError("holder is neither null nor an object with text session and cwd")
    if not (isinstance(sessions, list) and all(isinstance(entry, str) for entry in sessions)):
        raise TypeError("sessions is not a list of session ids")
    if not started_ok:
        raise TypeError("started_at is neither null nor a number")
    if not (isinstance(own, list) and all(isinstance(entry, str) for entry in own)):
        raise TypeError("own is not a list of paths")
    return {"head": record["head"], "dirty": record["dirty"], "holder": holder, "sessions": sessions,
            "started_at": started_at, "own": own}


def read_start_record(repo):
    """The start record on disk with its six keys; None when there is no file. A record that does not parse, or holds
    a key of the wrong type, raises StartRecordError."""
    record_file = code_wait.phase_dir(repo) / START_FILE
    if not record_file.is_file():
        return None

    try:
        return checked_record(json.loads(record_file.read_text()))
    except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as error:
        raise StartRecordError(f"{record_file}: {error!r}; expected {RECORD_SHAPE}. "
                               "Re-run phase_start.py before the next coder dispatch.") from error


def base_relates_to_head(repo, base_commit, head):
    """Whether `base_commit` is the recorded head, an ancestor of it (a merge-base), or the current HEAD when the
    recorded head is an ancestor of it (a resume base)."""
    if script_utils.is_ancestor(repo, base_commit, head):
        return True
    if not script_utils.is_ancestor(repo, head, base_commit):
        return False
    return base_commit == script_utils.head_commit(repo)


def check_record_base(repo, base_commit, record):
    """Raises StartRecordError when the record's head is neither an ancestor nor a descendant of the base."""
    head = record["head"]
    record_file = code_wait.phase_dir(repo) / START_FILE
    if not base_relates_to_head(repo, base_commit, head):
        raise StartRecordError(f"{record_file} records phase base {head}, and {base_commit} is neither an ancestor of "
                               f"it nor the current HEAD it is an ancestor of. Pass --base {head} (a base may be an "
                               "ancestor of the recorded head, or HEAD when the recorded head is an ancestor of it). "
                               f"When phase_start.py did not run before this phase's coder, run `{COMMAND}` first.")


def changed_dirty_files(repo, record):
    """The paths of `record["dirty"]` whose bytes now differ from the recorded hash. A deleted file counts as changed
    unless it was recorded as gone."""
    root = pathlib.Path(repo)
    return sorted(path for path, saved in record["dirty"].items() if worktree_snapshot.file_hash(root, path) != saved)


def handed_off_paths(run_folder):
    """The files the phase that just ended named in its hand-off; [] with no hand-off."""
    handoff_file = run_folder / code_wait.HANDOFF_FILE
    if not handoff_file.is_file():
        return []

    return handoff_files.handoff_entry_paths(handoff_file.read_text())


def with_later_dirty_files(kept, record, handed_off):
    """The kept record plus the files dirty now that it lacks and no phase so far handed off, and the handed-off files
    as the run's own. Every other key of the kept record (head, holder, sessions, started_at) is unchanged."""
    own = sorted({*kept["own"], *handed_off})
    new_dirty = {path: saved for path, saved in record["dirty"].items()
                 if path not in kept["dirty"] and path not in own}
    return {**kept, "dirty": {**kept["dirty"], **new_dirty}, "own": own}


def move_aside(folder, name, previous_name):
    """Rename <folder>/<name> to <previous_name>, replacing an older one, so the fork's next file of that name is new:
    the Write tool refuses an existing file the fork has not read. A failed rename is reported and the script goes
    on."""
    current_file = folder / name
    if not current_file.is_file():
        return

    previous_file = folder / previous_name
    try:
        os.replace(current_file, previous_file)
    except OSError as error:
        print(f"phase_start: could not move {current_file} to {previous_file}: {error}", file=sys.stderr)


def done_phase_numbers(repo, commit, markdown_path):
    """The numbers of the phases marked done in the `## Phase Status` of `markdown_path` at `commit`. A file missing
    at that commit has no phases. A line that does not parse is skipped."""
    text = script_utils.git_output(repo, "show", f"{commit}:{markdown_path}")
    if text is None:
        return set()
    entries, _ = plan_format.phase_status_entries(text.splitlines(), lambda title: None)
    return {entry["number"] for entry in entries if entry["done"]}


def ticked_since(repo, kept_head):
    """(path, phase number) of the first phase that is done at HEAD and was not done at `kept_head`, in a `.md` file
    changed between them; None when no phase was ticked."""
    changed = script_utils.git_output(repo, "diff", "--name-only", kept_head, "HEAD", "--", "*.md")
    if not changed:
        return None

    for markdown_path in changed.splitlines():
        done_before = done_phase_numbers(repo, kept_head, markdown_path)
        done_now = done_phase_numbers(repo, "HEAD", markdown_path)
        newly_done = sorted(done_now - done_before)
        if newly_done:
            return markdown_path, newly_done[0]
    return None


def resume_base(repo, kept):
    """The phase base of a resume: the kept record's head when it is an ancestor of HEAD and no phase was ticked since;
    else None."""
    if kept is None:
        print("phase_start: no start record to resume from; the phase base is HEAD.", file=sys.stderr)
        return None
    if not script_utils.is_ancestor(repo, kept["head"], "HEAD"):
        print(f"phase_start: the start record's head {kept['head']} is not an ancestor of HEAD; the phase base is "
              "HEAD.", file=sys.stderr)
        return None

    ticked = ticked_since(repo, kept["head"])
    if ticked is not None:
        markdown_path, number = ticked
        print(f"phase_start: phase {number} of {markdown_path} was ticked since the start record; starting a new "
              "record at HEAD", file=sys.stderr)
        return None
    return kept["head"]


def other_run_refusal(run_folder):
    """The refusal text when this repo's run folder holds no stop of its own (no stop.md, and no stop.prev.md newer
    than the session's recorded stop) and that recorded stop is in another run folder; None otherwise. Fail-open: no
    session id or no record resumes as before."""
    if (run_folder / stop_file_names.STOP_FILE).is_file():
        return None

    recorded = code_stop_record.last_stop(os.environ.get("CLAUDE_CODE_SESSION_ID"))
    if recorded is None:
        return None
    previous_stop = run_folder / stop_file_names.PREVIOUS_STOP_FILE
    if previous_stop.is_file() and previous_stop.stat().st_mtime > recorded["time"]:
        return None
    if pathlib.Path(recorded["runFolder"]).resolve() == run_folder.resolve():
        return None
    resume_line = recorded["goOn"] or f"/code resume {recorded['repoTop']}"
    return (f"phase_start: --resume found no stop in {run_folder}, and this session's last stop is in "
            f"{recorded['runFolder']}. Resume that run from its repo: {resume_line}")


def kept_record(kept, fresh, own_session_id):
    """The kept record of the run's start with this call's additions: this session's id when missing, and the holder
    seen now when the kept record has none. head, dirty and started_at stay as recorded."""
    sessions = list(kept["sessions"])
    if own_session_id and own_session_id not in sessions:
        sessions.append(own_session_id)
    holder = kept["holder"] or fresh["holder"]
    return {**kept, "holder": holder, "sessions": sessions}


def write_record(repo, record):
    folder = code_wait.phase_dir(repo)
    folder.mkdir(exist_ok=True)
    script_utils.write_text_atomically(folder / START_FILE, json.dumps(record, indent=2) + "\n")


def record_resume_or_exit(run_folder, repo):
    """Writes resume.json after the start record. A git fault there removes any stale resume.json (it would hold an
    older head and tree) and exits non-zero naming what was written, with no base printed."""
    try:
        resume_review_gate.record_resume(run_folder, repo)
    except script_utils.GitCallError as error:
        resume_review_gate.clear_resume(run_folder)
        sys.exit(f"phase_start: the start record was written, but {run_folder / resume_review_gate.RESUME_FILE} was "
                 f"not written, and any older one was removed ({error}). Fix the git fault and re-run "
                 f"`phase_start.py --resume`; the resume has no review check until then.")


def derived_name_match(reports_to):
    """The live registry row whose derived name may be the ListAgents name `reports_to`: a row with nameSource
    `derived` whose cwd folder name plus a dash and two hex characters is `reports_to` (the registry stores another
    suffix than ListAgents shows). None when no row fits."""
    for row in session_registry.live_session_rows():
        cwd = row.get("cwd")
        if row.get("nameSource") != "derived" or not isinstance(cwd, str) or not cwd:
            continue
        if re.fullmatch(re.escape(pathlib.Path(cwd).name) + "-[0-9a-f]{2}", reports_to):
            return row
    return None


def report_to_refusal(repo):
    """The stop text when this repo is a lane worktree whose lane file names a report-to session that no live
    registry row carries, listing the live names; None when it is live, the lane names none, the repo is no lane, or
    the lane file cannot be read (a note goes to stderr: the check never blocks on what it cannot read)."""
    try:
        lane = lane_entries.entry_containing(repo)
    except (lane_entries.LaneFileError, OSError) as error:
        print(f"phase_start: report-to session not checked: {error}", file=sys.stderr)
        return None
    if lane is None or not lane["reports_to"]:
        return None
    live_names = sorted({row["name"] for row in session_registry.live_session_rows() if row.get("name")})
    if lane["reports_to"] in live_names:
        return None
    if derived_name_match(lane["reports_to"]) is not None:
        print(f"phase_start: report-to session {lane['reports_to']} matches a live auto-named session, so it is "
              "taken as live", file=sys.stderr)
        return None
    listed = ", ".join(live_names) or "none"
    return (f"phase_start: the lane reports to session {lane['reports_to']}, which is not live. Live sessions: "
            f"{listed}. Ask the session that started this run for the name, then send every question and the "
            f"result to it.")


def main():
    flags = ("--new-run", "--resume")
    unknown = [arg for arg in sys.argv[1:] if arg not in flags]
    if unknown:
        sys.exit(f"phase_start: unknown argument {unknown[0]}\nusage: phase_start.py [--new-run | --resume]")
    if "--new-run" in sys.argv[1:] and "--resume" in sys.argv[1:]:
        sys.exit("phase_start: --new-run and --resume exclude each other\nusage: phase_start.py [--new-run | --resume]")

    repo = script_utils.repo_root(pathlib.Path.cwd())
    if repo is None:
        sys.exit(f"phase_start: {pathlib.Path.cwd()} is not inside a git work tree")

    if "--new-run" in sys.argv[1:]:
        refusal = report_to_refusal(repo)
        if refusal is not None:
            sys.exit(refusal)

    run_folder = code_wait.phase_dir(repo)
    if "--resume" in sys.argv[1:]:
        refusal = other_run_refusal(run_folder)
        if refusal is not None:
            sys.exit(refusal)
    handed_off = handed_off_paths(run_folder)
    move_aside(run_folder, stop_file_names.STOP_FILE, stop_file_names.PREVIOUS_STOP_FILE)
    move_aside(run_folder, code_wait.HANDOFF_FILE, code_wait.PREVIOUS_HANDOFF_FILE)
    move_aside(run_folder, stop_file_names.LOOP_DIR_FILE, stop_file_names.PREVIOUS_LOOP_DIR_FILE)
    move_aside(run_folder, code_wait.SCOPE_FILE, code_wait.PREVIOUS_SCOPE_FILE)
    if "--resume" not in sys.argv[1:]:
        resume_review_gate.clear_resume(run_folder)

    own_session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    if not own_session_id:
        print("phase_start: CLAUDE_CODE_SESSION_ID is not set, so no holder or session is recorded", file=sys.stderr)
    try:
        record = start_record(repo, own_session_id)
    except StartRecordError as error:
        sys.exit(f"phase_start: {error}")

    try:
        kept = read_start_record(repo)
    except StartRecordError as error:
        print(f"phase_start: replacing the bad start record: {error}", file=sys.stderr)
        kept = None
    if "--resume" in sys.argv[1:]:
        base = resume_base(repo, kept)
        if base is not None:
            write_record(repo, with_later_dirty_files(kept_record(kept, record, own_session_id), record, handed_off))
            record_resume_or_exit(run_folder, repo)
            print(base)
            return 0
    same_run = "--new-run" not in sys.argv[1:] and kept is not None and kept["head"] == record["head"]
    if same_run:
        record = with_later_dirty_files(kept_record(kept, record, own_session_id), record, handed_off)
        if record == kept:
            print(record["head"])
            return 0
    else:
        fix_coder_written.clear(repo)

    write_record(repo, record)
    if "--resume" in sys.argv[1:]:
        record_resume_or_exit(run_folder, repo)
    print(record["head"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
