"""Usage: suite_receipt.py tree <repo>
       suite_receipt.py record <repo> --tree <tree> --exit <code> --scope <scope> --summary <file>
       suite_receipt.py check <repo> <branch> [--base <base>]
       suite_receipt.py --help

The receipt of each `tests/run.sh` run, so a merge check can skip a suite rerun on a tree that already ran green.

`tree` prints the git tree hash of the work tree that holds <repo> as it stands: tracked files with their edits and
untracked files that are not ignored. It never touches the repo's own index.

`record` appends one row to `suite-receipts.jsonl` in the repo's common git dir, which every worktree of the repo
shares: the tree, HEAD, the time, the run's exit code and scope, and the test and failed-file counts read from
<summary> (the JSON file tests/parallel_tests.py writes). It writes nothing and exits 2 when the work tree no longer
hashes to <tree>, since the run then did not test one tree, or when <summary> is missing or unreadable.

`check` decides whether <branch> needs a suite run before it merges into <base> (default `master`):
  exit 0, `skip: ...`   <branch> fast-forwards <base>, and the latest receipt for <branch>'s tree is a green run
  exit 1, `rerun: ...`  <branch> does not fast-forward <base> (trial-merge it and run the suite on the result), or
                        no receipt names its tree, or the latest one on that tree failed
  exit 2                a git call failed or a receipt row is not JSON; the message is on stderr
"""
import argparse
import datetime
import json
import os
import pathlib
import subprocess
import sys
import tempfile

RECEIPTS_FILE = "suite-receipts.jsonl"
EXIT_SKIP = 0
EXIT_RERUN = 1
EXIT_FAILED = 2


class ReceiptError(Exception):
    """A git call or a receipt file could not give its answer."""


def receipt_git(repo, *args, env=None):
    """Standard output of `git <args>` in repo without its trailing newline; raise ReceiptError when git fails."""
    try:
        finished = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, env=env,
                                  stdin=subprocess.DEVNULL)
    except OSError as error:
        raise ReceiptError(f"cannot run git: {error}") from error
    if finished.returncode != 0:
        raise ReceiptError(f"git {' '.join(args)} failed in {repo}: {finished.stderr.strip()}")
    return finished.stdout.rstrip("\n")


def work_tree_hash(repo):
    """The tree hash of the work tree as it stands, ignored files left out, built in a temporary index so the repo's
    own index stays as it is."""
    top = receipt_git(repo, "rev-parse", "--show-toplevel")
    with tempfile.TemporaryDirectory() as scratch:
        env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        env["GIT_INDEX_FILE"] = str(pathlib.Path(scratch) / "index")
        # An unborn branch has no HEAD tree to start from; the empty index then takes every file from `add`.
        if git_succeeds(top, "rev-parse", "--verify", "--quiet", "HEAD"):
            receipt_git(top, "read-tree", "HEAD", env=env)
        receipt_git(top, "add", "--all", env=env)
        return receipt_git(top, "write-tree", env=env)


def git_succeeds(repo, *args):
    """True when `git <args>` exits 0 in repo."""
    finished = subprocess.run(["git", *args], cwd=repo, capture_output=True, stdin=subprocess.DEVNULL)
    return finished.returncode == 0


def suite_receipts_file(repo):
    """The receipts file in the common git dir of repo, shared by all of its worktrees."""
    common_dir = receipt_git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    return pathlib.Path(common_dir) / RECEIPTS_FILE


def read_summary(summary_file):
    """(tests, failed files) from the summary JSON tests/parallel_tests.py wrote."""
    try:
        summary = json.loads(pathlib.Path(summary_file).read_text())
    except (OSError, ValueError) as error:
        raise ReceiptError(f"no test summary at {summary_file}: {error}") from error
    return summary["tests"], len(summary["failed_files"])


def command_record(repo, start_tree, exit_code, scope, summary_file):
    end_tree = work_tree_hash(repo)
    if end_tree != start_tree:
        raise ReceiptError(f"the work tree changed during the run ({start_tree} -> {end_tree}); no receipt written")
    tests, failed = read_summary(summary_file)
    head = None
    if git_succeeds(repo, "rev-parse", "--verify", "--quiet", "HEAD"):
        head = receipt_git(repo, "rev-parse", "HEAD")
    row = {
        "tree": end_tree,
        "head": head,
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "exit": exit_code,
        "scope": scope,
        "tests": tests,
        "failed": failed,
    }
    path = suite_receipts_file(repo)
    with path.open("a") as receipts:
        receipts.write(json.dumps(row) + "\n")


def latest_suite_receipt(repo, tree):
    """The last row in the receipts file for `tree`, or None when no row names it."""
    path = suite_receipts_file(repo)
    if not path.exists():
        return None
    found = None
    for number, line in enumerate(path.read_text().splitlines(), start=1):
        try:
            row = json.loads(line)
        except ValueError as error:
            raise ReceiptError(f"{path}:{number} is not a JSON receipt row: {error}") from error
        if row.get("tree") == tree:
            found = row
    return found


def is_green(row):
    """True when the receipt row is a passing run that ran at least one test."""
    return row["exit"] == 0 and row["failed"] == 0 and row["tests"] > 0


def check(repo, branch, base):
    """(exit code, message) for whether `branch` needs a suite run before it merges into `base`."""
    branch_tree = receipt_git(repo, "rev-parse", f"{branch}^{{tree}}")
    if not git_succeeds(repo, "merge-base", "--is-ancestor", base, branch):
        return EXIT_RERUN, (f"rerun: {branch} does not fast-forward {base}; "
                            "trial-merge it and run the suite on the result")
    row = latest_suite_receipt(repo, branch_tree)
    if row is None:
        return EXIT_RERUN, f"rerun: no suite run is recorded on the tree of {branch} ({branch_tree[:12]})"
    if not is_green(row):
        return EXIT_RERUN, (f"rerun: the last suite run on the tree of {branch} failed "
                            f"(exit {row['exit']}, {row['failed']} failed files, {row['ts']})")
    return EXIT_SKIP, (f"skip: the suite ran green on the tree of {branch} "
                       f"({row['tests']} tests, scope {row['scope']}, {row['ts']}) and it fast-forwards {base}")


def parse_command_line(argv):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-h", "--help", action="store_true")
    verbs = parser.add_subparsers(dest="verb")
    tree_verb = verbs.add_parser("tree")
    tree_verb.add_argument("repo")
    record_verb = verbs.add_parser("record")
    record_verb.add_argument("repo")
    record_verb.add_argument("--tree", required=True)
    record_verb.add_argument("--exit", type=int, required=True, dest="exit_code")
    record_verb.add_argument("--scope", required=True)
    record_verb.add_argument("--summary", required=True)
    check_verb = verbs.add_parser("check")
    check_verb.add_argument("repo")
    check_verb.add_argument("branch")
    check_verb.add_argument("--base", default="master")
    return parser.parse_args(argv)


def main(argv):
    args = parse_command_line(argv)
    if args.help or args.verb is None:
        print(__doc__)
        return 0 if args.help else EXIT_FAILED
    try:
        if args.verb == "tree":
            print(work_tree_hash(args.repo))
            return 0
        if args.verb == "record":
            command_record(args.repo, args.tree, args.exit_code, args.scope, args.summary)
            return 0
        code, message = check(args.repo, args.branch, args.base)
    except ReceiptError as error:
        print(f"suite_receipt: {error}", file=sys.stderr)
        return EXIT_FAILED
    print(message)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
