import contextlib
import io
import json
import pathlib
import shlex
import subprocess
import sys
import tempfile
import types
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import accepted_failures
import full_check
import full_check_gate
import handback
import review_loop_scoped_tests

BUILD_TIME_COMMAND = "pytest && npm test"
NARROWED_COMMAND = "npm test"


class StubHost(full_check_gate.FullCheckSteps):
    """A LoopRun stand-in: the check runs as the narrowed command and ends with the result the test sets."""

    def __init__(self, result, tail="tail text"):
        self.init_full_check_state()
        self.result = result
        self.tail = tail
        self.stops = []
        self.out = pathlib.Path(tempfile.mkdtemp(prefix="full-check-gate-test-"))

    def lint_pass(self, check_command):
        return True

    def run_check(self, check_command):
        self.full_check_command = NARROWED_COMMAND
        self.full_check = self.result
        return self.tail

    def stop(self, status, remaining):
        self.stops.append((status, remaining))


class FullCheckMessagesNameTheCommandThatRanTest(unittest.TestCase):
    def test_a_setup_fault_stop_names_the_narrowed_command(self):
        host = StubHost(full_check.SETUP_FAULT)

        host.full_check_pass(BUILD_TIME_COMMAND)

        status, findings = host.stops[0]
        self.assertEqual(status, handback.SETUP_FAULT_STATUS)
        self.assertIn(f"(`{NARROWED_COMMAND}`)", findings[0])
        self.assertNotIn(BUILD_TIME_COMMAND, findings[0])

    def test_a_failure_finding_names_the_narrowed_command(self):
        host = StubHost("failed (exit 1)", tail="FAIL web/app.spec.ts")

        host.full_check_pass(BUILD_TIME_COMMAND)

        status, findings = host.stops[0]
        self.assertEqual(status, "critical-blocker")
        self.assertIn(f"(`{NARROWED_COMMAND}`)", findings[0])
        self.assertNotIn(BUILD_TIME_COMMAND, findings[0])


SCOPED_COMMAND = "pytest tests/test_a.py"
BASE_THROTTLED_LINE = "FAILED tests/test_a.py::test_one - HTTPError: 429 retry after 12s"
HEAD_THROTTLED_LINE = "FAILED tests/test_a.py::test_one - HTTPError: 429 retry after 7s"
NEW_FAILING_LINE = "FAILED tests/test_a.py::test_two - AssertionError"


class ScopedHost(StubHost):
    """A host in a real git repo whose scoped command has a base run that fails with the throttled line."""

    def __init__(self, folder):
        super().__init__("failed (exit 1)")
        self.repo = pathlib.Path(folder) / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        self.out = pathlib.Path(folder) / "out"
        self.out.mkdir()
        self.gate_env = ()
        base_log = [BASE_THROTTLED_LINE, "1 failed in 3.00s"]
        self.scoped_base_runs[SCOPED_COMMAND] = full_check.BaseRun("failed (exit 1)",
                                                                   *full_check.log_comparison(base_log))

    def set_base(self, result, *log_lines):
        self.scoped_base_runs[SCOPED_COMMAND] = full_check.BaseRun(result, *full_check.log_comparison(list(log_lines)))

    def head_output(self, *log_lines):
        """The red scoped run's output as the log lines given, with no runner summary line."""
        return [(SCOPED_COMMAND, "exit 1", "\n".join(log_lines))]

    def head_failures(self, *lines):
        """The red scoped run's output as the failing lines given, then a runner summary line."""
        output = "\n".join([*lines, f"{len(lines)} failed in 3.00s"])
        return [(SCOPED_COMMAND, "exit 1", output)]


class AcceptedScopedFailureTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.host = ScopedHost(self.folder.name)

    def test_a_changed_throttling_line_blocks_without_a_row(self):
        failures = self.host.head_failures(HEAD_THROTTLED_LINE)

        self.assertFalse(self.host.scoped_failures_pre_existing(failures))

    def test_a_changed_throttling_line_is_pre_existing_with_a_row(self):
        accepted_failures.accept(self.host.repo, HEAD_THROTTLED_LINE, "me", "throttled upstream")
        failures = self.host.head_failures(HEAD_THROTTLED_LINE)

        self.assertTrue(self.host.scoped_failures_pre_existing(failures))

    def test_a_new_failing_test_still_blocks_with_a_row_for_another_line(self):
        accepted_failures.accept(self.host.repo, HEAD_THROTTLED_LINE, "me", "throttled upstream")
        failures = self.host.head_failures(HEAD_THROTTLED_LINE, NEW_FAILING_LINE)

        self.assertFalse(self.host.scoped_failures_pre_existing(failures))

    def test_a_row_for_a_line_the_base_run_lacks_does_not_pass_it(self):
        accepted_failures.accept(self.host.repo, NEW_FAILING_LINE, "me", "known")
        failures = self.host.head_failures(NEW_FAILING_LINE)

        self.assertFalse(self.host.scoped_failures_pre_existing(failures))

    def test_the_blocker_hint_prints_the_accept_command_with_the_line(self):
        hint = self.host.accept_failure_hint(self.host.head_failures(HEAD_THROTTLED_LINE))

        self.assertIn("accepted_failures.py accept", hint)
        self.assertIn(HEAD_THROTTLED_LINE, hint)
        self.assertIn("--by '<who>'", hint)

    def test_the_hint_is_empty_when_no_failing_line_is_named(self):
        self.assertEqual("", self.host.accept_failure_hint([]))

    def test_the_hint_shell_quotes_a_line_with_spaces_and_quotes(self):
        line = "FAILED t.py::a - it's 429"

        text = accepted_failures.accept_command_text(self.host.repo, [line])

        self.assertIn(f"--line {shlex.quote(line)}", text)

    def test_a_changed_detail_number_blocks_without_a_row(self):
        self.host.set_base("failed (exit 1)", BASE_THROTTLED_LINE, "E   assert 5 == 4")
        failures = self.host.head_output(BASE_THROTTLED_LINE, "E   assert 5 == 6")

        self.assertFalse(self.host.scoped_failures_pre_existing(failures))

    def test_a_new_error_line_differing_by_a_number_blocks_without_a_row(self):
        self.host.set_base("failed (exit 1)", "Error: port 8080 in use", BASE_THROTTLED_LINE)
        failures = self.host.head_output("Error: port 9090 in use", BASE_THROTTLED_LINE)

        self.assertFalse(self.host.scoped_failures_pre_existing(failures))

    def test_a_row_with_inner_double_spaces_and_a_name_timing_clears_the_failure(self):
        base_line = "FAILED t.py::a (6.1 s) - HTTP 429 retry  after 3s"
        head_line = "FAILED t.py::a (7.3 s) - HTTP 429 retry  after 5s"
        self.host.set_base("failed (exit 1)", base_line)
        accepted_failures.accept(self.host.repo, head_line, "me", "throttled")

        self.assertTrue(self.host.scoped_failures_pre_existing(self.host.head_output(head_line)))

    def test_a_numbered_test_id_is_not_excused_by_a_row_for_another_number(self):
        self.host.set_base("failed (exit 1)", "FAILED t.py::test_x[1] - HTTPError: 429")
        accepted_failures.accept(self.host.repo, "FAILED t.py::test_x[1] - HTTPError: 429", "me", "known")
        failures = self.host.head_output("FAILED t.py::test_x[2] - HTTPError: 429")

        self.assertFalse(self.host.scoped_failures_pre_existing(failures))

    def test_a_base_run_that_passed_blocks_with_a_row(self):
        accepted_failures.accept(self.host.repo, HEAD_THROTTLED_LINE, "me", "throttled")
        self.host.scoped_base_runs[SCOPED_COMMAND] = None

        self.assertFalse(self.host.scoped_failures_pre_existing(self.host.head_failures(HEAD_THROTTLED_LINE)))

    def test_a_different_head_result_blocks_with_a_row(self):
        accepted_failures.accept(self.host.repo, HEAD_THROTTLED_LINE, "me", "throttled")
        failures = [(SCOPED_COMMAND, "exit 2", HEAD_THROTTLED_LINE)]

        self.assertFalse(self.host.scoped_failures_pre_existing(failures))

    def test_a_new_error_line_without_a_masked_twin_blocks_with_a_row(self):
        accepted_failures.accept(self.host.repo, HEAD_THROTTLED_LINE, "me", "throttled")
        failures = self.host.head_output("Traceback (most recent call last): KeyError", HEAD_THROTTLED_LINE)

        self.assertFalse(self.host.scoped_failures_pre_existing(failures))

    def test_a_new_log_line_differing_only_by_numbers_passes_with_a_row(self):
        self.host.set_base("failed (exit 1)", "error: retry 3 of 5 at 10:01", BASE_THROTTLED_LINE)
        accepted_failures.accept(self.host.repo, HEAD_THROTTLED_LINE, "me", "throttled")
        failures = self.host.head_output("error: retry 4 of 5 at 10:02", HEAD_THROTTLED_LINE)

        self.assertTrue(self.host.scoped_failures_pre_existing(failures))

    def test_a_new_detail_line_blocks_with_a_row(self):
        self.host.set_base("failed (exit 1)", BASE_THROTTLED_LINE, "E   assert 5 == 4")
        accepted_failures.accept(self.host.repo, HEAD_THROTTLED_LINE, "me", "throttled")
        failures = self.host.head_output(HEAD_THROTTLED_LINE, "E   KeyError: 'token'")

        self.assertFalse(self.host.scoped_failures_pre_existing(failures))

    def test_a_changed_detail_number_under_an_accepted_changed_line_passes(self):
        self.host.set_base("failed (exit 1)", BASE_THROTTLED_LINE, "E   assert 5 == 4")
        accepted_failures.accept(self.host.repo, HEAD_THROTTLED_LINE, "me", "throttled")
        failures = self.host.head_output(HEAD_THROTTLED_LINE, "E   assert 5 == 6")

        self.assertTrue(self.host.scoped_failures_pre_existing(failures))

    def test_an_unchanged_accepted_line_with_a_number_only_detail_change_passes(self):
        self.host.set_base("failed (exit 1)", BASE_THROTTLED_LINE, "E   retry after 12s")
        accepted_failures.accept(self.host.repo, BASE_THROTTLED_LINE, "me", "throttled")
        failures = self.host.head_output(BASE_THROTTLED_LINE, "E   retry after 7s")

        self.assertTrue(self.host.scoped_failures_pre_existing(failures))

    def test_an_unchanged_line_with_a_number_only_detail_change_blocks_without_a_row(self):
        self.host.set_base("failed (exit 1)", BASE_THROTTLED_LINE, "E   retry after 12s")
        failures = self.host.head_output(BASE_THROTTLED_LINE, "E   retry after 7s")

        self.assertFalse(self.host.scoped_failures_pre_existing(failures))

    def test_a_row_for_one_test_does_not_mask_another_tests_changed_detail(self):
        base_other = [NEW_FAILING_LINE, "E   assert 5 == 4"]
        self.host.set_base("failed (exit 1)", BASE_THROTTLED_LINE, "E   retry after 12s", *base_other)
        accepted_failures.accept(self.host.repo, HEAD_THROTTLED_LINE, "me", "throttled")
        failures = self.host.head_output(HEAD_THROTTLED_LINE, "E   retry after 7s", NEW_FAILING_LINE,
                                         "E   assert 5 == 6")

        self.assertFalse(self.host.scoped_failures_pre_existing(failures))

    def test_a_same_named_test_in_another_file_is_not_excused_by_a_row(self):
        accepted = "FAILED tests/a.py::test_x - HTTPError: 429"
        other = "FAILED tests/b.py::test_x - HTTPError: 429"
        base_log = ["=== FAILURES ===", "___ test_x ___", "E   HTTPError: retry after 12s",
                    "=== short test summary info ===", accepted, other]
        head_log = ["=== FAILURES ===", "___ test_x ___", "E   HTTPError: retry after 7s",
                    "=== short test summary info ===", accepted, other]
        self.host.set_base("failed (exit 1)", *base_log)
        accepted_failures.accept(self.host.repo, accepted, "me", "throttled")

        self.assertFalse(self.host.scoped_failures_pre_existing(self.host.head_output(*head_log)))

    def test_a_row_for_one_class_does_not_mask_another_classes_same_named_test(self):
        accepted = "FAILED tests/t.py::TestA::test_x - HTTPError: 429"
        other = "FAILED tests/t.py::TestB::test_x - AssertionError"
        base_log = ["=== FAILURES ===", "___ TestB.test_x ___", "E   AssertionError: 5 == 4",
                    "=== short test summary info ===", accepted, other]
        head_log = ["=== FAILURES ===", "___ TestB.test_x ___", "E   AssertionError: 5 == 6",
                    "=== short test summary info ===", accepted, other]
        self.host.set_base("failed (exit 1)", *base_log)
        accepted_failures.accept(self.host.repo, accepted, "me", "throttled")

        self.assertFalse(self.host.scoped_failures_pre_existing(self.host.head_output(*head_log)))

    def test_a_number_change_under_the_accepted_classs_header_passes_when_another_class_has_the_same_test_name(self):
        accepted = "FAILED tests/t.py::TestA::test_x - HTTPError: 429"
        other = "FAILED tests/t.py::TestB::test_x - AssertionError"
        base_log = ["=== FAILURES ===", "___ TestA.test_x ___", "E   HTTPError: retry after 12s",
                    "=== short test summary info ===", accepted, other]
        head_log = ["=== FAILURES ===", "___ TestA.test_x ___", "E   HTTPError: retry after 7s",
                    "=== short test summary info ===", accepted, other]
        self.host.set_base("failed (exit 1)", *base_log)
        accepted_failures.accept(self.host.repo, accepted, "me", "throttled")

        self.assertTrue(self.host.scoped_failures_pre_existing(self.host.head_output(*head_log)))

    def test_a_number_change_under_no_header_blocks_when_the_log_holds_a_pytest_header(self):
        accepted = "FAILED tests/t.py::TestA::test_x - HTTPError: 429"
        base_log = ["=== FAILURES ===", "___ TestA.test_x ___", "E   HTTPError: retry after 12s",
                    "=== short test summary info ===", "error: retry 3 of 5", accepted]
        head_log = ["=== FAILURES ===", "___ TestA.test_x ___", "E   HTTPError: retry after 12s",
                    "=== short test summary info ===", "error: retry 4 of 5", accepted]
        self.host.set_base("failed (exit 1)", *base_log)
        accepted_failures.accept(self.host.repo, accepted, "me", "throttled")

        self.assertFalse(self.host.scoped_failures_pre_existing(self.host.head_output(*head_log)))

    def test_a_steps_summary_passes_with_a_row_when_a_new_line_differs_only_by_numbers(self):
        self.host.set_base("failed (exit 1)", "waiting 3", "FAILED: lint")
        accepted_failures.accept(self.host.repo, "FAILED: lint", "me", "known")
        failures = self.host.head_output("waiting 4", "FAILED: lint")

        self.assertTrue(self.host.scoped_failures_pre_existing(failures))

    def test_a_steps_summary_blocks_with_a_row_when_a_line_is_new_to_the_log(self):
        self.host.set_base("failed (exit 1)", "FAILED: lint")
        accepted_failures.accept(self.host.repo, "FAILED: lint", "me", "known")
        failures = self.host.head_output("a note without an error marker", "FAILED: lint")

        self.assertFalse(self.host.scoped_failures_pre_existing(failures))

    def test_a_changed_assertion_in_a_test_with_no_row_blocks_in_pytest_layout(self):
        base_log = [
            "=== FAILURES ===", "___ test_one ___", "E   retry after 12s",
            "___ test_two ___", "E   AssertionError: 5 == 4",
            "=== short test summary info ===", BASE_THROTTLED_LINE, NEW_FAILING_LINE,
        ]
        head_log = [
            "=== FAILURES ===", "___ test_one ___", "E   retry after 7s",
            "___ test_two ___", "E   AssertionError: 5 == 6",
            "=== short test summary info ===", BASE_THROTTLED_LINE, NEW_FAILING_LINE,
        ]
        self.host.set_base("failed (exit 1)", *base_log)
        accepted_failures.accept(self.host.repo, BASE_THROTTLED_LINE, "me", "throttled")

        self.assertFalse(self.host.scoped_failures_pre_existing(self.host.head_output(*head_log)))

    def test_a_changed_number_under_the_accepted_test_header_passes_in_pytest_layout(self):
        base_log = ["=== FAILURES ===", "___ test_one ___", "E   retry after 12s",
                    "=== short test summary info ===", BASE_THROTTLED_LINE]
        head_log = ["=== FAILURES ===", "___ test_one ___", "E   retry after 7s",
                    "=== short test summary info ===", BASE_THROTTLED_LINE]
        self.host.set_base("failed (exit 1)", *base_log)
        accepted_failures.accept(self.host.repo, BASE_THROTTLED_LINE, "me", "throttled")

        self.assertTrue(self.host.scoped_failures_pre_existing(self.host.head_output(*head_log)))

    def test_a_changed_number_under_a_setup_error_header_passes_with_a_row(self):
        error_line = "ERROR tests/t.py::test_one - HTTPError: 429"
        base_log = ["=== ERRORS ===", "___ ERROR at setup of test_one ___", "E   HTTPError: retry after 12s",
                    "=== short test summary info ===", error_line]
        head_log = ["=== ERRORS ===", "___ ERROR at setup of test_one ___", "E   HTTPError: retry after 7s",
                    "=== short test summary info ===", error_line]
        self.host.set_base("failed (exit 1)", *base_log)
        accepted_failures.accept(self.host.repo, error_line, "me", "throttled")

        self.assertTrue(self.host.scoped_failures_pre_existing(self.host.head_output(*head_log)))

    def test_a_parameter_with_a_space_still_matches_its_header(self):
        failing_line = "FAILED tests/t.py::test_x[a b] - HTTPError: 429"
        base_log = ["=== FAILURES ===", "___ test_x[a b] ___", "E   HTTPError: retry after 12s",
                    "=== short test summary info ===", failing_line]
        head_log = ["=== FAILURES ===", "___ test_x[a b] ___", "E   HTTPError: retry after 7s",
                    "=== short test summary info ===", failing_line]
        self.host.set_base("failed (exit 1)", *base_log)
        accepted_failures.accept(self.host.repo, failing_line, "me", "throttled")

        self.assertTrue(self.host.scoped_failures_pre_existing(self.host.head_output(*head_log)))

    def test_a_line_that_is_not_a_failing_line_is_refused(self):
        with self.assertRaises(accepted_failures.AcceptRefusedError) as raised:
            accepted_failures.accept(self.host.repo, "just some text", "me", "y")

        self.assertIn("FAILED <test> - <reason>", str(raised.exception))
        self.assertEqual([], accepted_failures.read_rows(self.host.repo))

    def test_a_torn_stored_row_is_refused_with_its_file_and_line(self):
        store = accepted_failures.store_path(self.host.repo)
        good = json.dumps({"line": "FAILED a", "by": "me", "reason": "x"})
        store.write_text(good + "\n" + '{"line": "FAILED b", "by"\n')

        with self.assertRaises(accepted_failures.AcceptRefusedError) as raised:
            accepted_failures.accept(self.host.repo, "FAILED c", "me", "y")

        self.assertIn(f"{store}:2", str(raised.exception))
        self.assertEqual(store.read_text(), good + "\n" + '{"line": "FAILED b", "by"\n')

    def test_a_non_object_stored_row_is_refused_with_its_file_and_line(self):
        store = accepted_failures.store_path(self.host.repo)
        store.write_text("[1, 2]\n")

        with self.assertRaises(accepted_failures.AcceptRefusedError) as raised:
            accepted_failures.read_rows(self.host.repo)

        self.assertIn(f"{store}:1", str(raised.exception))

    def test_a_stored_row_without_a_string_line_is_refused(self):
        store = accepted_failures.store_path(self.host.repo)
        store.write_text(json.dumps({"line": 5, "by": "me", "reason": "x"}) + "\n")

        with self.assertRaises(accepted_failures.AcceptRefusedError):
            accepted_failures.accepted_lines(self.host.repo)


