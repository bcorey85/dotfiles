#!/usr/bin/env python3
"""Run every tests/scripts/test_*.py file as its own process, `nproc` at a time, slowest first.

  parallel_tests.py                       run the suite, print one line per file and failing output; exit 1 on failure
  parallel_tests.py test_a.py test_b.py   run only the named files from tests/scripts; an unknown name exits non-zero
  parallel_tests.py --worker FILE I N     (internal) run the tests of FILE whose position mod N is I

A file listed in SHARDS runs as several processes, each taking every Nth test, so one huge file cannot bound the
wall-clock. Each process writes how many tests the file holds; the file fails when the tests its processes ran do
not add up to that number, or when one of several processes ran none. Expected failures and skips follow unittest:
they do not fail the file."""

import concurrent.futures
import fcntl
import functools
import importlib
import json
import os
import pathlib
import re
import signal
import subprocess
import sys
import tempfile
import time
import unittest

# REPO_ROOT overrides the repo that holds tests/scripts, so the bundle copy can run against the installed suite.
REPO_ROOT = pathlib.Path(os.environ.get("REPO_ROOT") or pathlib.Path(__file__).resolve().parent.parent)
SCRIPTS_TESTS = REPO_ROOT / "tests" / "scripts"
# A test process that runs longer than this many seconds is killed and its file reported as failed.
# TEST_FILE_TIMEOUT_SECONDS overrides the limit.
FILE_TIMEOUT_SECONDS = float(os.environ.get("TEST_FILE_TIMEOUT_SECONDS") or 1200)
# How much nicer than the runner each test process runs.
WORKER_NICENESS = 10
# Files known to take minutes; each runs as this many processes, and the limit above applies to each process. The
# file's printed seconds are the sum over its processes.
SHARDS = {"test_review_loop_script.py": 4}
# Names the file where a test process writes how many tests the file holds and how many it took.
SHARD_REPORT_VARIABLE = "PARALLEL_TESTS_SHARD_REPORT"
# Slowest files by measured time, started before the rest (the rest start by file size, largest first).
HEAVY_FIRST = ["test_verify_branch_script.py", "test_refactor_flow.py", "test_review_fix_script.py", "test_adr_flow.py"]


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def run_worker(test_file, shard_index, shard_count):
    # Raised niceness is inherited by every process the tests start, so interactive work stays responsive.
    os.nice(WORKER_NICENESS)
    sys.path.insert(0, str(SCRIPTS_TESTS))
    module = importlib.import_module(pathlib.Path(test_file).stem)
    all_tests = list(flatten(unittest.defaultTestLoader.loadTestsFromModule(module)))
    chosen = [test for position, test in enumerate(all_tests) if position % shard_count == shard_index]
    report_file = os.environ.get(SHARD_REPORT_VARIABLE)
    if report_file:
        pathlib.Path(report_file).write_text(json.dumps({"total": len(all_tests), "chosen": len(chosen)}))
    suite = unittest.TestSuite(chosen)
    outcome = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if outcome.wasSuccessful() else 1


def build_jobs(file_names=()):
    # Returns (file name, shard index, shard count) jobs, heaviest first. Given file names, keeps only those files
    # and exits non-zero on a name that is not a test file in SCRIPTS_TESTS.
    files = sorted(SCRIPTS_TESTS.glob("test_*.py"), key=lambda path: path.stat().st_size, reverse=True)
    if file_names:
        known_names = {path.name for path in files}
        unknown_names = [name for name in file_names if name not in known_names]
        if unknown_names:
            sys.exit(f"parallel_tests.py: not a test file in {SCRIPTS_TESTS}: {' '.join(unknown_names)}")
        files = [path for path in files if path.name in file_names]
    jobs = []
    for path in files:
        shard_count = SHARDS.get(path.name, 1)
        for shard_index in range(shard_count):
            jobs.append((path.name, shard_index, shard_count))
    jobs.sort(key=lambda job: HEAVY_FIRST.index(job[0]) if job[0] in HEAVY_FIRST else len(HEAVY_FIRST))
    return jobs


