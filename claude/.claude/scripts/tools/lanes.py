#!/usr/bin/env python3
"""lanes.py: the command line of the lane file. JSON on stdout.

Usage: lanes.py add --name N --worktree W --main-checkout M --branch B [--reports-to R]
                     [--base-commit C]   (brief on stdin)
       lanes.py set-session N ID [--brief-stdin]     (new brief on stdin)
       lanes.py remove N                             (prints the removed entry)
       lanes.py get N | get --containing PATH        ({"entry": {...} or null})
       lanes.py path N                               ({"file": "<lane file of N>"}; N need not have an entry)
       lanes.py list                                 ({"lanes": [...]})
       lanes.py check [FILE...]                      (default: every lane file)

Exit 1: a live entry exists on add; no entry on set-session or remove. Exit 2: a bad lane file, a lock held too
long, an unwritable state folder, a file that cannot be written or a usage error, named on stderr."""
import argparse
import json
import pathlib
import sys

LIB_DIR = pathlib.Path(__file__).resolve().parents[1] / "lib"
sys.path.insert(0, str(LIB_DIR))
import file_lock
import lane_entries


def build_parser():
    parser = argparse.ArgumentParser(prog="lanes", description=__doc__.splitlines()[0])
    verbs = parser.add_subparsers(dest="verb", required=True)

    add = verbs.add_parser("add", help="write a new entry; the brief is read from stdin")
    add.add_argument("--name", required=True)
    add.add_argument("--worktree", required=True)
    add.add_argument("--main-checkout", required=True)
    add.add_argument("--branch", required=True)
    add.add_argument("--reports-to", default="")
    add.add_argument("--base-commit", default=None, help="the commit the lane branch starts from")

    set_session = verbs.add_parser("set-session", help="set the session id of an entry")
    set_session.add_argument("name")
    set_session.add_argument("session_id")
    set_session.add_argument("--brief-stdin", action="store_true", help="replace the brief with stdin")

    remove = verbs.add_parser("remove", help="delete an entry and print it")
    remove.add_argument("name")

    get = verbs.add_parser("get", help="print one entry, or null")
    get.add_argument("name", nargs="?")
    get.add_argument("--containing", metavar="PATH", help="the entry whose worktree holds PATH")

    path = verbs.add_parser("path", help="print the lane file of a name, whether or not it exists")
    path.add_argument("name")

    verbs.add_parser("list", help="print every entry, sorted by name")

    check = verbs.add_parser("check", help="validate lane files; exit 2 on the first bad one")
    check.add_argument("files", nargs="*")
    return parser


def print_json(value):
    print(json.dumps(value))


def read_brief_from_stdin():
    return sys.stdin.read().rstrip("\n")


def run_add(args):
    brief = read_brief_from_stdin()
    try:
        lane = lane_entries.add_entry(args.name, args.worktree, args.main_checkout, args.branch, brief,
                                      args.reports_to, args.base_commit)
    except lane_entries.LaneExistsError as error:
        print(f"lanes: {error}", file=sys.stderr)
        return 1
    print_json(lane)
    return 0


def run_set_session(args):
    brief = read_brief_from_stdin() if args.brief_stdin else None
    changed = lane_entries.set_session(args.name, args.session_id, brief)
    print_json({"changed": changed})
    return 0


def run_remove(args):
    print_json(lane_entries.remove_entry(args.name))
    return 0


def run_get(args, parser):
    if bool(args.name) == bool(args.containing):
        parser.error("get takes a name or --containing PATH, not both and not neither")
    if args.containing:
        print_json({"entry": lane_entries.entry_containing(args.containing)})
        return 0
    print_json({"entry": lane_entries.entry(args.name)})
    return 0


def run_path(args):
    print_json({"file": str(lane_entries.lane_file(args.name))})
    return 0


def run_list(args):
    print_json({"lanes": lane_entries.all_entries()})
    return 0


def run_check(args):
    if args.files:
        for file in args.files:
            lane_entries.read_named_entry(file)
        print_json({"checked": len(args.files)})
        return 0
    entries = lane_entries.all_entries()
    print_json({"checked": len(entries)})
    return 0


def dispatch(args, parser):
    if args.verb == "get":
        return run_get(args, parser)
    runners = {"add": run_add, "set-session": run_set_session, "remove": run_remove, "path": run_path,
               "list": run_list, "check": run_check}
    return runners[args.verb](args)


def os_error_subject(args):
    """`<lane file>: ` for a verb that names one lane, so an OS error says which file it hit; else empty."""
    name = getattr(args, "name", None)
    if not name:
        return ""
    try:
        return f"{lane_entries.lane_file(name)}: "
    except lane_entries.LaneFileError:
        return ""


def main(argv):
    parser = build_parser()
    args = parser.parse_args(argv[1:])
    try:
        return dispatch(args, parser)
    except lane_entries.LaneNotFoundError as error:
        print(f"lanes: {error}", file=sys.stderr)
        return 1
    except lane_entries.LaneFileError as error:
        print(f"lanes: {error}", file=sys.stderr)
        return 2
    except file_lock.LockTimeoutError:
        print(f"lanes: {os_error_subject(args)}lock {lane_entries.lane_lock_path()} held for "
              f"{lane_entries.LOCK_TIMEOUT_SECONDS}s", file=sys.stderr)
        return 2
    except OSError as error:
        print(f"lanes: {os_error_subject(args)}{error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
