"""Usage: land_lane.py <lane worktree> [--main <main checkout>] [--base master] [--remote origin]
       land_lane.py --help

Lands a lane branch on <remote>/<base> in one run. --main defaults to ~/dotfiles.
Steps, in order:
  0. A lane with uncommitted changes, tracked or untracked (ignored files excepted), stops the run.
  1. <main> must have <base> checked out (a detached HEAD or another branch stops the run).
  2. `git fetch <remote>` in the lane.
  3. Preflight: a file that <main> has changed (staged, unstaged, deleted, renamed, or untracked) and that the pull
     into <main> brings in, read against <main>'s own HEAD (the lane HEAD and <remote>/<base>, so commits <main> has
     not pulled count), stops the run, exit 1, before the merge, the suite or the push.
  4. When <remote>/<base> is not an ancestor of the lane HEAD, merge it in the lane. A conflict is aborted and listed;
     a merge that fails for another reason is reported as that. Merged or not, the suite is skipped only when a
     green suite receipt covers the tree (suite_receipt.py check); else it runs (`bash tests/run.sh`, under a memory
     cap when the machine can run one). A corrupt receipt row stops the run. A failing suite stops the
     run before the push.
  5. The main-on-<base> check and the preflight run again, since <main> may have changed during the suite. The lane
     must still be clean, on the same branch and at the same commit as after the merge in step 4; else the run
     stops, since the suite did not test what would be pushed.
  6. `git push <remote> <commit after the merge>:<base>`. A push rejected because <base> moved goes back to step 0;
     three attempts at most.
  7. `pull_keep_index.py <main>` runs and its exit code is the exit code of this run.
Every stop in steps 0 to 6 prints the state, then `rerun: <command>` on its own line. A failure in step 7 prints
none: pull_keep_index.py prints its own recovery.
Exit 0 prints one summary line, then the output of pull_keep_index.py. Bad arguments print this text to stderr and
exit 2."""
import argparse
import os
import pathlib
import shlex
import subprocess
import sys
import tempfile
from typing import NamedTuple

TOOLS_DIR = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(TOOLS_DIR.parent / "lib")]
import memory_cap_scope
import script_utils
import suite_receipt
import worktree_snapshot

MAX_ATTEMPTS = 3
SUITE_COMMAND = "bash tests/run.sh"
DEFAULT_MAIN = "~/dotfiles"
LOG_TAIL_LINES = 20
PULL_SCRIPT = TOOLS_DIR / "pull_keep_index.py"
# Words git prints when a push is refused because the remote branch moved.
REJECTED_WORDS = ("non-fast-forward", "fetch first", "[rejected]")


class LandError(Exception):
    """A stop: the message names the state; main prints the recovery command after it."""


class GitStepError(LandError):
    """A command the run needs failed or could not start."""


class LaneState(NamedTuple):
    """The commit and branch the suite or the receipt vouched for."""
    head: str
    branch: str


class PushRejectedError(Exception):
    """The remote branch moved since the fetch; the run starts over."""


def land_git(repo, *arguments, check=True):
    """The finished `git <arguments>` in repo; with check, a failure raises GitStepError naming the command."""
    return script_utils.run_or_raise(["git", *arguments], GitStepError, cwd=repo, check=check)


def land_git_text(repo, *arguments):
    """The stripped standard output of `git <arguments>` in repo."""
    return land_git(repo, *arguments).stdout.strip()


def dirty_files(repo):
    """({path: status code}, {new path: old path} for each rename) of every dirty file in repo."""
    try:
        return worktree_snapshot.status_entries(pathlib.Path(repo), strict=True)
    except script_utils.GitCallError as error:
        raise GitStepError(str(error)) from error


