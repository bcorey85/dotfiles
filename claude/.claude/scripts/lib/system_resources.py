"""system_resources.py: how much memory is available and how much disk space a folder has or holds, in GB.

Reads /proc/meminfo on Linux and `vm_stat` on macOS, runs `df -Pk` and `du -sk` for folders, and formats a byte
count as KB, MB or GB text (`size_text`). Knows no toolkit rule."""
import os
import pathlib
import re
import sys

import script_utils

KB_PER_GB = 1024 * 1024
BYTES_PER_GB = 1024 ** 3
BYTES_PER_MB = 1024 ** 2
BYTES_PER_KB = 1024
MEMINFO_FILE = "/proc/meminfo"
MEMINFO_AVAILABLE_PATTERN = re.compile(r"^MemAvailable:\s+(\d+)\s+kB\s*$", re.MULTILINE)
VM_STAT_PAGES_PATTERN = re.compile(r"^Pages (free|inactive|speculative):\s+(\d+)\.\s*$", re.MULTILINE)
VM_STAT_KINDS = {"free", "inactive", "speculative"}


class ResourceReadError(Exception):
    """A command failed or printed something unreadable; the message names the call."""


def parse_meminfo_gb(text):
    """GB of `MemAvailable` in /proc/meminfo text, or None when the line is missing."""
    found = MEMINFO_AVAILABLE_PATTERN.search(text)
    if found is None:
        return None
    return int(found.group(1)) / KB_PER_GB


def parse_vm_stat_gb(text, page_size):
    """GB of the free, inactive and speculative pages in `vm_stat` text, or None when one of the three is missing."""
    pages = {kind: int(count) for kind, count in VM_STAT_PAGES_PATTERN.findall(text)}
    if set(pages) != VM_STAT_KINDS:
        return None
    return sum(pages.values()) * page_size / BYTES_PER_GB


def size_text(size):
    """`N.N GB` at or over 1 GiB, `N.N MB` at or over 1 MiB, else `N KB`."""
    if size >= BYTES_PER_GB:
        return f"{size / BYTES_PER_GB:.1f} GB"
    if size >= BYTES_PER_MB:
        return f"{size / BYTES_PER_MB:.1f} MB"
    return f"{size // BYTES_PER_KB} KB"


def _command_output(argv):
    """Stdout of the command, or None when it is missing or exits non-zero."""
    try:
        return _required_output(argv)
    except ResourceReadError:
        return None


def _macos_available_gb():
    vm_stat_text = _command_output(["vm_stat"])
    page_size_text = _command_output(["sysctl", "-n", "hw.pagesize"])
    if vm_stat_text is None or page_size_text is None or not page_size_text.strip().isdigit():
        return None
    return parse_vm_stat_gb(vm_stat_text, int(page_size_text.strip()))


def _linux_available_gb():
    try:
        text = pathlib.Path(MEMINFO_FILE).read_text(encoding="utf-8")
    except OSError:
        return None
    return parse_meminfo_gb(text)


def memory_available_gb():
    """GB of memory available, or None when memory could not be read on this system."""
    if sys.platform.startswith("linux"):
        return _linux_available_gb()
    if sys.platform == "darwin":
        return _macos_available_gb()
    return None


def _required_output(argv, ok_codes=(0,)):
    """Stdout of the command. Raises ResourceReadError naming the call when it is missing or exits with a code
    outside `ok_codes`."""
    return script_utils.run_or_raise(argv, ResourceReadError, check=True, ok_codes=ok_codes).stdout


def free_gb(folder):
    """GB free on the filesystem of the existing `folder`, from `df -Pk`. Raises ResourceReadError when df fails
    or prints no figure."""
    argv = ["df", "-Pk", os.fspath(folder)]
    lines = _required_output(argv).splitlines()
    columns = lines[1].split() if len(lines) > 1 else []
    if len(columns) < 4 or not columns[3].isdigit():
        raise ResourceReadError(f"{' '.join(argv)} printed no available-space figure")
    return int(columns[3]) / KB_PER_GB


def tree_gb(folder):
    """GB the folder's files use, from `du -sk`. Exit 1 is accepted: du exits 1 for a file that vanished during the
    walk but still prints the total. Raises ResourceReadError when du fails or prints no figure."""
    argv = ["du", "-sk", os.fspath(folder)]
    words = _required_output(argv, ok_codes=(0, 1)).split()
    if not words or not words[0].isdigit():
        raise ResourceReadError(f"{' '.join(argv)} printed no size")
    return int(words[0]) / KB_PER_GB
