#!/usr/bin/env python3
"""mutation_lock.py: check, lock, back up and restore the one file a mutation-tester run mutates.

Usage: mutation_lock.py check <target>
       mutation_lock.py lock <target> --class TEXT --line TEXT --owner-pid PID
       mutation_lock.py restore --owner-pid PID --run-id ID

The lock file, its fields and its liveness rule belong to lib/calibration_lock.py; the byte copy and the copy back
to lib/file_backup.py. Every verb prints its result and ends with a NEXT:, STOP: or DONE: line. Exit 0: done or
next step; 1: a precondition failed or the request was refused, the lock untouched (restore, when the file is back
but the lock cannot be removed, prints the rm command); 3: the backup, or the file after the copy back, does not
match the hash the lock recorded; lock kept; 2: bad usage."""
import argparse
import json
import os
import pathlib
import secrets
import sys
import time
from typing import NamedTuple

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parents[1] / "lib")]
import calibration_lock
import file_backup
import file_lock
import script_utils

EXIT_OK = 0
EXIT_STOP = 1
EXIT_RESTORE_MISMATCH = 3

# The one list of the preconditions `check` and `lock` test, in check order. --help prints it.
PRECONDITIONS = (
    "the target is a regular file, not a symlink",
    "the target's folder is inside a git work tree",
    "the target is inside that work tree and not under .git/",
    "no calibration or mutation lock exists, live, stale or at the legacy path",
    "the backups folder can be written",
)

STOP_NOT_A_FILE = "STOP: the target is not a regular file (it is missing, a folder or a symlink); name a regular file"
STOP_NOT_A_REPO = "STOP: the target's folder is not inside a git work tree; name a file of a git repo"
STOP_OUTSIDE_TREE = "STOP: the target is not inside the work tree of its folder, or is under .git/; name a source file"
STOP_LIVE_LOCK = "STOP: a mutation or calibration run is live; do not touch its lock or file; wait for it to end"
STOP_UNRESTORED = "STOP: an earlier run left a lock; hand the recovery commands above to the caller; do not lock"
STOP_STATE_UNWRITABLE = "STOP: the state folder (lock or backups) cannot be written; hand this to the caller"
STOP_LOCK_BUSY = "STOP: another process holds the lock-write file; retry once, then hand this to the caller"
STOP_BACKUP_FAILED = "STOP: the target could not be backed up (too large or unreadable); no lock was written"
STOP_BAD_ARGUMENT = "STOP: --class must be one non-empty line"
STOP_NO_LOCK = "STOP: there is no lock; nothing to restore"
STOP_LEGACY_LOCK = "STOP: the lock sits at the legacy path; restore it by hand with the commands above"
STOP_OLD_LAYOUT = "STOP: the lock has the old backup layout; restore it by hand with the commands above"
STOP_NOT_OURS = ("STOP: the lock belongs to another writer, owner or run; "
                 "hand the recovery line above to the caller")
STOP_BACKUP_MISSING = "STOP: the backup named by the lock is missing; the lock is kept; hand this to the caller"
STOP_LOCK_NOT_REMOVED = (
    "STOP: the file is restored but the lock could not be removed; hand the rm line above to the caller")
STOP_RESTORE_MISMATCH = (
    "STOP: the restored file does not match its recorded hash; the lock is kept; report this loudly to the caller")
STOP_RESTORE_FAILED = "STOP: the file could not be restored; the lock is kept; hand the cp line above to the caller"
MISMATCH_HEADING = "RESTORE HASH MISMATCH"
NEXT_LOCK_TEMPLATE = ("NEXT: run the unmutated suite (baseline), then mutation_lock.py lock <target> "
                      "--class ... --line ... --owner-pid \"$PPID\"")
NEXT_APPLY = ("NEXT: apply the mutation with Edit (Step 2); restore later with "
              "mutation_lock.py restore --owner-pid \"$PPID\" --run-id {run_id}")
DONE_RESTORE = "DONE: restore hash-verified ({how}); lock removed"