def preflight(main, *incoming):
    """Stop when <main> holds local changes to a file the pull into <main> brings in. A revision of `incoming` (the
    lane HEAD, <remote>/<base>) is read against <main>'s own HEAD, so commits <main> has not pulled count too; a
    rename's old name counts as well as its new one."""
    overlapping = set()
    for revision in incoming:
        try:
            overlapping.update(suite_receipt.dirty_merge_paths(main, revision))
        except suite_receipt.ReceiptError as error:
            raise GitStepError(str(error)) from error
    if not overlapping:
        return
    print("\n".join(f"  {name}" for name in sorted(overlapping)))
    raise LandError(f"{main} has local changes to files this pull brings in; commit them or set them aside "
                    f"in {main}")


def merge_base_into_lane(lane, remote_base):
    """Merge <remote>/<base> into the lane; abort and raise on a conflict, report any other failure as itself."""
    merged = land_git(lane, "merge", "--no-edit", remote_base, check=False)
    if merged.returncode == 0:
        return
    listed = land_git(lane, "diff", "--name-only", "--diff-filter=U", "-z", check=False)
    conflicted = [name for name in listed.stdout.split("\0") if name]
    if not conflicted:
        raise LandError(f"merging {remote_base} into {lane} failed without a conflict: "
                        f"{merged.stderr.strip() or merged.stdout.strip()}; nothing was aborted; "
                        f"inspect with `git -C {lane} status`")
    land_git(lane, "merge", "--abort")
    raise LandError(f"merging {remote_base} conflicts in {', '.join(conflicted)}; merge aborted; "
                    f"merge {remote_base} in {lane} by hand")


def receipt_covers_tree(lane, remote_base):
    """True when suite_receipt.check says the lane HEAD needs no suite run; an unreadable receipt is a stop."""
    try:
        code, _message = suite_receipt.check(lane, "HEAD", remote_base)
    except suite_receipt.ReceiptRowError as error:
        raise LandError(f"{error}; repair or remove that row") from error
    except suite_receipt.ReceiptError as error:
        raise GitStepError(str(error)) from error
    return code == suite_receipt.EXIT_SKIP


def run_suite(lane):
    """Run the suite in the lane; a failure raises LandError naming the log tail."""
    log_handle, log_name = tempfile.mkstemp(prefix="land-lane-suite-", suffix=".log")
    command, use_shell = memory_cap_scope.shell_popen_args(SUITE_COMMAND)
    with os.fdopen(log_handle, "w") as log_file:
        finished = subprocess.run(command, shell=use_shell, cwd=lane, stdout=log_file, stderr=subprocess.STDOUT,
                                  stdin=subprocess.DEVNULL, check=False)
    if finished.returncode == 0:
        pathlib.Path(log_name).unlink()
        return
    log_lines = pathlib.Path(log_name).read_text(errors="replace").splitlines()
    print("\n".join(log_lines[-LOG_TAIL_LINES:]))
    raise LandError(f"the suite failed (exit {finished.returncode}); nothing was pushed; "
                    f"fix it in {lane} (log {log_name})")


def test_or_skip(lane, remote_base):
    """Run the suite unless a green suite receipt covers the tree; the summary phrase."""
    if receipt_covers_tree(lane, remote_base):
        return "suite skipped on receipt"
    run_suite(lane)
    return "suite ran"


def merge_if_behind(lane, remote_base):
    """Step 4, the merge half. The summary phrase for it."""
    if script_utils.is_ancestor(lane, remote_base, "HEAD"):
        return "no merge"
    merge_base_into_lane(lane, remote_base)
    return "merged"


def push_lane(lane, remote, base, commit):
    pushed = land_git(lane, "push", remote, f"{commit}:{base}", check=False)
    if pushed.returncode == 0:
        return
    if any(word in pushed.stderr for word in REJECTED_WORDS):
        raise PushRejectedError(pushed.stderr.strip())
    raise LandError(f"the push of {lane} to {remote}/{base} failed: {pushed.stderr.strip()}; "
                    "fix the cause")


def checked_out_branch(repo):
    """The branch repo has checked out, or "" for a detached HEAD; a git failure raises GitStepError."""
    branch = script_utils.current_branch(repo)
    if branch is None:
        raise GitStepError(f"git branch --show-current failed in {repo}")
    return branch


