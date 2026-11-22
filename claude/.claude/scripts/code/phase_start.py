#!/usr/bin/env python3
"""Record the tree a /code run starts from (kept across the run's phases at one HEAD), and print the phase base (HEAD,
or the kept record's head under --resume).

    python3 ~/.claude/scripts/code/phase_start.py [--new-run | --resume]

Run from the repo root before the phase's coder dispatch. Writes <git dir>/code-phase/start.json:
{"head": <sha>, "dirty": {<path>: <sha-256 of its bytes, or null when gone>}} for every file dirty or untracked now.
code_review_start.py reads it: a file dirty here that holds the same bytes at review time, while a live session other
than the run's works in the repo, is held by that session.
The record is of the run's start, not of each phase: `--new-run` replaces it. Without the flag an existing record
whose head is the current HEAD is kept, so the files an earlier phase of the run left dirty stay the run's own. A
missing record, or one for another HEAD, is replaced either way. Prints the HEAD sha, except under --resume (below).
`--resume` is for a run that went on after a stop, where the user may have committed the phase since: when the
kept record's head is an ancestor of HEAD, the record is kept and its head is printed as the phase base. With no
record, or a head that is not an ancestor, it prints HEAD as without the flag and says so on stderr.
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
import sys

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path[:0] = [str(SCRIPTS_DIR / folder) for folder in ("lib", "code")]

import code_stop_record
import code_wait
import script_utils
import stop_file_names
import worktree_snapshot

START_FILE = "start.json"
COMMAND = "python3 ~/.claude/scripts/code/phase_start.py"


class StartRecordError(ValueError):
    """A start record that is missing a field or names another phase base."""


def start_record(repo):
    """{"head", "dirty"} of the repo now."""
    head = script_utils.head_commit(repo)
    if head is None:
        raise StartRecordError(f"{repo} has no HEAD commit, so the phase has no base")

    root = pathlib.Path(repo)
    codes = worktree_snapshot.status_codes(root)
    dirty = {path: worktree_snapshot.file_hash(root, path) for path in sorted(codes)}
    return {"head": head, "dirty": dirty}


def read_start_record(repo):
    """The start record on disk as {"head", "dirty"}; None when there is no file. A record that does not parse raises
    StartRecordError."""
    record_file = code_wait.phase_dir(repo) / START_FILE
    if not record_file.is_file():
        return None

    try:
        record = json.loads(record_file.read_text())
        return {"head": record["head"], "dirty": record["dirty"]}
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise StartRecordError(f"{record_file}: {error}; expected {{\"head\": <sha>, \"dirty\": {{<path>: <hash>}}}}. "
                               "Re-run phase_start.py before the next coder dispatch.") from error


def base_relates_to_head(repo, base_commit, head):
    """Whether `base_commit` is the recorded head, an ancestor of it (a merge-base), or the current HEAD when the
    recorded head is an ancestor of it (a resume base)."""
    if script_utils.is_ancestor(repo, base_commit, head):
        return True
    if not script_utils.is_ancestor(repo, head, base_commit):
        return False
    return base_commit == script_utils.head_commit(repo)


def unchanged_dirty_files(repo, base_commit):
    """The files dirty when the run started (the kept start record) that hold the same bytes now: another session's,
    not the run's. None when no start record exists. A record whose head is neither an ancestor nor a descendant of
    the base, or one that does not parse, raises StartRecordError."""
    record = read_start_record(repo)
    if record is None:
        return None

    head, dirty = record["head"], record["dirty"]
    record_file = code_wait.phase_dir(repo) / START_FILE
    if not base_relates_to_head(repo, base_commit, head):
        raise StartRecordError(f"{record_file} records phase base {head}, and {base_commit} is neither an ancestor of "
                               f"it nor the current HEAD it is an ancestor of. Pass --base {head} (a base may be an "
                               "ancestor of the recorded head, or HEAD when the recorded head is an ancestor of it). "
                               f"When phase_start.py did not run before this phase's coder, run `{COMMAND}` first.")

    root = pathlib.Path(repo)
    return sorted(path for path, saved in dirty.items() if worktree_snapshot.file_hash(root, path) == saved)


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


def resume_base(repo, kept):
    """The phase base of a resume: the kept record's head when it is an ancestor of HEAD, else None."""
    if kept is None:
        print("phase_start: no start record to resume from; the phase base is HEAD.", file=sys.stderr)
        return None
    if not script_utils.is_ancestor(repo, kept["head"], "HEAD"):
        print(f"phase_start: the start record's head {kept['head']} is not an ancestor of HEAD; the phase base is "
              "HEAD.", file=sys.stderr)
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

    run_folder = code_wait.phase_dir(repo)
    if "--resume" in sys.argv[1:]:
        refusal = other_run_refusal(run_folder)
        if refusal is not None:
            sys.exit(refusal)
    move_aside(run_folder, stop_file_names.STOP_FILE, stop_file_names.PREVIOUS_STOP_FILE)
    move_aside(run_folder, code_wait.HANDOFF_FILE, code_wait.PREVIOUS_HANDOFF_FILE)
    move_aside(run_folder, code_wait.LOOP_DIR_FILE, code_wait.PREVIOUS_LOOP_DIR_FILE)

    try:
        record = start_record(repo)
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
            print(base)
            return 0
    if "--new-run" not in sys.argv[1:] and kept is not None and kept["head"] == record["head"]:
        print(record["head"])
        return 0

    folder = code_wait.phase_dir(repo)
    folder.mkdir(exist_ok=True)
    script_utils.write_text_atomically(folder / START_FILE, json.dumps(record, indent=2) + "\n")
    print(record["head"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
