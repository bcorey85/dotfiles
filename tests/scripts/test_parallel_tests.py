import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

PARALLEL_TESTS = pathlib.Path(os.environ.get("PARALLEL_TESTS")
                              or pathlib.Path(__file__).resolve().parents[1] / "parallel_tests.py")

SLEEPING_TEST = """import time
import unittest


class SleepingTest(unittest.TestCase):
    def test_sleeps_past_the_limit(self):
        time.sleep(60)
"""
QUICK_TEST = """import unittest


class QuickTest(unittest.TestCase):
    def test_passes(self):
        self.assertTrue(True)
"""


class FileTimeoutTest(unittest.TestCase):
    def run_suite(self, test_sources):
        repo = tempfile.TemporaryDirectory()
        self.addCleanup(repo.cleanup)
        tests_folder = pathlib.Path(repo.name) / "tests" / "scripts"
        tests_folder.mkdir(parents=True)
        for name, source in test_sources.items():
            (tests_folder / name).write_text(source)
        environment = dict(os.environ, REPO_ROOT=repo.name, TEST_FILE_TIMEOUT_SECONDS="2")
        return subprocess.run([sys.executable, str(PARALLEL_TESTS)], capture_output=True, text=True, env=environment,
                              timeout=50)

    def test_a_file_past_the_limit_is_killed_and_reported_as_failed(self):
        finished = self.run_suite({"test_sleepy.py": SLEEPING_TEST, "test_quick.py": QUICK_TEST})

        self.assertEqual(1, finished.returncode, finished.stdout)
        self.assertRegex(finished.stdout, r"test_sleepy\.py .* FAIL")
        self.assertRegex(finished.stdout, r"test_quick\.py .* OK")
        self.assertIn("test_sleepy.py timed out after 2s", finished.stdout)


if __name__ == "__main__":
    unittest.main()
