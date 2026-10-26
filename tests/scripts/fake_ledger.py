"""A stand-in `ledger` binary for tests of the scripts that write to the ledger.

`install(directory)` plants an executable `ledger` under `directory` and returns the environment
entries that put it first on PATH. It records what the scripts send and answers the one reader
the verify scripts call:

  ledger write <type> [--session <id>] [--ts <time>]
                                         appends the stdin JSON object to the rows file as one line,
                                         with `_type`, `_cwd` and, when given, `_session` and `_ts` added
  ledger yield --review-trees            prints `tree`, then the `tree` of each recorded review_run
                                         of the code-reviewer at branch-exit with source verify-branch
                                         and a tree, whose `branch_key` is the cwd's current branch
  anything else                          exits 64

`ledger write` records nothing and exits with the code in FAKE_LEDGER_WRITE_EXIT when that is set
to a nonzero number.

`path_without_ledger(path)` returns `path` with every directory that holds a `ledger` left out.

The real writer keys the branch before it stores it; this stand-in compares the raw branch the
scripts send, which is the same value the real one is given.
"""
import json
import os
import pathlib

LEDGER_SOURCE = '''#!/usr/bin/env python3
import json
import os
import subprocess
import sys

rowsPath = os.environ["FAKE_LEDGER_ROWS"]
args = sys.argv[1:]


def recordedRows():
    if not os.path.isfile(rowsPath):
        return []
    with open(rowsPath) as handle:
        return [json.loads(line) for line in handle if line.strip()]


if len(args) >= 2 and args[0] == "write":
    writeExit = int(os.environ.get("FAKE_LEDGER_WRITE_EXIT", "0"))
    if writeExit != 0:
        sys.stdin.read()
        sys.exit(writeExit)
    row = json.loads(sys.stdin.read())
    row["_type"] = args[1]
    row["_cwd"] = os.getcwd()
    if "--session" in args:
        row["_session"] = args[args.index("--session") + 1]
    if "--ts" in args:
        row["_ts"] = args[args.index("--ts") + 1]
    with open(rowsPath, "a") as handle:
        handle.write(json.dumps(row) + "\\n")
    sys.exit(0)

if args == ["yield", "--review-trees"]:
    branch = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True).stdout.strip()
    print("tree")
    for row in recordedRows():
        isBranchReview = (row["_type"] == "review_run" and row.get("gate") == "code-reviewer"
                          and row.get("scope") == "branch-exit" and row.get("source") == "verify-branch"
                          and row.get("tree") and row.get("branch_key") == branch)
        if isBranchReview:
            print(row["tree"])
    sys.exit(0)

sys.exit(64)
'''


def install(directory):
    """Plant the stand-in under `directory`; return the env entries that put it first on PATH."""
    bin_directory = pathlib.Path(directory) / "fake-ledger-bin"
    bin_directory.mkdir(parents=True, exist_ok=True)
    ledger = bin_directory / "ledger"
    ledger.write_text(LEDGER_SOURCE)
    ledger.chmod(0o755)
    return {
        "PATH": f"{bin_directory}{os.pathsep}{os.environ['PATH']}",
        "FAKE_LEDGER_ROWS": str(pathlib.Path(directory) / "fake-ledger-rows.jsonl"),
    }


def path_without_ledger(path):
    """`path`, a PATH string, without the directories that hold a `ledger` (the stand-in's included)."""
    return os.pathsep.join(part for part in path.split(os.pathsep) if not os.path.exists(os.path.join(part, "ledger")))


def recorded_rows(env, row_type=None):
    """The rows the stand-in recorded, oldest first; only those of `row_type` when given."""
    rows_path = pathlib.Path(env["FAKE_LEDGER_ROWS"])
    if not rows_path.is_file():
        return []
    rows = [json.loads(line) for line in rows_path.read_text().splitlines() if line.strip()]
    return [row for row in rows if row_type is None or row["_type"] == row_type]
