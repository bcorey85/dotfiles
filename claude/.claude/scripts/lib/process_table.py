"""process_table.py: one row per running process: pid, resident memory, command name, working folder and the
HERDR_WORKSPACE_ID of its environment.

Linux reads /proc (a field the user may not read stays None: an environment of another user's process, a kernel
thread's memory is skipped). macOS reads `ps -axo pid=,rss=,comm=` and has no workspace and no working folder. The
environment variable named by TABLE_FILE_VARIABLE points at a JSON file holding rows
`{pid, rss_kb, command, workspace, cwd}` that stands in for the real table, for tests. Knows no toolkit rule."""
import json
import os
import pathlib
import sys
from typing import NamedTuple

import script_utils

TABLE_FILE_VARIABLE = "PROCESS_TABLE_FILE"
WORKSPACE_VARIABLE = "HERDR_WORKSPACE_ID"
PROC_FOLDER = "/proc"
PS_ARGV = ["ps", "-axo", "pid=,rss=,comm="]


class ProcessTableError(Exception):
    """The table could not be read or is not in the expected shape; the message names the source."""


class ProcessRow(NamedTuple):
    pid: int
    rss_bytes: int
    command: str
    workspace: str | None
    cwd: str | None


def parse_fake_row(row, source):
    """A ProcessRow from one fake-table row. Raises ProcessTableError naming `source` for a row of another shape."""
    if not isinstance(row, dict) or not script_utils.is_int(row.get("pid")) \
            or not script_utils.is_int(row.get("rss_kb")) or not isinstance(row.get("command"), str):
        raise ProcessTableError(f"{source}: a row needs an int pid, an int rss_kb and a str command: {row!r}")
    return ProcessRow(row["pid"], row["rss_kb"] * 1024, row["command"], row.get("workspace"), row.get("cwd"))


def read_fake_table(table_file):
    try:
        rows = json.loads(pathlib.Path(table_file).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ProcessTableError(f"{table_file}: cannot read the fake process table: {error}") from error
    if not isinstance(rows, list):
        raise ProcessTableError(f"{table_file}: expected a JSON list of rows")
    return [parse_fake_row(row, table_file) for row in rows]


def status_fields(process_folder):
    """(command name, resident KB) from /proc/<pid>/status, or None for a kernel thread or a vanished process."""
    try:
        text = (process_folder / "status").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    name = None
    kilobytes = None
    for line in text.splitlines():
        if line.startswith("Name:"):
            name = line.removeprefix("Name:").strip()
        elif line.startswith("VmRSS:"):
            kilobytes = int(line.split()[1])
    if name is None or kilobytes is None:
        return None
    return name, kilobytes


def workspace_of(process_folder):
    """HERDR_WORKSPACE_ID from /proc/<pid>/environ, or None when unset or the file is not readable."""
    try:
        data = (process_folder / "environ").read_bytes()
    except OSError:
        return None
    prefix = f"{WORKSPACE_VARIABLE}=".encode()
    for entry in data.split(b"\0"):
        if entry.startswith(prefix):
            return entry[len(prefix):].decode("utf-8", errors="replace")
    return None


def cwd_of(process_folder):
    try:
        return os.readlink(process_folder / "cwd")
    except OSError:
        return None


def read_proc_table():
    rows = []
    for process_folder in pathlib.Path(PROC_FOLDER).iterdir():
        if not process_folder.name.isdigit():
            continue
        fields = status_fields(process_folder)
        if fields is None:
            continue
        name, kilobytes = fields
        rows.append(ProcessRow(int(process_folder.name), kilobytes * 1024, name, workspace_of(process_folder),
                               cwd_of(process_folder)))
    return rows


def read_ps_table():
    finished = script_utils.run_or_raise(PS_ARGV, ProcessTableError, check=True)
    rows = []
    for line in finished.stdout.splitlines():
        words = line.split(None, 2)
        if len(words) != 3 or not words[0].isdigit() or not words[1].isdigit():
            raise ProcessTableError(f"{' '.join(PS_ARGV)}: unexpected line {line!r}")
        rows.append(ProcessRow(int(words[0]), int(words[1]) * 1024, os.path.basename(words[2]), None, None))
    return rows


def read_table():
    """The ProcessRow list: the fake table when TABLE_FILE_VARIABLE is set, else this system's. Raises
    ProcessTableError."""
    table_file = os.environ.get(TABLE_FILE_VARIABLE)
    if table_file:
        return read_fake_table(table_file)
    if sys.platform.startswith("linux"):
        return read_proc_table()
    if sys.platform == "darwin":
        return read_ps_table()
    raise ProcessTableError(f"no process table reader for {sys.platform}")
