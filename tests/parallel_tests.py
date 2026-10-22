#!/usr/bin/env python3
"""Run every tests/scripts/test_*.py file as its own process, `nproc` at a time, slowest first.

  parallel_tests.py                       run the suite, print one line per file, print failing output, exit 1 on failure
  parallel_tests.py --worker FILE I N     (internal) run the tests of FILE whose position mod N is I

A file listed in SHARDS runs as several processes, each taking every Nth test, so one huge file cannot bound the
wall-clock. Expected failures and skips follow unittest: they do not fail the file."""
import concurrent.futures
import functools
import importlib
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import time
import unittest

# REPO_ROOT overrides the repo that holds tests/scripts, so the bundle copy can run against the installed suite.
REPO_ROOT = pathlib.Path(os.environ.get("REPO_ROOT") or pathlib.Path(__file__).resolve().parent.parent)
SCRIPTS_TESTS = REPO_ROOT / "tests" / "scripts"
# Files known to take minutes; each runs as this many processes.
SHARDS = {"test_code_step.py": 4}
# Slowest files by measured time, started before the rest (the rest start by file size, largest first).
# test_code_step_termination.py is one test, so it cannot be split and sets the lower bound on wall-clock.
HEAVY_FIRST = ["test_code_step_termination.py", "test_code_step.py", "test_verify_branch_script.py",
               "test_refactor_flow.py", "test_review_fix_script.py", "test_adr_flow.py"]


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def run_worker(testFile, shardIndex, shardCount):
    sys.path.insert(0, str(SCRIPTS_TESTS))
    module = importlib.import_module(pathlib.Path(testFile).stem)
    allTests = list(flatten(unittest.defaultTestLoader.loadTestsFromModule(module)))
    chosen = [test for position, test in enumerate(allTests) if position % shardCount == shardIndex]
    suite = unittest.TestSuite(chosen)
    outcome = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if outcome.wasSuccessful() else 1


def build_jobs():
    # Returns (file name, shard index, shard count) jobs, heaviest first.
    files = sorted(SCRIPTS_TESTS.glob("test_*.py"), key=lambda path: path.stat().st_size, reverse=True)
    jobs = []
    for path in files:
        shardCount = SHARDS.get(path.name, 1)
        for shardIndex in range(shardCount):
            jobs.append((path.name, shardIndex, shardCount))
    jobs.sort(key=lambda job: HEAVY_FIRST.index(job[0]) if job[0] in HEAVY_FIRST else len(HEAVY_FIRST))
    return jobs


def write_fixed_git_config(configFolder):
    # Writes the one global git config every test process sees; returns its path.
    # The empty file stands in for the machine's global ignore and attributes files.
    configPath = pathlib.Path(configFolder) / "gitconfig"
    emptyPath = pathlib.Path(configFolder) / "empty"
    emptyPath.write_text("")
    configPath.write_text('[user]\n\tname = ci\n\temail = ci@example.com\n[init]\n\tdefaultBranch = master\n'
                          f'[core]\n\texcludesFile = "{emptyPath}"\n\tattributesFile = "{emptyPath}"\n')
    return configPath


def fixed_git_environment(configPath):
    # Returns the environment for a test process: the fixed config replaces the machine's global and system git config,
    # and config passed through the environment is dropped.
    environment = {name: value for name, value in os.environ.items()
                   if name not in ("GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT")
                   and not name.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_"))}
    environment["GIT_CONFIG_GLOBAL"] = str(configPath)
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    return environment


def run_job(job, environment):
    testFile, shardIndex, shardCount = job
    started = time.monotonic()
    finished = subprocess.run(
        [sys.executable, str(pathlib.Path(__file__).resolve()), "--worker", testFile, str(shardIndex), str(shardCount)],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace", env=environment,
    )
    seconds = time.monotonic() - started
    output = finished.stdout + finished.stderr
    ran = re.search(r"^Ran (\d+) tests?", output, re.MULTILINE)
    testCount = int(ran.group(1)) if ran else 0
    return testFile, testCount, seconds, finished.returncode == 0 and ran is not None, output


def main():
    workers = os.cpu_count() or 1
    wallStarted = time.monotonic()
    perFile = {}
    with tempfile.TemporaryDirectory() as configFolder:
        environment = fixed_git_environment(write_fixed_git_config(configFolder))
        runJob = functools.partial(run_job, environment=environment)
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            for testFile, testCount, seconds, passed, output in pool.map(runJob, build_jobs()):
                entry = perFile.setdefault(testFile, {"count": 0, "seconds": 0.0, "passed": True, "failures": []})
                entry["count"] += testCount
                entry["seconds"] += seconds
                entry["passed"] = entry["passed"] and passed
                if not passed:
                    entry["failures"].append(output)

    totalTests, totalSeconds, failedFiles = 0, 0.0, []
    for testFile in sorted(perFile):
        entry = perFile[testFile]
        status = "OK" if entry["passed"] else "FAIL"
        print(f"{testFile:42} {entry['count']:5} tests {entry['seconds']:7.1f}s {status}")
        totalTests += entry["count"]
        totalSeconds += entry["seconds"]
        if not entry["passed"]:
            failedFiles.append(testFile)
    for testFile in failedFiles:
        print(f"\n===== {testFile} FAILED =====")
        for output in perFile[testFile]["failures"]:
            print(output)
    wall = time.monotonic() - wallStarted
    print(f"\n{totalTests} tests in {len(perFile)} files, wall-clock {wall:.1f}s, sum of per-file seconds {totalSeconds:.1f}s, "
          f"{len(failedFiles)} failed")
    return 1 if failedFiles else 0


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] == "--worker":
        sys.exit(run_worker(sys.argv[2], int(sys.argv[3]), int(sys.argv[4])))
    sys.exit(main())
