"""Questions about a running process and its process group, for any caller: a process's command line and a SIGTERM
for its group. It reads no toolkit state."""
import os
import signal
import subprocess

PS_TIMEOUT_SECONDS = 10


class ProcessQueryError(OSError):
    """`ps` could not answer: it is missing, timed out, or failed for a reason other than an unknown pid."""


def command_line(pid):
    """The command line of process pid, or "" when no such process runs. Raises ProcessQueryError when `ps` fails."""
    try:
        finished = subprocess.run(["ps", "-o", "command=", "-p", str(pid)], capture_output=True, text=True,
                                  timeout=PS_TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ProcessQueryError(f"ps -o command= -p {pid}: {error}") from error
    # `ps` exits 1 with no output for a pid that is gone: an answer, not a failure.
    if finished.returncode == 1 and not finished.stderr.strip():
        return ""
    if finished.returncode != 0:
        raise ProcessQueryError(f"ps -o command= -p {pid} exited {finished.returncode}: {finished.stderr.strip()}")
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