class StopError(Exception):
    """A refused or failed request: the lines to print (the last is the STOP: line) and the exit code."""

    def __init__(self, lines, code=EXIT_STOP):
        super().__init__(lines[-1])
        self.lines = lines
        self.code = code


class Target(NamedTuple):
    file: pathlib.Path
    worktree: pathlib.Path
    relpath: str


def locate_target(target_text):
    """Preconditions 1 to 3: the target's file, work tree and path in the tree."""
    file = pathlib.Path(os.path.abspath(target_text))
    if file.is_symlink() or not file.is_file():
        raise StopError([STOP_NOT_A_FILE])

    folder = file.parent.resolve()
    top = script_utils.repo_root(folder)
    if top is None:
        inside_git_dir = script_utils.git_output(folder, "rev-parse", "--is-inside-git-dir")
        if inside_git_dir == "true":
            raise StopError([STOP_OUTSIDE_TREE])
        raise StopError([STOP_NOT_A_REPO])

    worktree = top.resolve()
    try:
        relpath = (folder / file.name).relative_to(worktree).as_posix()
    except ValueError as error:
        raise StopError([f"{file} is not under {worktree} ({error})", STOP_OUTSIDE_TREE]) from error
    if relpath.split("/")[0] == ".git":
        raise StopError([STOP_OUTSIDE_TREE])
    return Target(file, worktree, relpath)


def refuse_existing_lock():
    """Precondition 4: stop on any lock, live, stale, unreadable or at the legacy path."""
    found = calibration_lock.find_lock()
    if found is None:
        return

    text = calibration_lock.read_lock_text(found)
    view = calibration_lock.read_lock_view(text)
    live = calibration_lock.lock_is_live(view.stamp, view.owner_pid, time.time(), view.writer)
    if live:
        notice = calibration_lock.live_notice(view.kind, view.file, view.worktree, view.owner_pid)
        raise StopError([notice.rstrip("\n"), STOP_LIVE_LOCK])

    message = calibration_lock.unrestored_message(view, found)
    raise StopError([f"locked file: {view.file}", f"backup: {view.backup}", message.rstrip("\n"), STOP_UNRESTORED])


def require_writable_backups():
    """Precondition 5: the nearest existing parent of the backups folder is writable. Creates nothing."""
    folder = calibration_lock.backups_folder()
    while folder and not os.path.exists(folder):
        folder = os.path.dirname(folder)
    if not os.access(folder or ".", os.W_OK | os.X_OK):
        raise StopError([f"not writable: {folder}", STOP_STATE_UNWRITABLE])


def check_preconditions(target_text):
    """Run the PRECONDITIONS in order; the Target when all pass, else Stop at the first failure.
    Fail-closed: any state this cannot read is a stop, never a pass."""
    target = locate_target(target_text)
    refuse_existing_lock()
    require_writable_backups()
    return target


def uncommitted_note(target):
    """The NOTE: line for a target git reports as modified or untracked, else None. The lock still proceeds: the
    byte backup and the hash-verified restore are what protect the edits."""
    status = script_utils.git_output(target.worktree, "status", "--porcelain", "--", target.relpath)
    if not status:
        return None
    return (f"NOTE: {target.relpath} has uncommitted edits ({status}); "
            "restore brings back the bytes as they are now")


def check_verb(args):
    target = check_preconditions(args.target)
    lines = []
    note = uncommitted_note(target)
    if note:
        lines.append(note)
    lines.append(NEXT_LOCK_TEMPLATE)
    return lines


def lock_fields(target, args, backup_copy, run_id):
    return {
        "ts": calibration_lock.format_stamp(time.time()),
        "kind": calibration_lock.MUTATION_KIND,
        "writer": calibration_lock.MUTATION_WRITER,
        "file": target.relpath,
        "backup_path": backup_copy,
        "pre_hash": calibration_lock.pre_hash(backup_copy),
        "class": "mutant: " + args.seed_class,
        "line": args.line,
        "worktree": str(target.worktree),
        "owner_pid": args.owner_pid,
        "run_id": run_id,
    }


