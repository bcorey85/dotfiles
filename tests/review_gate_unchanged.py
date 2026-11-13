#!/usr/bin/env python3
"""Checks that a suite run leaves no test repo in the real review-gate state folder. Read-only: it reads the folder and
never writes into it.

  review_gate_unchanged.py snapshot   print, as JSON, the repo keys held by each record file in the folder
  review_gate_unchanged.py compare RUN_TMP
                                      read that JSON on stdin, read the folder again; exit 1 and name the file and key
                                      of each key that is new and lies under RUN_TMP, the run's temp folder

A key is the top level of a repo, as reviewed_tree stores it. Files that change, vanish or arrive with only keys
outside RUN_TMP pass.

REVIEW_GATE_CHECK_DIR overrides the folder (default: the folder reviewed_tree.review_gate_dir() names)."""
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "claude" / ".claude" / "scripts" / "lib"))
import reviewed_tree
import script_utils

GATE_FOLDER = pathlib.Path(os.environ.get("REVIEW_GATE_CHECK_DIR") or reviewed_tree.review_gate_dir())
RECORD_NAME_ENDINGS = (reviewed_tree.REVIEWED_SUFFIX, reviewed_tree.BASE_SUFFIX, reviewed_tree.SHARED_REVIEWED_NAME)


def read_keys(folder):
    """Record file name -> sorted repo keys it holds; empty when the folder does not exist."""
    if not folder.is_dir():
        return {}
    keys_by_file = {}
    for entry in sorted(folder.iterdir()):
        if not entry.name.endswith(RECORD_NAME_ENDINGS):
            continue
        keys_by_file[entry.name] = sorted(reviewed_tree.read_json_object(entry))
    return keys_by_file


def new_keys_under(before, after, run_tmp):
    """(file name, key) for each key in `after` that `before` lacks and that lies under `run_tmp`, as given or with
    symlinks resolved."""
    roots = (run_tmp, str(pathlib.Path(run_tmp).resolve()))
    found = []
    for name, keys in sorted(after.items()):
        earlier = set(before.get(name, []))
        found.extend((name, key) for key in keys
                     if key not in earlier and any(script_utils.path_is_under(key, root) for root in roots))
    return found


def main(arguments):
    verb = arguments[0] if arguments else None
    if verb == "snapshot" and len(arguments) == 1:
        print(json.dumps(read_keys(GATE_FOLDER)))
        return 0
    if verb != "compare" or len(arguments) != 2:
        sys.exit(__doc__)
    leaked = new_keys_under(json.load(sys.stdin), read_keys(GATE_FOLDER), arguments[1])
    if not leaked:
        return 0
    print(f"review-gate folder {GATE_FOLDER} gained repos under {arguments[1]} during the suite run:", file=sys.stderr)
    for name, key in leaked:
        print(f"  {name}: {key}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
