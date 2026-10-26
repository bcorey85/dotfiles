"""Check that every earlier plan-review round left its reviewer reports in the task directory.

Usage: plan_review_reports.py check <task-dir> <round>

Round 1 needs nothing. Round N (N >= 2) needs, for each round 1..N-1, at least one non-empty
`review-round<k>-shard-<x>.md` file. Exit 0 when they are all there; otherwise print the missing round and the expected
file name and exit 1."""
import pathlib
import sys


def report_files(task_dir, review_round):
    """The non-empty report files one round wrote, sorted by name."""
    found = pathlib.Path(task_dir).glob(f"review-round{review_round}-shard-*.md")
    return sorted(path for path in found if path.is_file() and path.stat().st_size > 0)


def missing_rounds(task_dir, review_round):
    """The earlier rounds that have no report file."""
    return [prior for prior in range(1, review_round) if not report_files(task_dir, prior)]


def main(argv):
    if len(argv) != 4 or argv[1] != "check" or not argv[3].isdigit():
        print(__doc__, file=sys.stderr)
        return 2
    task_dir, review_round = argv[2], int(argv[3])
    missing = missing_rounds(task_dir, review_round)
    for prior in missing:
        print(f"{task_dir}: round {prior} has no report file; expected review-round{prior}-shard-<x>.md. "
              f"Write each reviewer's hand-back there before round {review_round}.")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
