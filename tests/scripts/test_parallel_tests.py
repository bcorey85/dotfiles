import importlib
import json
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
BROKEN_TEST = """import unittest


class BrokenTest(unittest.TestCase):
    def test_fails(self):
        self.fail("broken on purpose")
"""


class FileTimeoutTest(unittest.TestCase):
    def run_suite(self, test_sources):
        repo_root = make_repo(self, test_sources)
        slot_scratch = tempfile.TemporaryDirectory()
        self.addCleanup(slot_scratch.cleanup)
        environment = dict(os.environ, REPO_ROOT=repo_root, TEST_FILE_TIMEOUT_SECONDS="10",
                           SUITE_SLOT_DIR=str(pathlib.Path(slot_scratch.name) / "slots"))
        return subprocess.run([sys.executable, str(PARALLEL_TESTS)], capture_output=True, text=True, env=environment,
                              timeout=50)

    def test_a_file_past_the_limit_is_killed_and_reported_as_failed(self):
        finished = self.run_suite({"test_sleepy.py": SLEEPING_TEST, "test_quick.py": QUICK_TEST})

        self.assertEqual(1, finished.returncode, finished.stdout)
        self.assertRegex(finished.stdout, r"test_sleepy\.py .* FAIL")
        self.assertRegex(finished.stdout, r"test_quick\.py .* OK")
        self.assertIn("test_sleepy.py timed out after 10s", finished.stdout)

    def test_the_summary_file_names_the_test_count_and_the_failed_files(self):
        summary_scratch = tempfile.TemporaryDirectory()
        self.addCleanup(summary_scratch.cleanup)
        summary_file = pathlib.Path(summary_scratch.name) / "summary.json"
        repo_root = make_repo(self, {"test_quick.py": QUICK_TEST, "test_broken.py": BROKEN_TEST})
        environment = dict(os.environ, REPO_ROOT=repo_root, SUITE_SUMMARY_FILE=str(summary_file),
                           SUITE_SLOT_DIR=str(pathlib.Path(summary_scratch.name) / "slots"))

        subprocess.run([sys.executable, str(PARALLEL_TESTS)], capture_output=True, text=True, env=environment,
                       timeout=50)

        summary = json.loads(summary_file.read_text())
        self.assertEqual({"tests": 2, "files": 2, "failed_files": ["test_broken.py"]}, summary)


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


# Eight tests in two classes; each appends its own id and its process id to RAN_LOG.
RECORDING_TEST = """import os
import unittest


class Recording:
    def record(self):
        with open(os.environ["RAN_LOG"], "a") as log:
            log.write(f"{self.id()} {os.getpid()}\\n")

    def test_a(self):
        self.record()

    def test_b(self):
        self.record()

    def test_c(self):
        self.record()

    def test_d(self):
        self.record()


class FirstTest(Recording, unittest.TestCase):
    pass


class SecondTest(Recording, unittest.TestCase):
    pass
"""


# The seventh of eight tests ends its process with no unittest summary.
CRASHING_TEST = RECORDING_TEST.replace("    def test_c(self):\n        self.record()",
                                       "    def test_c(self):\n        if type(self).__name__ == 'SecondTest':\n"
                                       "            os._exit(3)\n        self.record()")
# The seventh of eight tests sleeps past the limit.
STALLING_TEST = RECORDING_TEST.replace("    def test_c(self):\n        self.record()",
                                       "    def test_c(self):\n        if type(self).__name__ == 'SecondTest':\n"
                                       "            import time\n            time.sleep(60)\n        self.record()")
# Two tests: with four processes, two of them take no test.
TWO_TESTS = """import unittest


class TwoTest(unittest.TestCase):
    def test_a(self):
        pass

    def test_b(self):
        pass
"""
# The first process to load the file sees one test more than the rest: it wins the exclusive create of MARKER_FILE.
UNEVEN_TEST = RECORDING_TEST + """

try:
    os.close(os.open(os.environ["MARKER_FILE"], os.O_CREAT | os.O_EXCL))
except FileExistsError:
    pass
else:
    class ThirdTest(unittest.TestCase):
        def test_only_one_process_sees(self):
            pass
"""
SHARDED_NAME = "test_review_loop_script.py"