def stop_on_dirty_lane(lane):
    """The suite runs on the lane's work tree but the push sends a commit, so tracked changes and new files that are
    not ignored would go unvouched."""
    codes, _origins = dirty_files(lane)
    if codes:
        raise LandError(f"{lane} has uncommitted changes; commit or set them aside in {lane}")


def stop_unless_main_has_base(main, base):
    """The pull into <main> only brings in <base> when <main> has <base> checked out."""
    branch = checked_out_branch(main)
    if branch == base:
        return
    held = f"branch {branch}" if branch else "a detached HEAD"
    raise LandError(f"{main} has {held} checked out, not {base}; check out {base} in {main}")


def read_lane_state(lane):
    return LaneState(head=land_git_text(lane, "rev-parse", "HEAD"), branch=checked_out_branch(lane))


def stop_if_lane_moved(lane, vouched):
    """The commit that the suite or receipt vouched for is the one to push; a suite that committed, switched branch
    or left changes behind means the push would send untested work."""
    now = read_lane_state(lane)
    if now != vouched:
        raise LandError(f"{lane} moved during the suite (was {vouched.head[:12]} on "
                        f"{vouched.branch or 'a detached HEAD'}, now {now.head[:12]} on "
                        f"{now.branch or 'a detached HEAD'}); nothing was pushed; commit that work and rerun")
    stop_on_dirty_lane(lane)


class LandedPass(NamedTuple):
    """What a finished pass pushed: the summary phrase for the merge and suite, and the commit."""
    outcome: str
    commit: str


def land_once(lane, main, remote, base):
    """One pass of steps 0 to 6; the LandedPass."""
    remote_base = f"{remote}/{base}"
    stop_on_dirty_lane(lane)
    stop_unless_main_has_base(main, base)
    land_git(lane, "fetch", remote)
    preflight(main, land_git_text(lane, "rev-parse", "HEAD"), remote_base)
    merge_phrase = merge_if_behind(lane, remote_base)
    vouched = read_lane_state(lane)
    outcome = f"{merge_phrase}, {test_or_skip(lane, remote_base)}"
    stop_unless_main_has_base(main, base)
    preflight(main, vouched.head)
    stop_if_lane_moved(lane, vouched)
    push_lane(lane, remote, base, vouched.head)
    return LandedPass(outcome=outcome, commit=vouched.head)


def land(lane, main, remote, base):
    for _attempt in range(MAX_ATTEMPTS):
        try:
            landed = land_once(lane, main, remote, base)
            break
        except PushRejectedError as rejected:
            last_cause = str(rejected)
    else:
        raise LandError(f"{remote}/{base} moved during all {MAX_ATTEMPTS} attempts ({last_cause})")
    print(f"land_lane: {landed.outcome}; pushed {landed.commit[:7]} to {remote}/{base}")


def read_land_lane_arguments(argv):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("lane")
    parser.add_argument("--main", default=DEFAULT_MAIN)
    parser.add_argument("--base", default="master")
    parser.add_argument("--remote", default="origin")
    return parser.parse_args(argv)


def main(argv):
    if script_utils.help_requested(argv):
        print(__doc__)
        return 0
    try:
        args = read_land_lane_arguments(argv)
    except SystemExit:
        print(__doc__, file=sys.stderr)
        return 2
    lane = str(pathlib.Path(args.lane).expanduser().resolve())
    main_checkout = str(pathlib.Path(args.main).expanduser().resolve())
    script_path = str(pathlib.Path(__file__).resolve())
    rerun_command = shlex.join(["python3", script_path, lane, "--main", main_checkout, "--base", args.base,
                                "--remote", args.remote])
    try:
        land(lane, main_checkout, args.remote, args.base)
    except GitStepError as stop:
        print(f"land_lane: {stop}; inspect with `git -C {lane} status` and `git -C {main_checkout} status`")
        print(f"rerun: {rerun_command}")
        return 1
    except LandError as stop:
        print(f"land_lane: {stop}")
        print(f"rerun: {rerun_command}")
        return 1
    pulled = subprocess.run([sys.executable, str(PULL_SCRIPT), main_checkout], check=False)
    return pulled.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
