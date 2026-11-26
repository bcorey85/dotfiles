"""The phase-end change-file check: run the repo's `.githooks/change-file-check` over the work tree's changes.

Run from the repo root. The check reads the `git diff --name-status -z` stream (NUL after each status and each path):
the work tree's changes against HEAD, and each untracked file as an added one. Its refusal text passes through. A
repo without the check passes. A file that phase_start.py recorded as dirty before the run, and whose bytes are
unchanged since, is left out of the stream. Exit 1 when the check refuses, with a last line that names the next step.
Exit 2 when git fails, the start record does not parse or the check crashes."""
import pathlib
import subprocess
import sys

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path[:0] = [str(SCRIPTS_DIR / folder) for folder in ("lib", "code")]

import phase_start
import script_utils

CHECK_RELATIVE_PATH = pathlib.Path(".githooks") / "change-file-check"
NO_CHECK_LINE = "no change-file check in this repo"
NEXT_STEP_LINE = ("Dispatch a coder to file the change file with that command, "
                  "then run phase_change_file.py again.")


def unchanged_since_start(repo, start_record):
    """The paths the start record lists as dirty before the run whose bytes still match the recorded hash; empty with
    no start record."""
    if start_record is None:
        return set()
    changed = set(phase_start.changed_dirty_files(repo, start_record))
    return set(start_record["dirty"]) - changed


def work_tree_changes(repo, start_record=None):
    """The `git diff --name-status -z` stream of the work tree against HEAD (NUL after each status and each path), with
    each untracked file added as an `A` record, and without the files `start_record` lists as dirty before the run
    and unchanged since; None when git fails. `change-file-check` reads it."""
    tracked = script_utils.git_output(repo, "diff", "--name-status", "-z", "--no-renames", "HEAD")
    untracked = script_utils.untracked_paths(repo)
    if tracked is None or untracked is None:
        return None

    left_out = unchanged_since_start(repo, start_record)
    fields = tracked.split("\0")[:-1] if tracked else []
    records = [f"{status}\0{changed_path}\0" for status, changed_path in zip(fields[0::2], fields[1::2], strict=True)
               if changed_path not in left_out]
    records.extend(f"A\0{untracked_path}\0" for untracked_path in untracked if untracked_path not in left_out)
    return "".join(records)


def main():
    repo = script_utils.git_output(pathlib.Path.cwd(), "rev-parse", "--show-toplevel")
    if repo is None:
        print("phase_change_file.py: not inside a git work tree", file=sys.stderr)
        return 2

    check = pathlib.Path(repo) / CHECK_RELATIVE_PATH
    if not check.is_file():
        print(NO_CHECK_LINE)
        return 0

    try:
        start_record = phase_start.read_start_record(repo)
    except phase_start.StartRecordError as error:
        print(f"phase_change_file.py: {error}", file=sys.stderr)
        return 2

    changes = work_tree_changes(repo, start_record)
    if changes is None:
        print("phase_change_file.py: git could not list the work tree's changes", file=sys.stderr)
        return 2

    finished = subprocess.run([str(check)], input=changes, text=True, cwd=repo)
    if finished.returncode == 0:
        return 0

    if finished.returncode != 1:
        print(f"phase_change_file.py: change-file-check failed with exit {finished.returncode}", file=sys.stderr)
        return 2

    print(NEXT_STEP_LINE, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