def write_fixed_git_config(config_folder):
    # Writes the one global git config every test process sees; returns its path.
    # The empty file stands in for the machine's global ignore and attributes files.
    config_path = pathlib.Path(config_folder) / "gitconfig"
    empty_path = pathlib.Path(config_folder) / "empty"
    empty_path.write_text("")
    config_path.write_text(
        "[user]\n\tname = ci\n\temail = ci@example.com\n[init]\n\tdefaultBranch = master\n"
        f'[core]\n\texcludesFile = "{empty_path}"\n\tattributesFile = "{empty_path}"\n'
    )
    return config_path


def fixed_git_environment(config_path):
    # Returns the environment for a test process: the fixed config replaces the machine's global and system git config,
    # and config passed through the environment is dropped.
    environment = {
        name: value
        for name, value in os.environ.items()
        if name not in ("GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT")
        and not name.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_"))
    }
    environment["GIT_CONFIG_GLOBAL"] = str(config_path)
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    return environment


def slot_count():
    # Test files that may run at once across every suite run on this machine; SUITE_SLOT_COUNT overrides nproc.
    return int(os.environ.get("SUITE_SLOT_COUNT") or os.cpu_count() or 1)


def slot_folder():
    # Holds one lock file per slot; SUITE_SLOT_DIR overrides it. Without a runtime dir it falls back to the temp dir.
    configured = os.environ.get("SUITE_SLOT_DIR")
    if configured:
        return pathlib.Path(configured)
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if runtime:
        return pathlib.Path(runtime) / "dotfiles-suite-slots"
    return pathlib.Path(tempfile.gettempdir()) / f"dotfiles-suite-slots-{os.getuid()}"


