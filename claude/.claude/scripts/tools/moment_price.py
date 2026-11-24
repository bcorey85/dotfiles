#!/usr/bin/env python3
"""moment_price.py: price one hillclimb moment, a block range of one session, as one line.

  moment_price.py price <export.md> <first>-<last> [--json]    (`<n>` alone names one block)
  moment_price.py price --session <id> --since <ts> --until <ts> [--json]
  moment_price.py check <export.md>

Both sources parse into one list of Call records, and price_calls is the only function that sums them. A file that
does not parse, a range outside the file, a window with no rows, and a ledger that cannot be read all stop with a
message and a non-zero exit; none prints a zero price. Exit codes: 0 done, 1 a stop, 2 a bad command line."""
import argparse
import json
import pathlib
import re
import sys
from typing import NamedTuple

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent.parent / "lib")]
import iso_time
import script_utils

SESSION_LINE = re.compile(r"# Session \S+: .+ \(repo: .+\)")
SESSION_FORM = "# Session <id>: <title> (repo: <name>)"
BLOCK_HEADER = re.compile(r"## Block (\d+) · (\d\d):(\d\d) · (\S[^·]*?)(?: · (\d[\d,]*) / (\d[\d,]*) / (\d[\d,]*))?")
BLOCK_FORM = "## Block <N> · <HH:MM> · <who> · <fresh> / <cache read> / <output>  (user: ## Block <N> · <HH:MM> · user)"
WHO_WITH_MODEL = re.compile(r".*\((.+)\)")
SESSION_ID = re.compile(r"[0-9a-f-]+")
RANGE = re.compile(r"(\d+)(?:-(\d+))?")
LEDGER_COLUMNS = ["ts", "model", "input_tokens", "cache_creation_tokens", "cache_read_tokens", "output_tokens"]
SESSION_COLUMN = "session"


class StopError(Exception):
    """A loud stop: the message is printed and the exit code is 1."""


class UsageError(Exception):
    """A bad command line that argparse could not see: reported through parser.error, exit code 2."""


class Call(NamedTuple):
    """One block or one ledger row. A user block has is_call False and no tokens; its time still counts."""
    index: int
    seconds: float
    model: str
    fresh: int
    cache_read: int
    output: int
    is_call: bool


class Price(NamedTuple):
    label: str
    calls: int
    minutes: int
    per_model: dict


def parse_header(line, number, source):
    """The Call for one `## ` line, without its index order check. Stops on a header with a bad shape."""
    match = BLOCK_HEADER.fullmatch(line)
    if match is None:
        raise StopError(f"{source}:{number}: bad block header {line!r}; expected {BLOCK_FORM}")
    index, hours, minutes, who, fresh, cache_read, output = match.groups()
    seconds = (int(hours) * 60 + int(minutes)) * 60
    if int(hours) > 23 or int(minutes) > 59:
        raise StopError(f"{source}:{number}: bad time in {line!r}; expected {BLOCK_FORM}")
    if who == "user":
        if fresh is not None:
            raise StopError(f"{source}:{number}: a user block carries no tokens: {line!r}; expected {BLOCK_FORM}")
        return Call(int(index), seconds, "user", 0, 0, 0, False)
    if fresh is None:
        raise StopError(f"{source}:{number}: block header without tokens {line!r}; expected {BLOCK_FORM}")
    named = WHO_WITH_MODEL.fullmatch(who)
    model = named.group(1) if named else who
    tokens = [int(text.replace(",", "")) for text in (fresh, cache_read, output)]
    return Call(int(index), seconds, model, tokens[0], tokens[1], tokens[2], True)


def parse_export(path):
    """The Call list of an export file, in file order. Stops, naming file and line, on anything off the grammar."""
    lines = pathlib.Path(path).read_text(encoding="utf-8").splitlines()
    if not lines or SESSION_LINE.fullmatch(lines[0]) is None:
        raise StopError(f"{path}:1: missing session line; expected {SESSION_FORM}")

    calls = []
    for number, line in enumerate(lines[1:], start=2):
        if not line.startswith("## "):
            continue
        call = parse_header(line, number, path)
        if calls and call.index <= calls[-1].index:
            raise StopError(f"{path}:{number}: block {call.index} follows block {calls[-1].index}; "
                            f"expected block numbers in increasing order")
        calls.append(call)
    return calls


def select_range(calls, text, source):
    """The calls of an export range `<first>-<last>` or `<n>`. Stops on a bad range or a block not in the file."""
    match = RANGE.fullmatch(text)
    if match is None:
        raise StopError(f"{text!r}: expected a block range <first>-<last> or <n>")
    first = int(match.group(1))
    last = int(match.group(2) or first)
    if first > last:
        raise StopError(f"{text!r}: the first block is after the last; expected <first>-<last> with first <= last")
    chosen = [call for call in calls if first <= call.index <= last]
    present = {call.index for call in chosen}
    for wanted in (first, last):
        if wanted not in present:
            raise StopError(f"{source}: block {wanted} is not in the file (the range {text})")
    return chosen


def parse_timestamp(text):
    """A zone-aware datetime for an ISO timestamp such as 2026-11-22T14:55:42.777Z. Stops on any other form."""
    bad_form = f"{text!r}: expected an ISO timestamp such as 2026-11-22T14:55:42.777Z"
    try:
        return iso_time.parse_zoned_iso_timestamp(text)
    except ValueError:
        raise StopError(bad_form) from None