class ShardedFileTest(unittest.TestCase):
    def run_runner(self, file_name, source, arguments=(), limit_seconds=None):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        ran_log = pathlib.Path(scratch.name) / "ran.log"
        ran_log.write_text("")
        environment = dict(os.environ, REPO_ROOT=make_repo(self, {file_name: source}),
                           SUITE_SLOT_DIR=str(pathlib.Path(scratch.name) / "slots"), RAN_LOG=str(ran_log),
                           MARKER_FILE=str(pathlib.Path(scratch.name) / "marker"))
        if limit_seconds:
            environment["TEST_FILE_TIMEOUT_SECONDS"] = str(limit_seconds)
        finished = subprocess.run([sys.executable, str(PARALLEL_TESTS), *arguments], capture_output=True, text=True,
                                  env=environment, timeout=50)
        ran_lines = [line.split() for line in ran_log.read_text().splitlines()]
        test_ids = sorted(test_id for test_id, _ in ran_lines)
        process_ids = {process_id for _, process_id in ran_lines}
        return finished, test_ids, process_ids

    def run_suite(self, file_name, arguments=()):
        finished, test_ids, process_ids = self.run_runner(file_name, RECORDING_TEST, arguments)
        self.assertEqual(0, finished.returncode, finished.stdout + finished.stderr)
        return finished.stdout, test_ids, process_ids

    def assert_all_eight_ran_once_in_four_processes(self, stdout, test_ids, process_ids):
        expected_ids = sorted(f"test_review_loop_script.{class_name}.test_{letter}"
                              for class_name in ("FirstTest", "SecondTest") for letter in "abcd")
        self.assertEqual(expected_ids, test_ids)
        self.assertEqual(4, len(process_ids), "the file did not run as four processes")
        self.assertRegex(stdout, r"test_review_loop_script\.py +8 tests .* OK")
        self.assertIn("8 tests in 1 files", stdout)

    def test_the_review_loop_test_file_runs_in_several_processes_and_each_test_runs_once(self):
        stdout, test_ids, process_ids = self.run_suite(SHARDED_NAME)

        self.assert_all_eight_ran_once_in_four_processes(stdout, test_ids, process_ids)

    def test_a_run_that_names_only_the_sharded_file_still_runs_every_test_of_it(self):
        stdout, test_ids, process_ids = self.run_suite(SHARDED_NAME, arguments=[SHARDED_NAME])

        self.assert_all_eight_ran_once_in_four_processes(stdout, test_ids, process_ids)

    def test_one_process_that_crashes_fails_the_file(self):
        finished, test_ids, _ = self.run_runner(SHARDED_NAME, CRASHING_TEST)

        self.assertEqual(1, finished.returncode, finished.stdout)
        self.assertRegex(finished.stdout, r"test_review_loop_script\.py .* FAIL")
        self.assertNotIn("test_review_loop_script.SecondTest.test_c", test_ids)
        self.assertIn("1 failed", finished.stdout)

    def test_one_process_past_the_limit_fails_the_file_and_names_the_process(self):
        finished, _, _ = self.run_runner(SHARDED_NAME, STALLING_TEST, limit_seconds=10)

        self.assertEqual(1, finished.returncode, finished.stdout)
        self.assertRegex(finished.stdout, r"test_review_loop_script\.py .* FAIL")
        self.assertIn("test_review_loop_script.py timed out after 10s and was killed (process 3 of 4)",
                      finished.stdout)

    def test_a_process_that_takes_no_test_fails_the_file(self):
        finished, _, _ = self.run_runner(SHARDED_NAME, TWO_TESTS)

        self.assertEqual(1, finished.returncode, finished.stdout)
        self.assertRegex(finished.stdout, r"test_review_loop_script\.py +2 tests .* FAIL")
        self.assertIn("ran no test", finished.stdout)

    def test_processes_that_load_different_numbers_of_tests_fail_the_file(self):
        finished, _, _ = self.run_runner(SHARDED_NAME, UNEVEN_TEST)

        self.assertEqual(1, finished.returncode, finished.stdout)
        self.assertRegex(finished.stdout, r"test_review_loop_script\.py .* FAIL")
        self.assertIn("its processes loaded different numbers of tests: [8, 9]", finished.stdout)

    def test_a_file_with_no_shard_entry_runs_in_one_process(self):
        stdout, test_ids, process_ids = self.run_suite("test_plain.py")

        self.assertEqual(8, len(test_ids))
        self.assertEqual(1, len(process_ids))
        self.assertRegex(stdout, r"test_plain\.py +8 tests .* OK")


class CountProblemsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(PARALLEL_TESTS.parent))
        cls.addClassCleanup(sys.path.remove, str(PARALLEL_TESTS.parent))
        cls.runner = importlib.import_module(PARALLEL_TESTS.stem)

    def problems(self, shard_runs):
        return self.runner.count_problems("test_big.py", shard_runs)

    def test_counts_that_add_up_to_the_file_give_no_problem(self):
        whole = {"total": 5, "chosen": 5}
        self.assertEqual([], self.problems([(5, whole)]))
        self.assertEqual([], self.problems([(3, {"total": 5, "chosen": 3}), (2, {"total": 5, "chosen": 2})]))
        self.assertEqual([], self.problems([(0, {"total": 0, "chosen": 0})]))

    def test_fewer_tests_run_than_the_file_holds_is_a_problem(self):
        problems = self.problems([(3, {"total": 5, "chosen": 3}), (1, {"total": 5, "chosen": 2})])

        self.assertEqual(["test_big.py: 4 tests ran, but the file holds 5",
                          "test_big.py (one of 2 processes) ran 1 of the 2 tests it took"], problems)

    def test_a_process_with_no_count_is_a_problem(self):
        problems = self.problems([(3, {"total": 5, "chosen": 3}), (2, None)])

        self.assertEqual(1, len(problems))
        self.assertIn("wrote no readable count of its tests", problems[0])

    def test_a_report_that_is_not_two_whole_numbers_reads_as_no_report(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        report_path = pathlib.Path(scratch.name) / "report.json"

        self.assertIsNone(self.runner.read_shard_report(report_path))
        for text in ("", '{"total": 5', "[5, 5]", '{"total": "5", "chosen": 5}', '{"total": 5}'):
            report_path.write_text(text)
            self.assertIsNone(self.runner.read_shard_report(report_path), text)
        report_path.write_text('{"total": 5, "chosen": 2}')
        self.assertEqual({"total": 5, "chosen": 2}, self.runner.read_shard_report(report_path))


if __name__ == "__main__":
    unittest.main()