def acquire_slot(folder, count):
    # Blocks until one of `count` slot files is flocked; returns its open descriptor. The kernel frees the lock when the
    # process exits, so a crashed run leaks no slot.
    folder.mkdir(parents=True, exist_ok=True)
    while True:
        for number in range(count):
            slot_descriptor = os.open(folder / f"slot-{number}.lock", os.O_CREAT | os.O_WRONLY)
            try:
                fcntl.flock(slot_descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                os.close(slot_descriptor)
                continue
            return slot_descriptor
        time.sleep(0.05)


def run_job(job, environment, report_folder):
    slot_descriptor = acquire_slot(slot_folder(), slot_count())
    try:
        return run_job_in_slot(job, environment, report_folder)
    finally:
        os.close(slot_descriptor)


def read_shard_report(report_path):
    # Returns the {"total", "chosen"} counts a test process wrote, or None when it wrote none or broke off mid-write.
    try:
        report = json.loads(report_path.read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(report, dict) or not all(isinstance(report.get(key), int) for key in ("total", "chosen")):
        return None
    return report


def count_problems(test_file, shard_runs):
    # Returns one line per way the processes of a file fail to add up to the whole file. `shard_runs` holds one
    # (tests run, shard report) pair per process.
    shard_count = len(shard_runs)
    process_name = f"{test_file} (one of {shard_count} processes)" if shard_count > 1 else test_file
    reports = [report for _, report in shard_runs]
    if None in reports:
        return [f"{process_name} wrote no readable count of its tests"]
    problems = []
    totals = sorted({report["total"] for report in reports})
    if len(totals) > 1:
        problems.append(f"{test_file}: its processes loaded different numbers of tests: {totals}")
    tests_run = sum(count for count, _ in shard_runs)
    if tests_run != totals[0]:
        problems.append(f"{test_file}: {tests_run} tests ran, but the file holds {totals[0]}")
    for count, report in shard_runs:
        if count != report["chosen"]:
            problems.append(f"{process_name} ran {count} of the {report['chosen']} tests it took")
    if shard_count > 1 and any(count == 0 for count, _ in shard_runs):
        problems.append(f"{process_name} ran no test: lower its SHARDS entry or remove it")
    return problems


def run_job_in_slot(job, environment, report_folder):
    test_file, shard_index, shard_count = job
    report_path = pathlib.Path(report_folder) / f"{test_file}.{shard_index}.json"
    environment = dict(environment, **{SHARD_REPORT_VARIABLE: str(report_path)})
    started = time.monotonic()
    command = [
        sys.executable,
        str(pathlib.Path(__file__).resolve()),
        "--worker",
        test_file,
        str(shard_index),
        str(shard_count),
    ]
    # The worker leads its own process group, so a timeout kills the subprocesses its tests started too.
    process = subprocess.Popen(
        command,
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        start_new_session=True,
    )
    timed_out = False

    try:
        stdout, stderr = process.communicate(timeout=FILE_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()

    seconds = time.monotonic() - started
    output = (stdout or "") + (stderr or "")
    if timed_out:
        process_note = f" (process {shard_index + 1} of {shard_count})" if shard_count > 1 else ""
        output += f"\n{test_file} timed out after {FILE_TIMEOUT_SECONDS:g}s and was killed{process_note}\n"
    ran = re.search(r"^Ran (\d+) tests?", output, re.MULTILINE)
    test_count = int(ran.group(1)) if ran else 0
    passed = not timed_out and process.returncode == 0 and ran is not None
    return test_file, test_count, seconds, passed, output, read_shard_report(report_path)


def main(file_names=()):
    jobs = build_jobs(file_names)
    workers = slot_count()
    wall_started = time.monotonic()
    per_file = {}
    # The guard puts a failing `ledger` first on PATH and an empty CARGO_HOME in this process's environment, which every
    # test process inherits, so no test reaches the ledger this machine installed.
    # The guard comes from this file's own tree: a REPO_ROOT suite need not hold toolkit_paths.
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "scripts"))
    toolkit_paths = importlib.import_module("toolkit_paths")
    toolkit_paths.guard_real_ledger()
    with tempfile.TemporaryDirectory() as config_folder:
        fixed_git_config = write_fixed_git_config(config_folder)
        environment = fixed_git_environment(fixed_git_config)
        job_runner = functools.partial(run_job, environment=environment, report_folder=config_folder)
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            for test_file, test_count, seconds, passed, output, shard_report in pool.map(job_runner, jobs):
                entry = per_file.setdefault(
                    test_file, {"count": 0, "seconds": 0.0, "passed": True, "failures": [], "shard_runs": []}
                )
                entry["count"] += test_count
                entry["seconds"] += seconds
                entry["passed"] = entry["passed"] and passed
                entry["shard_runs"].append((test_count, shard_report))
                if not passed:
                    entry["failures"].append(output)

    # A file whose processes all passed still fails when their test counts do not add up to the whole file.
    for test_file, entry in per_file.items():
        problems = count_problems(test_file, entry["shard_runs"])
        if problems and entry["passed"]:
            entry["passed"] = False
            entry["failures"].append("\n".join(problems))

    total_tests, total_seconds, failed_files = 0, 0.0, []
    for test_file in sorted(per_file):
        entry = per_file[test_file]
        status = "OK" if entry["passed"] else "FAIL"
        print(f"{test_file:42} {entry['count']:5} tests {entry['seconds']:7.1f}s {status}")
        total_tests += entry["count"]
        total_seconds += entry["seconds"]
        if not entry["passed"]:
            failed_files.append(test_file)
    for test_file in failed_files:
        print(f"\n===== {test_file} FAILED =====")
        for output in per_file[test_file]["failures"]:
            print(output)
    wall = time.monotonic() - wall_started
    print(
        f"\n{total_tests} tests in {len(per_file)} files, wall-clock {wall:.1f}s, "
        f"sum of per-file seconds {total_seconds:.1f}s, {len(failed_files)} failed"
    )
    return 1 if failed_files else 0


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] == "--worker":
        sys.exit(run_worker(sys.argv[2], int(sys.argv[3]), int(sys.argv[4])))
    sys.exit(main(sys.argv[1:]))