def lock_verb(args):
    if not args.seed_class.strip() or "\n" in args.seed_class or "\r" in args.seed_class:
        raise StopError([STOP_BAD_ARGUMENT])

    # Checked once before the state folder exists, so a refused request creates nothing; lock_under_hold checks again.
    check_preconditions(args.target)
    state_folder = pathlib.Path(calibration_lock.state_folder())
    try:
        os.makedirs(state_folder, exist_ok=True)
        with file_lock.hold_exclusive(state_folder / "lock.write", calibration_lock.LOCK_WAIT_SECONDS):
            return lock_under_hold(args)
    except file_lock.LockTimeoutError as error:
        raise StopError([str(error), STOP_LOCK_BUSY]) from error
    except OSError as error:
        raise StopError([f"cannot write under {state_folder}: {error}", STOP_STATE_UNWRITABLE]) from error


def lock_under_hold(args):
    target = check_preconditions(args.target)
    lines = []
    note = uncommitted_note(target)
    if note:
        lines.append(note)

    backups = pathlib.Path(calibration_lock.backups_folder())
    backup = file_backup.save_files(target.worktree, [target.relpath], backups)
    if backup.unsaved or target.relpath not in backup.saved:
        raise StopError([*lines, f"not backed up: {target.file}", STOP_BACKUP_FAILED])

    # Joined as a string, as refuse_unrestorable rebuilds it.
    backup_copy = calibration_lock.backup_path(target.relpath)
    run_id = secrets.token_hex(8)
    fields = lock_fields(target, args, backup_copy, run_id)
    lock = calibration_lock.lock_path()
    script_utils.write_text_atomically(lock, json.dumps(fields, indent=2) + "\n")
    next_line = NEXT_APPLY.format(run_id=run_id)
    lines += [f"lock: {lock}", f"backup: {backup_copy}", f"pre_hash: {fields['pre_hash']}", next_line]
    return lines


def manual_lines(view, lock):
    copy_command, remove_command = calibration_lock.recovery_commands(view, lock)
    return [f"  {copy_command}", f"  {remove_command}"]


class OwnLock(NamedTuple):
    """The state-path lock, its text read once, its view and the two fields restore acts on."""
    path: str
    view: calibration_lock.LockView
    raw_file: str
    recorded_hash: str
    run_id: str


def read_own_lock():
    """The state-path lock; StopError for a legacy-only or missing lock."""
    lock = calibration_lock.lock_path()
    if os.path.isfile(lock):
        text = calibration_lock.read_lock_text(lock)
        return OwnLock(
            path=lock,
            view=calibration_lock.read_lock_view(text),
            raw_file=calibration_lock.lock_field(text, "file", "?", "?"),
            recorded_hash=calibration_lock.lock_field(text, "pre_hash", "?", "?"),
            run_id=calibration_lock.lock_field(text, "run_id", "", ""),
        )

    legacy = calibration_lock.legacy_lock_path()
    if os.path.isfile(legacy):
        view = calibration_lock.read_lock_view(calibration_lock.read_lock_text(legacy))
        raise StopError([f"legacy lock: {legacy}", *manual_lines(view, legacy), STOP_LEGACY_LOCK])
    raise StopError([STOP_NO_LOCK])


def refuse_unrestorable(own, args):
    """Stop for an old-layout lock or one that is not this run's. Nothing is written."""
    view = own.view
    expected_backup = calibration_lock.backup_path(own.raw_file)
    old_layout = (not view.worktree or own.raw_file == "?" or os.path.isabs(own.raw_file)
                  or view.backup != expected_backup)
    if old_layout:
        raise StopError([f"lock: {own.path}", *manual_lines(view, own.path), STOP_OLD_LAYOUT])

    ours = (view.writer == calibration_lock.MUTATION_WRITER and view.owner_pid == str(args.owner_pid)
            and own.run_id != "" and own.run_id == args.run_id)
    if not ours:
        copy_command, remove_command = calibration_lock.recovery_commands(view, own.path)
        raise StopError([f"lock: {own.path}", f"{copy_command} && {remove_command}", STOP_NOT_OURS])


