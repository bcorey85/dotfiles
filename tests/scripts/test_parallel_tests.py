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
        repo_root = make_repo(self, test_sources)
        slot_scratch = tempfile.TemporaryDirectory()
        self.addCleanup(slot_scratch.cleanup)
        environment = dict(os.environ, REPO_ROOT=repo_root, TEST_FILE_TIMEOUT_SECONDS="2",
                           SUITE_SLOT_DIR=str(pathlib.Path(slot_scratch.name) / "slots"))
        return subprocess.run([sys.executable, str(PARALLEL_TESTS)], capture_output=True, text=True, env=environment,
                              timeout=50)

    def test_a_file_past_the_limit_is_killed_and_reported_as_failed(self):
        finished = self.run_suite({"test_sleepy.py": SLEEPING_TEST, "test_quick.py": QUICK_TEST})

        self.assertEqual(1, finished.returncode, finished.stdout)
        self.assertRegex(finished.stdout, r"test_sleepy\.py .* FAIL")
        self.assertRegex(finished.stdout, r"test_quick\.py .* OK")
        self.assertIn("test_sleepy.py timed out after 2s", finished.stdout)


def make_repo(test_case, test_sources):
    repo = tempfile.TemporaryDirectory()
    test_case.addCleanup(repo.cleanup)
    tests_folder = pathlib.Path(repo.name) / "tests" / "scripts"
    tests_folder.mkdir(parents=True)
    for name, source in test_sources.items():
        (tests_folder / name).write_text(source)
    return repo.name


# Takes the guard lock without waiting; a second test file holding it at the same time records an overlap.
GUARDED_TEST = """import fcntl
import os
import time
import unittest


class GuardedTest(unittest.TestCase):
    def test_runs_alone(self):
        with open(os.environ["GUARD_FILE"], "a") as guard:
            try:
                fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                with open(os.environ["OVERLAP_LOG"], "a") as log:
                    log.write("overlap\\n")
                return
            time.sleep(1)
"""
NICENESS_TEST = """import os
import unittest


class NicenessTest(unittest.TestCase):
    def test_records_niceness(self):
        with open(os.environ["NICENESS_LOG"], "w") as log:
            log.write(str(os.nice(0)))
"""


class SlotPoolTest(unittest.TestCase):
    def test_two_runners_sharing_one_slot_never_overlap_test_files(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        overlap_log = pathlib.Path(scratch.name) / "overlap.log"
        environment = dict(os.environ, SUITE_SLOT_DIR=str(pathlib.Path(scratch.name) / "slots"), SUITE_SLOT_COUNT="1",
                           GUARD_FILE=str(pathlib.Path(scratch.name) / "guard"), OVERLAP_LOG=str(overlap_log))
        sources = {"test_guarded_a.py": GUARDED_TEST, "test_guarded_b.py": GUARDED_TEST}
        runners = []
        for _ in range(2):
            runner_environment = dict(environment, REPO_ROOT=make_repo(self, sources))
            runners.append(subprocess.Popen([sys.executable, str(PARALLEL_TESTS)], env=runner_environment,
                                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True))

        outputs = [runner.communicate(timeout=60)[0] for runner in runners]

        for runner, output in zip(runners, outputs, strict=True):
            self.assertEqual(0, runner.returncode, output)
        self.assertFalse(overlap_log.exists(), "two test files ran at the same time")

    def test_workers_run_at_a_raised_niceness(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        niceness_log = pathlib.Path(scratch.name) / "niceness.log"
        environment = dict(os.environ, REPO_ROOT=make_repo(self, {"test_nice.py": NICENESS_TEST}),
                           SUITE_SLOT_DIR=str(pathlib.Path(scratch.name) / "slots"), NICENESS_LOG=str(niceness_log))

        finished = subprocess.run([sys.executable, str(PARALLEL_TESTS)], capture_output=True, text=True,
                                  env=environment, timeout=50)

        self.assertEqual(0, finished.returncode, finished.stdout)
        runner_niceness = os.nice(0)
        self.assertEqual(min(runner_niceness + 10, 19), int(niceness_log.read_text()))


if __name__ == "__main__":
    unittest.main()
