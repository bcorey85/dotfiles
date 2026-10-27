#!/usr/bin/env python3
"""ledger_deferred.py: print the deferred-findings queue of the current repo and branch (`ledger yield --deferred`).

Waits while the ledger cache is behind its shards, the same way every ledger read does. Exit codes: 0 when the queue was
printed or the ledger is not installed, 75 when the ledger stayed busy (the output says what to run), and the ledger's
own code when it fails."""
import pathlib
import sys

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent.parent / "lib")]
import script_utils


def main():
    try:
        done = script_utils.read_ledger(["yield", "--deferred"])
    except script_utils.LedgerNotInstalledError:
        print("deferred: not tracked (ledger not installed)")
        return 0
    except script_utils.LedgerBusyError as error:
        script = pathlib.Path(__file__).resolve()
        print(f"deferred: not read ({error}). Run `ledger worker --once`, then `{script}` to read the queue.")
        return script_utils.LEDGER_BUSY_EXIT

    if done.returncode != 0:
        print(done.stderr, end="", file=sys.stderr)
        print(f"deferred: not read ({script_utils.ledger_failure_reason(done)})")
        return done.returncode

    print(done.stdout, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