class ScopedTestsStopHost(ScopedHost, review_loop_scoped_tests.ScopedTestRuns):
    """A ScopedHost whose scoped run is red with the throttled failing line."""
    gates_every_run = False

    def scoped_run_within(self, test_commands, deadline):
        failures = self.head_failures(HEAD_THROTTLED_LINE)
        return types.SimpleNamespace(tails=["tail text"], real_failures=failures, result="failed (exit 1)",
                                     summaries=[], gave_no_result=False)

    def autofix_touched_files(self):
        return False


class RedScopedRunStopTest(unittest.TestCase):
    def test_a_red_scoped_run_with_no_row_stops_with_the_accept_command(self):
        with tempfile.TemporaryDirectory() as folder:
            host = ScopedTestsStopHost(folder)

            result = host.run_test_commands([SCOPED_COMMAND])

        self.assertFalse(result)
        self.assertEqual(["critical-blocker"], [status for status, _findings in host.stops])
        finding = host.stops[0][1][0]
        self.assertIn("accepted_failures.py accept", finding)
        self.assertIn(HEAD_THROTTLED_LINE, finding)

    def test_a_torn_stored_row_stops_with_a_blocker_naming_the_file(self):
        with tempfile.TemporaryDirectory() as folder:
            host = ScopedTestsStopHost(folder)
            store = accepted_failures.store_path(host.repo)
            store.write_text('{"line": "FAILED b", "by"\n')

            result = host.run_test_commands([SCOPED_COMMAND])

        self.assertFalse(result)
        self.assertEqual(["critical-blocker"], [status for status, _findings in host.stops])
        self.assertIn(f"{store}:1", host.stops[0][1][0])

    def test_a_stored_row_without_a_string_line_stops_with_a_blocker(self):
        with tempfile.TemporaryDirectory() as folder:
            host = ScopedTestsStopHost(folder)
            store = accepted_failures.store_path(host.repo)
            store.write_text(json.dumps({"by": "me"}) + "\n")

            result = host.run_test_commands([SCOPED_COMMAND])

        self.assertFalse(result)
        self.assertEqual(["critical-blocker"], [status for status, _findings in host.stops])
        self.assertIn("no string `line`", host.stops[0][1][0])

    def test_the_accept_hint_offers_only_lines_accept_takes(self):
        lint_output = "F401 `os` imported but unused\n --> a.py:1:8\n" + HEAD_THROTTLED_LINE
        lines = accepted_failures.failing_lines_of(lint_output)

        self.assertEqual([HEAD_THROTTLED_LINE], lines)


class AcceptedFailuresCliTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.repo = pathlib.Path(folder.name) / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)

    def run_main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = accepted_failures.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_an_empty_reason_is_refused_and_keeps_no_row(self):
        code, _out, err = self.run_main("accept", "--repo", str(self.repo), "--line", HEAD_THROTTLED_LINE,
                                        "--by", "me", "--reason", " ")

        self.assertEqual(2, code)
        self.assertIn("refused", err)
        self.assertEqual([], accepted_failures.read_rows(self.repo))

    def test_an_accepted_row_is_listed_as_json(self):
        self.run_main("accept", "--repo", str(self.repo), "--line", HEAD_THROTTLED_LINE, "--by", "me",
                      "--reason", "throttled")

        code, out, _err = self.run_main("list", "--repo", str(self.repo))

        self.assertEqual(0, code)
        self.assertEqual({"line": HEAD_THROTTLED_LINE, "by": "me", "reason": "throttled"}, json.loads(out))

    def test_accept_prints_the_accepted_line_and_who(self):
        code, out, _err = self.run_main("accept", "--repo", str(self.repo), "--line", HEAD_THROTTLED_LINE,
                                        "--by", "me", "--reason", "throttled")

        self.assertEqual(0, code)
        self.assertEqual(f"accepted: {HEAD_THROTTLED_LINE} (by me)\n", out)

    def test_list_exits_2_on_a_torn_row(self):
        store = accepted_failures.store_path(self.repo)
        store.write_text('{"line": "FAILED b", "by"\n')

        code, _out, err = self.run_main("list", "--repo", str(self.repo))

        self.assertEqual(2, code)
        self.assertIn("refused", err)

    def test_a_folder_with_no_git_dir_is_refused(self):
        with tempfile.TemporaryDirectory() as bare:
            code, _out, err = self.run_main("accept", "--repo", bare, "--line", HEAD_THROTTLED_LINE, "--by", "me",
                                            "--reason", "y")

        self.assertEqual(2, code)
        self.assertIn("cannot find the git dir", err)


if __name__ == "__main__":
    unittest.main()
