import fcntl
import pathlib
import sys
import tempfile
import threading
import time
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import file_lock


class HoldExclusiveTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.lock_path = pathlib.Path(temp.name) / "x.lock"

    def test_the_block_runs_and_the_lock_is_free_after_it(self):
        with file_lock.hold_exclusive(self.lock_path, 1):
            pass

        with file_lock.hold_exclusive(self.lock_path, 0.1):
            pass

    def test_a_held_lock_raises_a_timeout_that_names_the_file_and_runs_nothing(self):
        ran = []
        with open(self.lock_path, "a", encoding="utf-8") as holder:
            fcntl.flock(holder, fcntl.LOCK_EX)
            with self.assertRaises(file_lock.LockTimeoutError) as raised, \
                    file_lock.hold_exclusive(self.lock_path, 0.1):
                ran.append(True)

        self.assertIn(str(self.lock_path), str(raised.exception))
        self.assertIsInstance(raised.exception, OSError)
        self.assertEqual(ran, [])

    def test_a_waiter_gets_the_lock_once_the_holder_lets_go(self):
        order = []

        def first():
            with file_lock.hold_exclusive(self.lock_path, 5):
                order.append("first in")
                time.sleep(0.3)
                order.append("first out")

        thread = threading.Thread(target=first)
        thread.start()
        time.sleep(0.1)
        with file_lock.hold_exclusive(self.lock_path, 5):
            order.append("second in")
        thread.join()

        self.assertEqual(order, ["first in", "first out", "second in"])

    def test_the_lock_is_freed_when_the_block_raises(self):
        with self.assertRaises(RuntimeError), file_lock.hold_exclusive(self.lock_path, 1):
            raise RuntimeError("boom")

        with file_lock.hold_exclusive(self.lock_path, 0.1):
            pass


if __name__ == "__main__":
    unittest.main()
