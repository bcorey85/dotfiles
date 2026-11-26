#!/usr/bin/env python3
"""memory_sample.py: append one line to a rotating memory log: the time, the GB of memory available, and the 15
biggest holders of resident memory, summed by command name and by herdr workspace.

Usage: memory_sample.py

The log is `${XDG_STATE_HOME:-~/.local/state}/memory-sample/samples.jsonl`. A file over 5 MB moves to
`samples.jsonl.1` (the older copy is replaced) before the next line is written. A line is
  {"time": <UTC ISO>, "mem_available_gb": <number or null>,
   "by_command": [{"command", "rss_kb", "count"}], "by_workspace": [{"workspace", "rss_kb"}]}
and a process with no workspace is summed under workspace "". `install/memory-sample` runs it every minute.
Exit 0, or 1 when the process table cannot be read (the message is on stderr)."""
import datetime
import operator
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import process_table
import script_utils
import system_resources

TOP_HOLDERS = 15
ROTATE_BYTES = 5 * 1024 * 1024
STATE_FOLDER = "memory-sample"
LOG_NAME = "samples"
LOG_SUFFIX = ".jsonl"


def samples_path():
    state_dir = script_utils.xdg_state_home() / STATE_FOLDER
    return script_utils.state_file_path(state_dir, LOG_NAME, LOG_SUFFIX)


def summed(rows, key):
    """{key(row): (kilobytes, count)} over the rows."""
    totals = {}
    for row in rows:
        name = key(row)
        kilobytes, count = totals.get(name, (0, 0))
        totals[name] = (kilobytes + row.rss_bytes // 1024, count + 1)
    return totals


def by_command(rows):
    totals = summed(rows, lambda row: row.command)
    largest = script_utils.largest_entries(totals, TOP_HOLDERS, operator.itemgetter(0))
    return [{"command": command, "rss_kb": kilobytes, "count": count} for command, (kilobytes, count) in largest]


def by_workspace(rows):
    totals = summed(rows, lambda row: row.workspace or "")
    return [{"workspace": workspace, "rss_kb": kilobytes}
            for workspace, (kilobytes, _) in script_utils.largest_entries(totals, TOP_HOLDERS, operator.itemgetter(0))]


def sample_line(rows):
    now = datetime.datetime.now(datetime.timezone.utc)
    return {"time": now.isoformat(timespec="seconds"), "mem_available_gb": system_resources.memory_available_gb(),
            "by_command": by_command(rows), "by_workspace": by_workspace(rows)}


def rotate_when_big(path):
    if path.exists() and path.stat().st_size > ROTATE_BYTES:
        os.replace(path, path.with_name(path.name + ".1"))


def main():
    try:
        rows = process_table.read_table()
    except process_table.ProcessTableError as error:
        print(f"memory_sample: {error}", file=sys.stderr)
        return 1

    path = samples_path()
    rotate_when_big(path)
    script_utils.append_jsonl(path, sample_line(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
