#!/usr/bin/env python3
"""accepted_failures.py: failing test lines a person accepted as already failing before the diff.

    python3 accepted_failures.py accept --repo <repo> --line <failing line> --by <who> --reason <text>
    python3 accepted_failures.py list --repo <repo>

The review loop's scoped test run passes a red command whose failing lines also fail on HEAD without the diff. A
failure whose line differs between the two runs only in a number or a timestamp (a throttled call's 429 line) reads as
new, so the loop stops. An accepted row names such a line: full_check.is_pre_existing then compares that line (the
numbers of its reason only), the detail lines of each failing block with that line, and the new log lines under that
test's `___ name ___` header or under no header, with their numbers masked. The detail lines of every other failing
block, and the log lines under any other test's header, stay exact. With no row naming a failing line, every
comparison is exact, and a new failing test stays a blocker. Rows are kept in the repo's git dir, one JSON object per
line.
Exit 0 when done, 2 when `accept` is refused (an empty field, a line that is not a failing line, no git dir, or a
stored line that is not a JSON object). `list` exits 2 for a stored line that is not a JSON object."""
import argparse
import json
import pathlib
import shlex
import sys

SCRIPT_PATH = pathlib.Path(__file__).resolve()
sys.path[:0] = [str(SCRIPT_PATH.parent / folder) for folder in (".", "../lib")]
import full_check
import script_utils

ACCEPTED_FAILURES_FILE = "accepted-failures.jsonl"
ROW_FIELDS = ("line", "by", "reason")


def store_path(repo):
    """The rows file inside the git dir of `repo`; None when git cannot say where that is."""
    return script_utils.git_path(repo, ACCEPTED_FAILURES_FILE)


class AcceptRefusedError(ValueError):
    """An accept call or a stored row the store cannot take."""


def read_rows(repo):
    """The accepted rows of the repo, oldest first; none when the store holds none or git cannot place it. Raises
    AcceptRefusedError, naming the file and the line, for a line that is not a JSON object: a torn line must not
    vanish from the next write."""
    path = store_path(repo)
    if path is None or not path.exists():
        return []

    rows = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for number, line in enumerate(text.splitlines(), start=1):
        try:
            row = json.loads(line)
        except ValueError as error:
            message = f"{path}:{number}: not JSON ({error}); expected one JSON object per line"
            raise AcceptRefusedError(message) from error
        if not isinstance(row, dict):
            raise AcceptRefusedError(f"{path}:{number}: not a JSON object; expected one JSON object per line")
        rows.append(row)
    return rows


def accepted_lines(repo):
    """The failing lines the accepted rows name. Raises AcceptRefusedError for a row whose `line` is not a string."""
    lines = []
    for row in read_rows(repo):
        if not isinstance(row.get("line"), str):
            raise AcceptRefusedError(f"{store_path(repo)}: row has no string `line`: {json.dumps(row)}")
        lines.append(row["line"])
    return lines


def accept(repo, line, by, reason):
    """Add one row, written with the whole file in one atomic step. Returns the row. Raises AcceptRefusedError for an
    empty field, a line that is not a failing line, or when git cannot place the store."""
    row = {"line": line.strip(), "by": by.strip(), "reason": reason.strip()}
    empty = [field for field in ROW_FIELDS if not row[field]]
    if empty:
        raise AcceptRefusedError(f"empty field: {', '.join(empty)}")

    if not is_acceptable_line(row["line"]):
        raise AcceptRefusedError(f"not a failing line: {row['line']!r}; expected a line such as "
                                 "`FAILED <test> - <reason>` or `ERROR <test> - <reason>`")

    path = store_path(repo)
    if path is None:
        raise AcceptRefusedError(f"cannot find the git dir of {repo}")

    rows = [*read_rows(repo), row]
    script_utils.write_text_atomically(path, "".join(json.dumps(each) + "\n" for each in rows))
    return row


def is_acceptable_line(line):
    """True when `accept` takes the line: it is a failing line on its own."""
    return bool(full_check.failing_step_lines([line]))


def failing_lines_of(output):
    """The failing lines of one command's output that `accept` takes, in order, each once."""
    lines = full_check.failing_step_lines(output.splitlines())
    return list(dict.fromkeys(line.strip() for line in lines if is_acceptable_line(line)))


def accept_command_text(repo, failing_lines):
    """The accept command for each failing line, one per line, with the reason and the person left to fill."""
    commands = []
    for line in failing_lines:
        commands.append(f"python3 {shlex.quote(str(SCRIPT_PATH))} accept --repo {shlex.quote(str(repo))} "
                        f"--line {shlex.quote(line)} --by '<who>' --reason '<why it fails without the diff>'")
    return "\n".join(commands)


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    accept_parser = commands.add_parser("accept")
    accept_parser.add_argument("--repo", required=True)
    accept_parser.add_argument("--line", required=True)
    accept_parser.add_argument("--by", required=True)
    accept_parser.add_argument("--reason", required=True)
    list_parser = commands.add_parser("list")
    list_parser.add_argument("--repo", required=True)
    args = parser.parse_args(argv)

    if args.command == "list":
        try:
            rows = read_rows(args.repo)
        except AcceptRefusedError as error:
            print(f"accepted_failures: refused: {error}", file=sys.stderr)
            return 2
        for row in rows:
            print(json.dumps(row))
        return 0

    try:
        row = accept(args.repo, args.line, args.by, args.reason)
    except AcceptRefusedError as error:
        print(f"accepted_failures: refused: {error}", file=sys.stderr)
        return 2
    print(f"accepted: {row['line']} (by {row['by']})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
