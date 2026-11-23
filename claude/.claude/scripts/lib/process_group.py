"""Questions about a running process and its process group, for any caller: a process's command line and a SIGTERM
for its group. It reads no toolkit state."""
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


def wait_until_gone(pid, seconds, poll_seconds=0.05):
    """True once process pid no longer exists, polling for at most `seconds`; False when it is still alive then."""
    deadline = time.monotonic() + seconds
    while pid_is_alive(pid):
        if time.monotonic() >= deadline:
            return False
        time.sleep(poll_seconds)
    return True


def command_line(pid):
    """The command line of process pid, or "" when no such process runs. Raises ProcessQueryError when `ps` fails."""
    ps_command = ["ps", "-ww", "-o", "command=", "-p", str(pid)]
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


def terminate_group(pid):
    """Sends SIGTERM to the process group of process pid. Returns False when the process is already gone and True when
    the signal was sent. Raises OSError on any other failure, such as a missing permission."""
    try:
        group = os.getpgid(pid)
        os.killpg(group, signal.SIGTERM)
    except ProcessLookupError:
        return False
    return True
