"""Exit 1 when a branch diff or the work tree touches a path outside the bounds a close pass may edit.

Usage: python3 branch_bounds.py <base-sha> <head-sha>
Exit 0: every path is inside the bounds. Exit 1: offending paths listed on stdout.
Exit 2: a bad argument or a sha git cannot resolve.
"""
import subprocess
import sys

OFFENDING_PREFIXES = (
    "claude/.claude/scripts/review/",
    "claude/.claude/scripts/gates/",
)
OFFENDING_PATHS = (
    "claude/.claude/scripts/code/plan_check.py",
    "claude/.claude/settings.json",
)
OFFENDING_BASENAMES = ("CLAUDE.md", "orchestration.md")
VERIFY_PREP_PATH = "claude/.claude/scripts/review/verify-prep"

EXIT_OK = 0
EXIT_OUT_OF_BOUNDS = 1
EXIT_BAD_INPUT = 2


class BadInputError(Exception):
    """A usage error or a sha git cannot resolve."""


def run_git(args):
    """Run git in the current folder and return its stdout; raise BadInputError on a non-zero exit."""
    result = subprocess.run(["git", *args], capture_output=True, text=True)
    if result.returncode != 0:
        command = " ".join(args)
        raise BadInputError(f"git {command} failed: {result.stderr.strip()}")
    return result.stdout


def check_sha(sha):
    """Raise BadInputError unless `sha` names a commit."""
    run_git(["rev-parse", "--verify", "--quiet", sha + "^{commit}"])


def diff_paths(base, head):
    """Paths the head side changed since its merge base with base, so a commit only base has is not counted."""
    output = run_git(["diff", "--name-only", "-z", base + "..." + head])
    return [path for path in output.split("\0") if path]


def work_tree_paths():
    """Paths the work tree changes, untracked files listed one by one; a rename lists both names."""
    output = run_git(["status", "--porcelain", "--untracked-files=all", "-z"])
    entries = output.split("\0")
    paths = []
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if len(entry) < 4:
            continue
        paths.append(entry[3:])
        is_rename_or_copy = entry[0] in "RC" or entry[1] in "RC"
        if is_rename_or_copy and index < len(entries):
            paths.append(entries[index])
            index += 1
    return paths


def is_offending(path):
    """Whether `path` lies outside the bounds."""
    if path.startswith(OFFENDING_PREFIXES):
        return True
    if path in OFFENDING_PATHS:
        return True
    basename = path.rsplit("/", 1)[-1]
    return basename in OFFENDING_BASENAMES


def offending_paths(paths):
    """The sorted, unique offending paths among `paths`."""
    return sorted({path for path in paths if is_offending(path)})


def report(offenders):
    """Print each offending path; name verify-prep when it is among them."""
    print("Paths outside the close-pass bounds:")
    for path in offenders:
        print("  " + path)
    if VERIFY_PREP_PATH in offenders:
        print(f"{VERIFY_PREP_PATH} is off limits.")


def main(argv):
    if len(argv) != 2:
        print("usage: branch_bounds.py <base-sha> <head-sha>", file=sys.stderr)
        return EXIT_BAD_INPUT
    base, head = argv
    try:
        check_sha(base)
        check_sha(head)
        paths = diff_paths(base, head) + work_tree_paths()
    except BadInputError as error:
        print(f"branch_bounds: {error}", file=sys.stderr)
        return EXIT_BAD_INPUT
    offenders = offending_paths(paths)
    if not offenders:
        return EXIT_OK
    report(offenders)
    return EXIT_OUT_OF_BOUNDS


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
