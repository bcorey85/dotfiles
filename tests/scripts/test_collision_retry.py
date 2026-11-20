"""Tests for lib/collision_retry.py: the wait and retry policy of a check that collided on the test database."""
import sys
import unittest
from unittest import mock

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import check_output
import collision_retry


class CollisionRetrySecondsTest(unittest.TestCase):
    def test_a_retry_runs_only_for_a_collision_with_time_left_after_the_wait(self):
        collided = "Got an error recreating the test database"
        wait = collision_retry.TEST_DB_COLLISION_WAIT_SECONDS
        floor = collision_retry.MIN_COMMAND_SECONDS
        enough = wait + floor
        self.assertTrue(check_output.is_test_db_collision(collided), "fixture must read as a collision")
        cases = [
            ("enough time", 1, collided, enough, floor),
            ("too little time", 1, collided, enough - 1, None),
            ("passed run", 0, collided, 1000, None),
            ("timed out run", None, collided, 1000, None),
            ("no collision", 1, "1 failed", 1000, None),
        ]
        for label, code, output, seconds_left, wanted in cases:
            with self.subTest(label):
                retry_seconds = collision_retry.collision_retry_seconds(code, output, seconds_left)
                self.assertEqual(wanted, retry_seconds, label)

    def test_waiting_out_a_collision_sleeps_the_wait_seconds(self):
        with mock.patch.object(collision_retry.time, "sleep") as sleep:
            collision_retry.wait_out_collision()

        sleep.assert_called_once_with(collision_retry.TEST_DB_COLLISION_WAIT_SECONDS)


if __name__ == "__main__":
    unittest.main()
