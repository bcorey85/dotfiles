"""The wait and retry policy for a check that failed on a test-database collision (another run of the same tests shares
the test database). Detecting a collision is lib/check_output.py `is_test_db_collision`; this module says whether a
retry runs, how long it may take, and waits before it. Used by the coder gate and by review/full_check.py."""
import time

from check_output import is_test_db_collision

# The seconds a caller waits before it runs a collided check once more.
TEST_DB_COLLISION_WAIT_SECONDS = 30
# A command is not started with less time left than this: it could not give a result.
MIN_COMMAND_SECONDS = 60


def collision_retry_seconds(code, output, seconds_left):
    """The seconds a collided check's retry has once it has waited, or None when no retry runs: the run passed or
    timed out, its output shows no test-database collision, or less than MIN_COMMAND_SECONDS would be left after the
    wait. seconds_left is what the caller's time limit has left after the first run."""
    if code in (0, None) or not is_test_db_collision(output):
        return None

    seconds_after_wait = seconds_left - TEST_DB_COLLISION_WAIT_SECONDS
    if seconds_after_wait < MIN_COMMAND_SECONDS:
        return None
    return seconds_after_wait


def wait_out_collision():
    """Wait TEST_DB_COLLISION_WAIT_SECONDS so the other run can finish with the shared test database."""
    time.sleep(TEST_DB_COLLISION_WAIT_SECONDS)