def ledger_sql(session, since, until):
    """The query for the window. Every quoted value has passed a character check, so none can carry a quote."""
    if SESSION_ID.fullmatch(session) is None:
        raise StopError(f"{session!r}: expected a session id of characters 0-9, a-f and -")
    # The ledger stores `ts` as UTC text with milliseconds. The start rounds up so a row before it stays out.
    since_text = iso_time.utc_millisecond_text(parse_timestamp(since), round_up=True)
    until_text = iso_time.utc_millisecond_text(parse_timestamp(until))
    return (f"select {', '.join(LEDGER_COLUMNS)} from otel_api_request where {SESSION_COLUMN} = '{session}' "
            f"and ts >= '{since_text}' and ts <= '{until_text}' order by ts")


def read_live_calls(session, since, until):
    """The Call list of the ledger's otel_api_request rows in the window. Stops when the ledger cannot be read."""
    sql = ledger_sql(session, since, until)
    command = f'ledger query "{sql}"'
    not_read = f"not read: the otel_api_request rows of session {session}"
    try:
        done = script_utils.read_ledger(["query", sql])
    except script_utils.LedgerUnreadError as error:
        raise StopError(f"{not_read} ({error}); read them with: {command}") from None
    if done.returncode != 0:
        reason = script_utils.ledger_failure_reason(done)
        raise StopError(f"{not_read} ({reason}); read them with: {command}")

    lines = [line for line in done.stdout.splitlines() if line.strip()]
    rows = [line.split("\t") for line in lines[1:]]
    if not rows:
        raise StopError(f"no otel_api_request rows for session {session} between {since} and {until}; "
                        f"check with: {command}")
    return [live_call(number, row, command) for number, row in enumerate(rows, start=1)]


def live_call(number, row, command):
    """One ledger row as a Call; stops when the row does not have the columns the query asked for."""
    if len(row) != len(LEDGER_COLUMNS):
        raise StopError(f"ledger row {number}: {len(row)} columns; expected {','.join(LEDGER_COLUMNS)} from: {command}")
    stamp, model, plain_input, cache_creation, cache_read, output = row
    try:
        tokens = [int(value) for value in (plain_input, cache_creation, cache_read, output)]
    except ValueError:
        raise StopError(f"ledger row {number}: token columns are not whole numbers {row!r}; from: {command}") from None
    try:
        seconds = parse_timestamp(stamp).timestamp()
    except StopError:
        raise StopError(f"ledger row {number}: bad ts {stamp!r}; expected an ISO timestamp; from: {command}") from None
    return Call(number, seconds, model, tokens[0] + tokens[1], tokens[2], tokens[3], True)


def price_calls(calls, label):
    """The only sum: the Price of a list of Call records. Minutes run from the first record's time to the last's,
    user blocks included; a list that runs back in time (a range across midnight) stops."""
    seconds = [call.seconds for call in calls]
    if seconds[-1] < seconds[0]:
        raise StopError(f"{label}: the range runs across midnight; split it at midnight")
    minutes = round((seconds[-1] - seconds[0]) / 60)

    per_model = {}
    for call in calls:
        if not call.is_call:
            continue
        totals = per_model.setdefault(call.model, {"fresh": 0, "cache_read": 0, "output": 0})
        totals["fresh"] += call.fresh
        totals["cache_read"] += call.cache_read
        totals["output"] += call.output
    call_count = sum(1 for call in calls if call.is_call)
    return Price(label, call_count, minutes, per_model)


def model_order(item):
    """Sort key for (model, totals): total tokens, largest first, ties by model name."""
    model, totals = item
    return (-sum(totals.values()), model)


def format_line(price):
    """The output line of a Price."""
    parts = [price.label, f"{price.calls} calls", f"{price.minutes} min"]
    for model, totals in sorted(price.per_model.items(), key=model_order):
        parts.append(f"{model} {totals['fresh']:,} fresh / {totals['cache_read']:,} cache read / "
                     f"{totals['output']:,} output")
    return " · ".join(parts)


def format_json(price):
    return json.dumps({"label": price.label, "calls": price.calls, "minutes": price.minutes,
                       "models": price.per_model}, indent=2)


def block_label(chosen):
    return f"blocks {chosen[0].index}-{chosen[-1].index}"


def run_price_verb(args):
    if args.session:
        if not args.since or not args.until or args.target:
            raise UsageError("price --session <id> --since <ts> --until <ts>")
        calls = read_live_calls(args.session, args.since, args.until)
        label = f"{args.since}..{args.until}"
    else:
        if len(args.target) != 2 or args.since or args.until:
            raise UsageError("price <export.md> <first>-<last>")
        export, range_text = args.target
        calls = select_range(parse_export(export), range_text, export)
        label = block_label(calls)
    price = price_calls(calls, label)
    print(format_json(price) if args.json else format_line(price))


def run_check_verb(args):
    if len(args.target) != 1 or args.session or args.since or args.until or args.json:
        raise UsageError("check <export.md>")
    calls = parse_export(args.target[0])
    print(f"ok: {len(calls)} blocks")


def build_moment_parser():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("verb", choices=["price", "check"])
    parser.add_argument("target", nargs="*")
    parser.add_argument("--session")
    parser.add_argument("--since")
    parser.add_argument("--until")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv):
    parser = build_moment_parser()
    args = parser.parse_args(argv)
    run = run_price_verb if args.verb == "price" else run_check_verb
    try:
        run(args)
    except UsageError as usage:
        parser.error(str(usage))
    except StopError as stop:
        print(f"moment_price {args.verb}: {stop}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