def mismatch_stop(own, target):
    lines = [MISMATCH_HEADING, f"target: {target}", f"backup: {own.view.backup}", f"lock kept: {own.path}",
             STOP_RESTORE_MISMATCH]
    return StopError(lines, EXIT_RESTORE_MISMATCH)


def copy_back_verified(own):
    """Copy the backup over the target only when the backup matches the recorded hash, then check the target.
    Returns the paths copied. An I/O error keeps the lock and prints the manual recovery line."""
    view = own.view
    target = pathlib.Path(view.file)
    backups = pathlib.Path(calibration_lock.backups_folder())
    try:
        if calibration_lock.pre_hash(view.backup) != own.recorded_hash:
            raise mismatch_stop(own, target)
        copied = file_backup.restore_changed(file_backup.Backup(view.worktree, backups, [own.raw_file], []))
        if copied:
            # copy2 gives the target the backup's old mtime; a build tool must see the file as changed.
            os.utime(target)
        if not target.is_file() or calibration_lock.pre_hash(target) != own.recorded_hash:
            raise mismatch_stop(own, target)
    except OSError as error:
        copy_command, remove_command = calibration_lock.recovery_commands(view, own.path)
        lines = [f"cannot restore {target}: {error}", f"lock kept: {own.path}", f"{copy_command} && {remove_command}"]
        raise StopError([*lines, STOP_RESTORE_FAILED]) from error
    return copied


def restore_verb(args):
    own = read_own_lock()
    refuse_unrestorable(own, args)

    view = own.view
    if not os.path.isfile(view.backup):
        raise StopError([f"missing backup: {view.backup}", f"lock kept: {own.path}", STOP_BACKUP_MISSING])

    copied = copy_back_verified(own)
    try:
        os.unlink(own.path)
    except OSError as error:
        _, remove_command = calibration_lock.recovery_commands(view, own.path)
        raise StopError([f"cannot remove the lock: {error}", f"  {remove_command}", STOP_LOCK_NOT_REMOVED]) from error
    how = "copied" if copied else "already identical"
    return [DONE_RESTORE.format(how=how)]


def positive_int(text):
    try:
        number = int(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"{text!r} is not an integer") from error
    if number <= 0:
        raise argparse.ArgumentTypeError(f"{text!r} is not a positive pid")
    return number


def build_parser():
    epilog = "preconditions, in check order:\n" + "\n".join(
        f"  {number}. {text}" for number, text in enumerate(PRECONDITIONS, 1))
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0], epilog=epilog,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    verbs = parser.add_subparsers(dest="verb", required=True)

    check = verbs.add_parser("check", help="test the preconditions; write nothing")
    check.add_argument("target")

    lock = verbs.add_parser("lock", help="back the target up and write the lock")
    lock.add_argument("target")
    lock.add_argument("--class", dest="seed_class", required=True, help="the mutation class")
    lock.add_argument("--line", required=True, help="the line the mutation touches")
    lock.add_argument("--owner-pid", type=positive_int, required=True, help="the process that owns the run")

    restore = verbs.add_parser("restore", help="put the target back from the backup, verify it, remove the lock")
    restore.add_argument("--owner-pid", type=positive_int, required=True, help="the process that owns the run")
    restore.add_argument("--run-id", required=True, help="the run id that `lock` printed on its NEXT line")
    return parser


VERBS = {"check": check_verb, "lock": lock_verb, "restore": restore_verb}


def main(argv):
    args = build_parser().parse_args(argv[1:])
    try:
        lines = VERBS[args.verb](args)
    except StopError as stop:
        print("\n".join(stop.lines))
        return stop.code
    print("\n".join(lines))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv))
