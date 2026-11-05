#!/usr/bin/env python3
"""ledger_deferred.py: print the deferred-findings queue of the current repo and branch (`ledger yield --deferred`).

Waits while the ledger cache is behind its shards, the same way every ledger read does. When it stays behind, runs
`ledger worker --once` itself and reads once more, with one try and no wait. Exit codes: 0 when the queue was printed
or the ledger is not installed, 75 when the ledger stayed busy or the worker failed (the output says the worker ran),
and the ledger's own code when it fails."""
import pathlib
import subprocess
import sys

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent.parent / "lib")]
import script_utils

READ_ARGS = ["yield", "--deferred"]
WORKER_TIMEOUT_SECONDS = 120


def run_worker_once():
    """Run `ledger worker --once` to bring the cache up to date. Returns None when it finished with exit 0, else the
    reason it did not."""
    ledger = script_utils.ledger_bin()
    try:
        worker = subprocess.run([ledger, "worker", "--once"], capture_output=True, text=True,
                                errors="replace", timeout=WORKER_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        return f"ledger worker --once: no answer within {WORKER_TIMEOUT_SECONDS} s"
    if worker.returncode != 0:
        return f"ledger worker --once: {script_utils.ledger_failure_reason(worker)}"
    return None


def read_after_worker(first_error):
    """Run the worker once after a busy read, then read once more. Returns (done, None) on an answer, or
    (None, reason) when the worker failed or the ledger is still busy; the reason names that the worker ran."""
    worker_problem = run_worker_once()
    if worker_problem:
        return None, f"{first_error}; the worker ran and failed: {worker_problem}"
    try:
        return script_utils.read_ledger(READ_ARGS, wait_seconds=0), None
    except script_utils.LedgerBusyError as error:
        return None, f"{first_error}; {error}; the worker already ran"


def main():
    try:
        done = script_utils.read_ledger(READ_ARGS)
    except script_utils.LedgerNotInstalledError:
        print("deferred: not tracked (ledger not installed)")
        return 0
    except script_utils.LedgerBusyError as first_error:
        done, reason = read_after_worker(first_error)
        if done is None:
            print(f"deferred: not read ({reason})")
            return script_utils.LEDGER_BUSY_EXIT

    if done.returncode != 0:
        print(done.stderr, end="", file=sys.stderr)
        print(f"deferred: not read ({script_utils.ledger_failure_reason(done)})")
        return done.returncode

    print(done.stdout, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
