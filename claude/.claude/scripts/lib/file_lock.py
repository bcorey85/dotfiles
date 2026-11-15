"""file_lock.py: an exclusive lock on a lock file, held for a `with` block, that gives up after a timeout.

The lock is an flock on a file of its own, so two processes (or two open descriptions in one process) exclude each
other, and the operating system frees it when the holder dies."""
import contextlib
import fcntl
import time

RETRY_SECONDS = 0.02


class LockTimeoutError(OSError):
    """The lock stayed held by someone else for the whole timeout. The message names the lock file."""


@contextlib.contextmanager
def hold_exclusive(lock_path, timeout_seconds):
    """Holds an exclusive lock on `lock_path` (made when missing) for the block. Raises LockTimeoutError when another
    holder keeps it for `timeout_seconds`; raises OSError when the file cannot be opened."""
    with open(lock_path, "a", encoding="utf-8") as lock_file:
        deadline = time.monotonic() + timeout_seconds
        while True:
            try:
                fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise LockTimeoutError(f"{lock_path} is locked by another process (waited {timeout_seconds:g} s)") \
                        from None
                time.sleep(RETRY_SECONDS)
        try:
            yield
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
