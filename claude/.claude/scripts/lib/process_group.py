"""Questions about a running process and its process group, for any caller: a process's command line, program name
and resident memory, and a SIGTERM for its group. It reads no toolkit state."""
import os
import shlex
import signal
import subprocess
import time

PS_TIMEOUT_SECONDS = 10


class ProcessQueryError(OSError):
    """`ps` could not answer: it is missing, timed out, or failed for a reason other than an unknown pid."""


def pid_is_alive(owner_pid):
    """True when a process with this pid (an int or its digits) exists, even one this user may not signal."""
    try:
        pid = int(owner_pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, OverflowError):
        # A pid past the C int range cannot name a process.
        return False
    except PermissionError:
        return True
    return True


def group_id(pid):
    """The process group id of process pid, or None when no such process exists. Read it before signalling: a leader
    that has exited no longer names its group."""
    try:
        return os.getpgid(pid)
    except ProcessLookupError:
        return None


def group_is_alive(group):
    """True when any process of process group `group` exists, even one this user may not signal."""
    try:
        os.killpg(group, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _wait_until_not(is_alive, subject, seconds, poll_seconds):
    deadline = time.monotonic() + seconds
    while is_alive(subject):
        if time.monotonic() >= deadline:
            return False
        time.sleep(poll_seconds)
    return True


def wait_until_group_gone(group, seconds, poll_seconds=0.05):
    """True once no process of group `group` exists, polling for at most `seconds`; False while one is still alive."""
    return _wait_until_not(group_is_alive, group, seconds, poll_seconds)


def _ps_field(pid, field, wide=False):
    """The stripped `ps` output for `field` of process pid, or "" when no such process runs. Raises
    ProcessQueryError when `ps` fails."""
    ps_command = ["ps", *(["-ww"] if wide else []), "-o", f"{field}=", "-p", str(pid)]
    try:
        finished = subprocess.run(ps_command, capture_output=True, text=True, timeout=PS_TIMEOUT_SECONDS,
                                  check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ProcessQueryError(f"{shlex.join(ps_command)}: {error}") from error
    # `ps` exits 1 with no output for a pid that is gone: an answer, not a failure.
    if finished.returncode == 1 and not finished.stderr.strip():
        return ""
    if finished.returncode != 0:
        raise ProcessQueryError(
            f"{shlex.join(ps_command)} exited {finished.returncode}: {finished.stderr.strip()}")
    return finished.stdout.strip()


def command_line(pid):
    """The command line of process pid, or "" when no such process runs. Raises ProcessQueryError when `ps` fails."""
    return _ps_field(pid, "command", wide=True)


def resident_bytes(pid):
    """The resident memory of process pid in bytes, or None when no such process runs. Raises ProcessQueryError
    when `ps` fails or prints something other than a number of KB."""
    kilobytes = _ps_field(pid, "rss")
    if kilobytes == "":
        return None
    if not kilobytes.isdigit():
        raise ProcessQueryError(f"ps -o rss= -p {pid}: expected a number of KB, got {kilobytes!r}")
    return int(kilobytes) * 1024


def program_name(pid):
    """The base name of the program process pid runs, or "" when no such process runs. Raises ProcessQueryError
    when `ps` fails."""
    return os.path.basename(_ps_field(pid, "comm"))


def terminate_group(pid):
    """Sends SIGTERM to the process group of process pid. Returns False when the process is already gone and True when
    the signal was sent. Raises OSError on any other failure, such as a missing permission."""
    try:
        group = os.getpgid(pid)
        os.killpg(group, signal.SIGTERM)
    except ProcessLookupError:
        return False
    return True
