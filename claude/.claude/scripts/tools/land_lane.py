"""Usage: land_lane.py <lane worktree> [--main <main checkout>] [--base master] [--remote origin]
       land_lane.py --help

Lands a lane branch on <remote>/<base> in one run. --main defaults to ~/dotfiles.
Steps, in order:
  0. A lane with uncommitted changes, tracked or untracked (ignored files excepted), stops the run.
  1. `git fetch <remote>` in the lane.
  2. Preflight: a file the lane changed since its merge base with <remote>/<base> that <main> also has changed
     (staged, unstaged, deleted, renamed, or untracked) stops the run, exit 1, before the merge, the suite or the push.
  3. When <remote>/<base> is not an ancestor of the lane HEAD, merge it in the lane. A conflict is aborted and listed;
     a merge that fails for another reason is reported as that. Merged or not, the suite is skipped only when a
     green suite receipt covers the tree (suite_receipt.py check); else it runs (`bash tests/run.sh`, under a memory
     cap when the machine can run one). A corrupt receipt row stops the run. The environment variable
     LAND_LANE_SUITE, a command string run with `bash -c`, replaces the suite command. A failing suite stops the
     run before the push.
  4. The preflight runs again, since <main> may have changed during the suite.
  5. `git push <remote> HEAD:<base>`. A push rejected because <base> moved goes back to step 0; three attempts at most.
  6. `pull_keep_index.py <main>` runs and its exit code is the exit code of this run.
Every stop prints the state, then `rerun: <command>` on its own line.
Exit 0 prints one summary line, then the output of pull_keep_index.py."""
import argparse
import os
import pathlib
import shlex
import subprocess
import sys
import tempfile

TOOLS_DIR = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(TOOLS_DIR.parent / "lib"), str(TOOLS_DIR.parent / "review")]
import memory_cap_scope
import script_utils
import suite_receipt
import worktree_snapshot

MAX_ATTEMPTS = 3
SUITE_VARIABLE = "LAND_LANE_SUITE"
DEFAULT_MAIN = "~/dotfiles"
LOG_TAIL_LINES = 20
PULL_SCRIPT = TOOLS_DIR / "pull_keep_index.py"
# Words git prints when a push is refused because the remote branch moved.
REJECTED_WORDS = ("non-fast-forward", "fetch first", "[rejected]")


class LandError(Exception):
    """A stop: the message names the state; main prints the recovery command after it."""


class GitStepError(LandError):
    """A command the run needs failed or could not start."""


class PushRejectedError(Exception):
    """The remote branch moved since the fetch; the run starts over."""


def land_git(repo, *arguments, check=True):
    """The finished `git <arguments>` in repo; with check, a failure raises GitStepError naming the command."""
    return script_utils.run_or_raise(["git", *arguments], GitStepError, cwd=repo, check=check)


def land_git_text(repo, *arguments):
    """The stripped standard output of `git <arguments>` in repo."""
    return land_git(repo, *arguments).stdout.strip()


def lane_touched_files(lane, remote_base):
    """Every name the lane changed since its merge base with remote_base; --no-renames lists a rename's old name too."""
    merge_base = land_git_text(lane, "merge-base", remote_base, "HEAD")
    listed = land_git(lane, "diff", "--name-only", "--no-renames", "-z", merge_base, "HEAD")
    return {name for name in listed.stdout.split("\0") if name}


def dirty_main_files(main):
    """{path: status code} for every dirty file in main, and {new path: old path} for each rename."""
    try:
        return worktree_snapshot.status_entries(pathlib.Path(main), strict=True)
    except script_utils.GitCallError as error:
        raise GitStepError(str(error)) from error


def preflight(lane, main, remote_base):
    """Stop when <main> has changed a file the lane also changed, under either name of a rename."""
    touched = lane_touched_files(lane, remote_base)
    codes, origins = dirty_main_files(main)
    overlapping = []
    for name, code in sorted(codes.items()):
        names = [name]
        if name in origins:
            names.append(origins[name])
        if touched.intersection(names):
            overlapping.append(f"  {code} {' <- '.join(names)}")
    if not overlapping:
        return
    print("\n".join(overlapping))
    raise LandError(f"{main} has local changes to files this lane touches; commit them or set them aside "
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


def suite_command():
    override = os.environ.get(SUITE_VARIABLE)
    if override:
        return ["bash", "-c", override]
    if memory_cap_scope.cap_available():
        return [*shlex.split(memory_cap_scope.CAPPED_PREFIX), "bash", "tests/run.sh"]
    return ["bash", "tests/run.sh"]


def receipt_covers_tree(lane, remote_base):
    """True when suite_receipt.check says the lane HEAD needs no suite run; an unreadable receipt is a stop."""
    try:
        code, _message = suite_receipt.check(lane, "HEAD", remote_base)
    except suite_receipt.ReceiptError as error:
        raise LandError(f"{error}; repair or remove that row") from error
    return code == suite_receipt.EXIT_SKIP


def run_suite(lane):
    """Run the suite in the lane; a failure raises LandError naming the log tail."""
    log_handle, log_name = tempfile.mkstemp(prefix="land-lane-suite-", suffix=".log")
    with os.fdopen(log_handle, "w") as log_file:
        finished = subprocess.run(suite_command(), cwd=lane, stdout=log_file, stderr=subprocess.STDOUT,
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


def merge_and_test(lane, remote_base):
    """Step 3. The summary phrase for the merge and the suite."""
    if script_utils.is_ancestor(lane, remote_base, "HEAD"):
        return f"no merge, {test_or_skip(lane, remote_base)}"
    merge_base_into_lane(lane, remote_base)
    return f"merged, {test_or_skip(lane, remote_base)}"


def push_lane(lane, remote, base):
    pushed = land_git(lane, "push", remote, f"HEAD:{base}", check=False)
    if pushed.returncode == 0:
        return
    if any(word in pushed.stderr for word in REJECTED_WORDS):
        raise PushRejectedError(pushed.stderr.strip())
    raise LandError(f"the push of {lane} to {remote}/{base} failed: {pushed.stderr.strip()}; "
                    "fix the cause")


def stop_on_dirty_lane(lane):
    """The suite runs on the lane's work tree but the push sends HEAD, so tracked changes and new files that are not
    ignored would go unvouched."""
    status = land_git_text(lane, "status", "--porcelain")
    if status:
        raise LandError(f"{lane} has uncommitted changes; commit or set them aside in {lane}")


def land_once(lane, main, remote, base):
    """One pass of steps 0 to 5; the summary phrase for the merge and suite."""
    remote_base = f"{remote}/{base}"
    stop_on_dirty_lane(lane)
    land_git(lane, "fetch", remote)
    preflight(lane, main, remote_base)
    outcome = merge_and_test(lane, remote_base)
    preflight(lane, main, remote_base)
    push_lane(lane, remote, base)
    return outcome


def land(lane, main, remote, base):
    for _attempt in range(MAX_ATTEMPTS):
        try:
            outcome = land_once(lane, main, remote, base)
            break
        except PushRejectedError as rejected:
            last_cause = str(rejected)
    else:
        raise LandError(f"{remote}/{base} moved during all {MAX_ATTEMPTS} attempts ({last_cause})")
    pushed_hash = land_git_text(lane, "rev-parse", "--short", "HEAD")
    print(f"land_lane: {outcome}; pushed {pushed_hash} to {remote}/{base}")


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
    rerun_command = shlex.join(["python3", script_path, *argv])
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
