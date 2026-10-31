import contextlib
import importlib.util
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import unittest.mock

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = pathlib.Path(os.environ.get("SCRIPT_UTILS_SCRIPT")
                      or REPO_ROOT / "claude" / ".claude" / "scripts" / "lib" / "script_utils.py")
sys.path.insert(0, str(SCRIPT.parent.parent / "telemetry"))
module_spec = importlib.util.spec_from_file_location("script_utils", SCRIPT)
script_utils = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(script_utils)


class TextBeforeMarkerTest(unittest.TestCase):
    def test_the_text_is_cut_at_the_first_marker_and_kept_whole_without_one(self):
        self.assertEqual("report", script_utils.text_before_marker("report--stamp one--stamp two", "--stamp"))
        self.assertEqual("report", script_utils.text_before_marker("report", "--stamp"))
        self.assertEqual("", script_utils.text_before_marker("--stamp only", "--stamp"))


class HeadCommitHelpersTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.repo = pathlib.Path(folder.name)
        self.env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                    "GIT_COMMITTER_EMAIL": "t@t"}
        self.git("init", "-q")
        (self.repo / "a.txt").write_text("a\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "first")
        self.first = self.git("rev-parse", "HEAD").strip()
        (self.repo / "b.txt").write_text("b\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "second")

    def git(self, *arguments):
        return subprocess.run(["git", *arguments], cwd=self.repo, check=True, env=self.env, capture_output=True,
                              text=True).stdout

    def test_head_descends_from_an_ancestor_and_not_from_a_commit_it_was_reset_past_or_an_unknown_one(self):
        second = self.git("rev-parse", "HEAD").strip()
        self.assertTrue(script_utils.head_descends_from(self.repo, self.first))
        self.git("reset", "-q", "--hard", "HEAD~1")
        self.assertFalse(script_utils.head_descends_from(self.repo, second))
        self.assertFalse(script_utils.head_descends_from(self.repo, "0" * 40))

    def test_head_blob_hashes_names_each_file_at_head_and_leaves_out_one_head_lacks(self):
        hashes = script_utils.head_blob_hashes(self.repo, ["a.txt", "missing.txt"])
        self.assertEqual({"a.txt": self.git("rev-parse", "HEAD:a.txt").strip()}, hashes)
        self.assertEqual({}, script_utils.head_blob_hashes(self.repo, []))


class PathIsUnderTest(unittest.TestCase):
    def test_a_path_is_under_its_prefix_or_equal_to_it_but_not_under_a_sibling_that_shares_the_start(self):
        self.assertTrue(script_utils.path_is_under("task", "task"))
        self.assertTrue(script_utils.path_is_under("task/notes.md", "task"))
        self.assertTrue(script_utils.path_is_under("task/notes.md", "task/"))
        self.assertFalse(script_utils.path_is_under("task-other.md", "task"))
        self.assertFalse(script_utils.path_is_under("tas", "task"))


class StateFilePathTest(unittest.TestCase):
    def test_every_character_outside_the_safe_set_becomes_an_underscore_and_the_suffix_is_added(self):
        cases = [
            ("session-1_a.b", ".jsonl", "/state/session-1_a.b.jsonl"),
            ("shop/feature x", ".json", "/state/shop_feature_x.json"),
            ("../escape", ".jsonl", "/state/.._escape.jsonl"),
        ]
        for name, suffix, expected in cases:
            with self.subTest(name=name):
                self.assertEqual(pathlib.Path(expected), script_utils.state_file_path("/state", name, suffix))


class DetailsWithOutcomeTest(unittest.TestCase):
    def test_only_the_entries_with_the_outcome_are_kept_in_map_order(self):
        outcomes = {"b": {"outcome": "x", "detail": "one"}, "a": {"outcome": "y", "detail": "two"},
                    "c": {"outcome": "x", "detail": "three"}}

        self.assertEqual(["b", "c"], list(script_utils.details_with_outcome(outcomes, "x")))
        self.assertEqual({"b": "one", "c": "three"}, script_utils.details_with_outcome(outcomes, "x"))
        self.assertEqual({}, script_utils.details_with_outcome(outcomes, "z"))
        self.assertEqual({}, script_utils.details_with_outcome({}, "x"))


class SubagentTypeTest(unittest.TestCase):
    def test_coder_types_match_each_coder_and_its_deep_variant_only(self):
        for name in ("coder", "coder-deep", "backend-coder", "frontend-coder-deep"):
            self.assertTrue(script_utils.CODERS.match(name), name)
        for name in ("code-reviewer", "coder-helper", "plan-coder", "Explore"):
            self.assertFalse(script_utils.CODERS.match(name), name)

    def test_reviewer_types_match_each_reviewer_and_its_deep_variant_only(self):
        for name in ("code-reviewer", "perf-reviewer-deep", "reviewer"):
            self.assertTrue(script_utils.REVIEWERS.match(name), name)
        for name in ("review-loop", "coder", "reviewer-notes", "Explore"):
            self.assertFalse(script_utils.REVIEWERS.match(name), name)


class FencedLineIndexesTest(unittest.TestCase):
    def test_lines_between_backtick_fences_and_the_fences_themselves_are_fenced(self):
        lines = ["# a", "```bash", "# not a heading", "```", "# b"]
        self.assertEqual({1, 2, 3}, script_utils.fenced_line_indexes(lines))

    def test_tilde_fence_is_closed_only_by_tildes(self):
        lines = ["~~~", "```", "# x", "~~~", "# y"]
        self.assertEqual({0, 1, 2, 3}, script_utils.fenced_line_indexes(lines))

    def test_a_longer_fence_is_not_closed_by_a_shorter_one(self):
        lines = ["````md", "```", "# x", "```", "````", "# y"]
        self.assertEqual({0, 1, 2, 3, 4}, script_utils.fenced_line_indexes(lines))

    def test_an_unclosed_fence_runs_to_the_end(self):
        self.assertEqual({1, 2}, script_utils.fenced_line_indexes(["# a", "```", "# b"]))

    def test_an_indented_fence_inside_a_list_item_counts(self):
        lines = ["- step", "    ```sh", "    # comment", "    ```", "# h"]
        self.assertEqual({1, 2, 3}, script_utils.fenced_line_indexes(lines))

    def test_text_with_no_fence_has_no_fenced_lines(self):
        self.assertEqual(set(), script_utils.fenced_line_indexes(["# a", "b `code` c"]))


class HeadingSectionIndexesTest(unittest.TestCase):
    def test_the_lines_under_the_heading_run_to_the_next_heading_of_its_level(self):
        lines = ["# t", "## Notes", "a", "## Other", "b"]
        self.assertEqual([2], script_utils.heading_section_indexes(lines, "Notes"))

    def test_a_deeper_heading_and_its_lines_stay_inside_the_section(self):
        lines = ["## Notes", "a", "#### Deep", "b", "## Other", "c"]
        self.assertEqual([1, 2, 3], script_utils.heading_section_indexes(lines, "Notes"))

    def test_a_higher_heading_ends_the_section(self):
        lines = ["### Notes", "a", "## Up", "b"]
        self.assertEqual([1], script_utils.heading_section_indexes(lines, "Notes"))

    def test_a_hash_line_inside_a_fence_is_not_a_heading_and_stays_in_the_section(self):
        lines = ["## Notes", "```", "## Other", "```", "tail", "## End"]
        self.assertEqual([1, 2, 3, 4], script_utils.heading_section_indexes(lines, "Notes"))

    def test_the_heading_text_must_match_exactly_and_every_matching_section_counts(self):
        lines = ["## Notes later", "a", "## Notes", "b", "## X", "## Notes", "c"]
        self.assertEqual([3, 6], script_utils.heading_section_indexes(lines, "Notes"))

    def test_text_with_no_such_heading_gives_no_lines(self):
        self.assertEqual([], script_utils.heading_section_indexes(["## A", "b"], "Notes"))


class TopLevelSectionsTest(unittest.TestCase):
    def test_only_two_hash_headings_outside_code_fences_start_a_section(self):
        lines = ["# Title", "## A", "### Deeper", "```", "## in a fence", "```", "text", "## B", "##C"]
        self.assertEqual([1, 7], script_utils.top_level_sections(lines))

    def test_text_with_no_section_gives_no_indexes(self):
        self.assertEqual([], script_utils.top_level_sections(["a", "# b"]))


class SubagentTranscriptPathTest(unittest.TestCase):
    def test_the_subagent_transcript_sits_in_a_folder_named_for_the_session_transcript(self):
        self.assertEqual("/t/s/subagents/agent-a1.jsonl", script_utils.subagent_transcript_path("/t/s.jsonl", "a1"))


class VisibleTextTest(unittest.TestCase):
    def test_a_line_without_comments_comes_back_whole(self):
        self.assertEqual(("plain text", False), script_utils.visible_text("plain text", False))

    def test_an_inline_comment_is_removed(self):
        self.assertEqual(("a  b", False), script_utils.visible_text("a <!-- x --> b", False))

    def test_an_unclosed_comment_hides_the_rest_and_stays_open(self):
        self.assertEqual(("a ", True), script_utils.visible_text("a <!-- x", False))

    def test_an_open_comment_closes_on_a_later_line(self):
        self.assertEqual((" tail", False), script_utils.visible_text("end --> tail", True))
        self.assertEqual(("", True), script_utils.visible_text("still inside", True))

    def test_a_comment_opener_inside_inline_code_opens_nothing(self):
        self.assertEqual(("write `<!--` to open", False), script_utils.visible_text("write `<!--` to open", False))

    def test_a_real_comment_after_an_inline_code_span_still_opens(self):
        self.assertEqual(("`a` ", True), script_utils.visible_text("`a` <!-- x", False))


class LinesAddedTest(unittest.TestCase):
    def test_a_new_line_is_added(self):
        self.assertEqual(["Also b."], script_utils.lines_added(["a", "c"], ["a", "Also b.", "c"]))

    def test_a_checkbox_tick_is_not_an_added_line(self):
        self.assertEqual([], script_utils.lines_added(["- [ ] check"], ["- [x] check"]))
        self.assertEqual([], script_utils.lines_added(["- [x] check"], ["- [X] check"]))

    def test_added_blank_lines_are_not_added_lines(self):
        self.assertEqual([], script_utils.lines_added(["a", "b"], ["a", "", "", "b"]))

    def test_whitespace_only_changes_are_not_added_lines(self):
        self.assertEqual([], script_utils.lines_added(["Do a."], ["Do a. "]))
        self.assertEqual([], script_utils.lines_added(["- x"], ["  - x"]))
        self.assertEqual([], script_utils.lines_added(["a  b"], ["a b"]))

    def test_a_reworded_line_is_added_in_its_new_form(self):
        self.assertEqual(["Do c."], script_utils.lines_added(["Do a."], ["Do c."]))

    def test_deleted_lines_add_nothing(self):
        self.assertEqual([], script_utils.lines_added(["a", "b"], ["a"]))


class UsageRequestedTest(unittest.TestCase):
    def test_only_an_exact_help_word_asks_for_usage(self):
        cases = [(["--help"], True), (["decide", "-h"], True), (["--helpful"], False), (["help"], False), ([], False)]
        for words, expected in cases:
            with self.subTest(words=words):
                self.assertEqual(expected, script_utils.usage_requested(words))


class WaitForTest(unittest.TestCase):
    def test_returns_the_value_the_check_finds_at_once(self):
        self.assertEqual("row", script_utils.wait_for(lambda: "row", 5, 0.01))

    def test_polls_until_the_check_finds_something(self):
        found = []
        threading.Timer(0.3, lambda: found.append("late")).start()
        result = script_utils.wait_for(lambda: found[0] if found else None, 5, 0.05)
        self.assertEqual("late", result)

    def test_gives_up_at_the_limit_with_none(self):
        started = time.monotonic()
        self.assertIsNone(script_utils.wait_for(lambda: None, 0.3, 0.05))
        self.assertLess(time.monotonic() - started, 2)

    def test_a_zero_limit_checks_once(self):
        calls = []
        self.assertIsNone(script_utils.wait_for(lambda: calls.append(1), 0, 0.05))
        self.assertEqual(1, len(calls))


class RunRetryingTest(unittest.TestCase):
    """A planted program that exits with the next code of a list on each run, or sleeps when the code is `hang`."""

    PROGRAM = (
        "import pathlib, sys, time\n"
        "folder = pathlib.Path(sys.argv[1])\n"
        "runs = len(list(folder.glob('run-*')))\n"
        "(folder / f'run-{runs}').write_text('')\n"
        "codes = (folder / 'codes').read_text().split()\n"
        "code = codes[min(runs, len(codes) - 1)]\n"
        "if code == 'hang':\n"
        "    time.sleep(30)\n"
        "print(f'run {runs} exit {code}')\n"
        "sys.exit(int(code))\n")

    def plant(self, codes):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = pathlib.Path(folder.name)
        (self.folder / "codes").write_text(" ".join(codes))
        (self.folder / "program.py").write_text(self.PROGRAM)
        self.sleeps = []
        return [sys.executable, str(self.folder / "program.py"), str(self.folder)]

    def runs(self):
        return len(list(self.folder.glob("run-*")))

    def run_retrying(self, argv, attempts=4, timeout_seconds=10):
        return script_utils.run_retrying(argv, (75,), attempts, 2, timeout_seconds, sleep=self.sleeps.append)

    def test_a_clean_run_is_not_repeated(self):
        done = self.run_retrying(self.plant(["0"]))
        self.assertEqual((0, 1, []), (done.returncode, self.runs(), self.sleeps))
        self.assertEqual("run 0 exit 0\n", done.stdout)

    def test_a_retry_code_is_run_again_with_a_growing_pause_until_it_clears(self):
        done = self.run_retrying(self.plant(["75", "75", "0"]))
        self.assertEqual((0, 3, [2, 4]), (done.returncode, self.runs(), self.sleeps))

    def test_a_retry_code_on_the_last_attempt_is_returned_not_raised(self):
        done = self.run_retrying(self.plant(["75"]), attempts=3)
        self.assertEqual((75, 3, [2, 4]), (done.returncode, self.runs(), self.sleeps))

    def test_any_other_failure_is_returned_at_once_without_a_retry(self):
        done = self.run_retrying(self.plant(["1", "0"]))
        self.assertEqual((1, 1, []), (done.returncode, self.runs(), self.sleeps))

    def test_a_timed_out_run_is_run_again(self):
        done = self.run_retrying(self.plant(["hang", "0"]), timeout_seconds=1)
        self.assertEqual((0, 2, [2]), (done.returncode, self.runs(), self.sleeps))

    def test_a_timeout_on_the_last_attempt_raises(self):
        argv = self.plant(["hang"])
        with self.assertRaises(subprocess.TimeoutExpired):
            self.run_retrying(argv, attempts=2, timeout_seconds=1)
        self.assertEqual((2, [2]), (self.runs(), self.sleeps))


class AttemptsWithinTest(unittest.TestCase):
    def test_the_tries_are_the_most_whose_growing_pauses_fit_the_wait(self):
        cases = [(18, 3, 4), (90, 3, 8), (2, 3, 1), (3, 3, 2), (0, 3, 1), (83, 3, 7), (84, 3, 8)]
        for wait, backoff, expected in cases:
            with self.subTest(wait=wait, backoff=backoff):
                self.assertEqual(expected, script_utils.attempts_within(wait, backoff))


class FileTailTest(unittest.TestCase):
    def test_the_tail_is_the_last_lines_cut_to_the_last_characters_with_a_note_for_an_unreadable_or_empty_file(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = pathlib.Path(temp_dir.name) / "file.log"
        empty = pathlib.Path(temp_dir.name) / "empty.log"
        empty.write_text("")
        path.write_text("one\ntwo\nthree\nfour\n")

        self.assertEqual("three\nfour", script_utils.file_tail(path, 2, 100))
        self.assertEqual("ree\nfour", script_utils.file_tail(path, 2, 8))
        self.assertEqual("(log is empty)", script_utils.file_tail(empty, 2, 100))
        self.assertIn("log not readable", script_utils.file_tail(pathlib.Path(temp_dir.name) / "none.log", 2, 100))


class LedgerFailureReasonTest(unittest.TestCase):
    def test_the_reason_is_the_last_stderr_line_or_the_exit_code(self):
        cases = [("first\nlast\n", "last"), ("", "exited 3"), ("\n  \n", "exited 3")]
        for stderr, expected in cases:
            with self.subTest(stderr=stderr):
                done = subprocess.CompletedProcess(["ledger"], 3, stdout="", stderr=stderr)
                self.assertEqual(expected, script_utils.ledger_failure_reason(done))


class ReadLedgerTest(unittest.TestCase):
    """A planted `ledger` that logs each call. The pause between tries is 0 unless a test sets it."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = pathlib.Path(folder.name)
        self.calls = self.folder / "calls"
        environment = unittest.mock.patch.dict(os.environ, {
            "PATH": os.pathsep.join([str(self.folder), "/usr/bin", "/bin"]),
            "CARGO_HOME": str(self.folder / "cargo"),
            script_utils.LEDGER_BACKOFF_ENV: "0", script_utils.LEDGER_CALL_TIMEOUT_ENV: "10"})
        environment.start()
        self.addCleanup(environment.stop)

    def plant(self, body):
        stub = self.folder / "ledger"
        stub.write_text(f'#!/bin/sh\necho x >> "{self.calls}"\ntries=$(wc -l < "{self.calls}")\n{body}')
        stub.chmod(0o755)

    def tries(self):
        return len(self.calls.read_text().split())

    def test_a_ledger_busy_for_six_tries_is_waited_for_and_its_answer_returned(self):
        self.plant('[ "$tries" -le 6 ] && { echo "cache behind" >&2; exit 75; }\necho "the answer: $*"\n')

        done = script_utils.read_ledger(["yield", "--deferred"])

        self.assertEqual((0, "the answer: yield --deferred\n", 7), (done.returncode, done.stdout, self.tries()))

    def test_another_failure_is_returned_after_one_try(self):
        self.plant('echo "broken schema" >&2\nexit 1\n')

        done = script_utils.read_ledger(["yield", "--deferred"])

        self.assertEqual((1, "broken schema\n", 1), (done.returncode, done.stderr, self.tries()))

    def test_a_ledger_that_stays_busy_raises_with_its_stderr_line_and_the_wait(self):
        self.plant('echo "cache behind: too many shard rows are not loaded yet; retry" >&2\nexit 75\n')

        with self.assertRaises(script_utils.LedgerBusyError) as raised:
            script_utils.read_ledger(["yield", "--deferred"])

        self.assertEqual("ledger yield --deferred: cache behind: too many shard rows are not loaded yet; retry "
                         "(0 s of pauses)", str(raised.exception))
        self.assertEqual(8, self.tries())

    def test_the_wait_in_the_message_is_the_sum_of_the_pauses(self):
        busy = subprocess.CompletedProcess(["ledger"], 75, "", "cache behind\n")
        with unittest.mock.patch.dict(os.environ, {script_utils.LEDGER_BACKOFF_ENV: "3"}), \
                unittest.mock.patch.object(script_utils, "run_retrying", return_value=busy) as retrying:
            self.plant("exit 75\n")
            with self.assertRaises(script_utils.LedgerBusyError) as raised:
                script_utils.read_ledger(["yield", "--deferred"])

        self.assertEqual("ledger yield --deferred: cache behind (84 s of pauses)", str(raised.exception))
        self.assertEqual(8, retrying.call_args.args[2])

    def test_a_ledger_that_never_answers_raises_busy(self):
        self.plant("exec sleep 30\n")
        os.environ[script_utils.LEDGER_CALL_TIMEOUT_ENV] = "0.3"

        with self.assertRaises(script_utils.LedgerBusyError) as raised:
            script_utils.read_ledger(["yield", "--deferred"])

        self.assertIn("no answer within 0.3 s", str(raised.exception))
        self.assertEqual(8, self.tries())

    def test_no_ledger_on_path_or_in_the_cargo_folder_raises_not_installed(self):
        with self.assertRaises(script_utils.LedgerNotInstalledError):
            script_utils.read_ledger(["yield", "--deferred"])

    def test_the_ledger_in_the_cargo_bin_folder_answers_when_path_has_none(self):
        cargo_bin = self.folder / "cargo" / "bin"
        cargo_bin.mkdir(parents=True)
        stub = cargo_bin / "ledger"
        stub.write_text('#!/bin/sh\necho "cargo ledger: $*"\n')
        stub.chmod(0o755)

        done = script_utils.read_ledger(["yield", "--deferred"])

        self.assertEqual((0, "cargo ledger: yield --deferred\n"), (done.returncode, done.stdout))


class MissingLedgerWarningTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = pathlib.Path(folder.name)
        environment = unittest.mock.patch.dict(os.environ, {
            "PATH": os.pathsep.join([str(self.folder), "/usr/bin", "/bin"]),
            "CARGO_HOME": str(self.folder / "cargo"), "CLAUDE_TOOLKIT_TELEMETRY": "1"})
        environment.start()
        self.addCleanup(environment.stop)

    def test_telemetry_on_with_no_ledger_names_the_jsonl_fallback(self):
        warning = script_utils.missing_ledger_warning()

        self.assertIn("No ledger found on PATH or in the cargo bin folder ($CARGO_HOME/bin, default ~/.cargo/bin)",
                      warning)
        self.assertIn("jsonl files under ~/.claude", warning)

    def test_no_ledger_when_cargo_home_and_home_are_unset_gives_none_not_a_guess(self):
        del os.environ["CARGO_HOME"]
        os.environ["HOME"] = ""

        self.assertIsNone(script_utils.ledger_bin())

    def test_a_directory_named_ledger_in_the_cargo_bin_folder_is_not_a_ledger(self):
        (self.folder / "cargo" / "bin" / "ledger").mkdir(parents=True)

        self.assertIsNone(script_utils.ledger_bin())

    def test_telemetry_off_gives_no_warning(self):
        os.environ["CLAUDE_TOOLKIT_TELEMETRY"] = "0"

        self.assertIsNone(script_utils.missing_ledger_warning())

    def test_a_ledger_on_path_gives_no_warning(self):
        stub = self.folder / "ledger"
        stub.write_text("#!/bin/sh\n")
        stub.chmod(0o755)

        self.assertIsNone(script_utils.missing_ledger_warning())


class RunProcessTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = pathlib.Path(folder.name)

    def test_a_list_command_returns_its_exit_code_and_both_streams(self):
        code, stdout, stderr = script_utils.run_process(
            [sys.executable, "-c", "import sys; print('out'); print('err', file=sys.stderr); sys.exit(3)"],
            self.folder)
        self.assertEqual((3, "out\n", "err\n"), (code, stdout, stderr))

    def test_a_string_command_runs_in_the_shell_in_the_given_folder(self):
        code, stdout, _ = script_utils.run_process("pwd && echo $((1 + 2))", self.folder)
        self.assertEqual(0, code)
        self.assertEqual([str(self.folder.resolve()), "3"], stdout.split())

    def test_stdin_reaches_the_command(self):
        command = [sys.executable, "-c", "import sys; print(sys.stdin.read().upper())"]
        code, stdout, _ = script_utils.run_process(command, self.folder, stdin="hello")
        self.assertEqual((0, "HELLO\n"), (code, stdout))

    def test_a_command_that_outlives_the_timeout_returns_no_exit_code_with_what_it_printed(self):
        started = time.monotonic()
        code, stdout, _ = script_utils.run_process("echo before; sleep 30", self.folder, timeout=1)
        self.assertIsNone(code)
        self.assertEqual("before\n", stdout)
        self.assertLess(time.monotonic() - started, 10)

    def test_a_timeout_kills_a_child_that_holds_the_pipes_open(self):
        marker = self.folder / "survived"
        command = f"(sleep 3; touch {marker}) & wait"
        code, _, _ = script_utils.run_process(command, self.folder, timeout=1)
        self.assertIsNone(code)
        time.sleep(3.5)
        self.assertFalse(marker.exists())


class GitOutputTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.repo = pathlib.Path(folder.name)
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)

    def test_stdout_comes_back_without_its_trailing_newline(self):
        top = script_utils.git_output(self.repo, "rev-parse", "--show-toplevel")
        self.assertEqual(str(self.repo.resolve()), top)

    def test_stderr_of_a_command_that_succeeds_is_not_part_of_the_answer(self):
        self.assertEqual("", script_utils.git_output(self.repo, "checkout", "-q", "-b", "topic"))
        self.assertEqual("", script_utils.git_output(self.repo, "checkout", "-b", "other"))

    def test_a_failing_command_a_folder_outside_any_repo_and_a_missing_folder_give_none(self):
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)

        self.assertIsNone(script_utils.git_output(self.repo, "rev-parse", "--verify", "-q", "HEAD"))
        self.assertIsNone(script_utils.git_output(outside.name, "rev-parse", "--show-toplevel"))
        self.assertIsNone(script_utils.git_output(self.repo / "missing", "status"))

    def test_a_non_ascii_name_comes_back_unquoted(self):
        (self.repo / "café.txt").write_text("x\n")
        self.assertEqual("café.txt", script_utils.git_output(self.repo, "ls-files", "--others"))

    @unittest.skipUnless(sys.platform.startswith("linux"), "only Linux file systems take a name that is not UTF-8")
    def test_a_name_that_is_not_utf8_round_trips_through_fsencode(self):
        name = b"caf\xe9.txt"
        (self.repo / os.fsdecode(name)).write_text("x\n")

        listing = script_utils.git_output(self.repo, "ls-files", "--others", "-z")

        self.assertEqual(name + b"\0", os.fsencode(listing))


class JoinedDistinctTest(unittest.TestCase):
    def test_equal_values_appear_once_and_empty_values_are_dropped(self):
        self.assertEqual("Q? (a.ts:3)", script_utils.joined_distinct(["Q? (a.ts:3)", "", "Q? (a.ts:3)"]))

    def test_different_values_are_joined_in_order(self):
        self.assertEqual("a - b", script_utils.joined_distinct(["a", "b"]))
        self.assertEqual("a | b", script_utils.joined_distinct(["a", "b"], " | "))


class HangingIndentLinesTest(unittest.TestCase):
    def test_the_first_line_takes_the_lead_and_later_lines_the_indent(self):
        self.assertEqual(["1. a", "   b", "   c"], script_utils.hanging_indent_lines("1. ", "a\nb\nc"))
        self.assertEqual(["- a", "  b"], script_utils.hanging_indent_lines("- ", "a\nb", indent="  "))

    def test_empty_text_gives_no_lines(self):
        self.assertEqual([], script_utils.hanging_indent_lines("1. ", ""))

    def test_a_value_that_is_not_text_prints_as_text(self):
        self.assertEqual(["- 5"], script_utils.hanging_indent_lines("- ", 5))


class ContainsIgnoringWhitespaceTest(unittest.TestCase):
    def test_a_part_that_differs_only_in_line_breaks_and_indentation_is_contained(self):
        self.assertTrue(script_utils.contains_ignoring_whitespace("intro\n\n  a   b\nc\n", "a b\n   c"))

    def test_a_part_with_a_different_word_is_not_contained(self):
        self.assertFalse(script_utils.contains_ignoring_whitespace("intro a b", "a b c"))

    def test_an_empty_or_blank_part_is_not_contained(self):
        self.assertFalse(script_utils.contains_ignoring_whitespace("anything", " \n"))


class HasWhitespaceTest(unittest.TestCase):
    def test_a_space_tab_or_newline_anywhere_counts(self):
        for text in ("two words", "tab\there", "line\nbreak", " leading", "trailing "):
            self.assertTrue(script_utils.has_whitespace(text), repr(text))

    def test_text_with_none_does_not(self):
        for text in ("docs/plans/orders/spec.md", "ABC-400", ""):
            self.assertFalse(script_utils.has_whitespace(text), repr(text))


class WordsOfArgumentsTest(unittest.TestCase):
    def test_one_argument_with_spaces_is_split_at_them(self):
        self.assertEqual(["fix", "the", "typo"], script_utils.words_of_arguments(["fix  the typo"]))

    def test_several_arguments_are_kept_as_given_even_when_one_holds_spaces(self):
        self.assertEqual(["fix", "the typo"], script_utils.words_of_arguments(["fix", "the typo"]))

    def test_no_arguments_give_no_words(self):
        self.assertEqual([], script_utils.words_of_arguments([]))

    def test_a_tuple_of_arguments_gives_a_list(self):
        self.assertEqual(["a", "b"], script_utils.words_of_arguments(("a", "b")))


class PreToolUseDenyTest(unittest.TestCase):
    def test_prints_one_json_line_that_denies_the_call_with_the_reason(self):
        printed = io.StringIO()

        with contextlib.redirect_stdout(printed):
            script_utils.pre_tool_use_deny("Read the file first.")

        printed_lines = printed.getvalue().splitlines()
        denial = json.loads(printed.getvalue())
        self.assertEqual({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                 "permissionDecisionReason": "Read the file first."}}, denial)
        self.assertEqual(1, len(printed_lines))


class SortableUniqueIdTest(unittest.TestCase):
    def test_ids_made_in_one_second_differ_and_later_seconds_sort_later(self):
        first = script_utils.sortable_unique_id(1000)
        self.assertNotEqual(first, script_utils.sortable_unique_id(1000))
        self.assertLess(first, script_utils.sortable_unique_id(1001))


class LastChangeNsTest(unittest.TestCase):
    def test_a_renamed_file_with_an_old_mtime_reports_its_newer_ctime(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        source = pathlib.Path(temp_dir.name) / "source.md"
        source.write_text("x\n")
        os.utime(source, (50, 50))
        moved = pathlib.Path(temp_dir.name) / "moved.md"
        source.rename(moved)

        self.assertEqual(50 * 10**9, moved.stat().st_mtime_ns)
        self.assertGreater(script_utils.last_change_ns(moved), 50 * 10**9)

    def test_a_file_whose_mtime_was_set_into_the_future_reports_the_mtime(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = pathlib.Path(temp_dir.name) / "future.md"
        path.write_text("x\n")
        future = time.time() + 1000
        os.utime(path, (future, future))

        self.assertEqual(path.stat().st_mtime_ns, script_utils.last_change_ns(path))


class TextAndFileHelpersTest(unittest.TestCase):
    def test_one_line_collapses_whitespace_and_cuts(self):
        self.assertEqual(script_utils.one_line("a \n  b\t c"), "a b c")
        self.assertEqual(script_utils.one_line("abcdef", 3), "abc")

    def test_unquote_strips_one_matching_pair_only(self):
        self.assertEqual(script_utils.unquote(' "x" '), "x")
        self.assertEqual(script_utils.unquote("'x'"), "x")
        self.assertEqual(script_utils.unquote("\"x'"), "\"x'")
        self.assertEqual(script_utils.unquote('""x""'), '"x"')

    def test_first_number(self):
        self.assertEqual(script_utils.first_number("2 of 3"), 2)
        self.assertIsNone(script_utils.first_number("two"))
        self.assertIsNone(script_utils.first_number(None))

    def test_unquoted_mask_blanks_quoted_spans(self):
        masked = script_utils.unquoted_mask('a: "b: c" d')
        self.assertNotIn("b: c", masked)
        self.assertEqual(len(masked), len('a: "b: c" d'))

    def test_top_level_braces_splits_flow_lists_and_ignores_quoted_braces(self):
        groups = script_utils.top_level_braces('{a: 1}, {b: {c: 2}}, {d: "}"}')
        self.assertEqual(groups, ["{a: 1}", "{b: {c: 2}}", '{d: "}"}'])

    def test_normalize_path_strips_ticks_dot_slash_and_line_suffix(self):
        self.assertEqual(script_utils.normalize_path("`./src/a.ts:12-20`"), "src/a.ts")
        self.assertEqual(script_utils.normalize_path("a.ts:1, b.ts:2"), "a.ts")
        self.assertEqual(script_utils.normalize_path("src/a.ts"), "src/a.ts")

    def test_split_location_returns_path_and_first_line(self):
        self.assertEqual(script_utils.split_location("a.ts:12-20, b.ts:3"), ("a.ts", 12))
        self.assertEqual(script_utils.split_location("a.ts"), ("a.ts", 0))
        self.assertEqual(script_utils.split_location("a.ts:x"), ("a.ts", 0))

    def test_paths_named_collects_the_first_path_and_every_path_line_token_once(self):
        paths = script_utils.paths_named("./a.ts:1", "see b.ts:2 and `c.ts:3-4` and a.ts:9", None)
        self.assertEqual(paths, ["a.ts", "b.ts", "c.ts"])

    def test_append_jsonl_and_read_jsonl_round_trip_and_skip_torn_lines(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = pathlib.Path(directory.name) / "deep" / "rows.jsonl"
        script_utils.append_jsonl(path, {"n": 1})
        script_utils.append_jsonl(path, {"n": 2})
        with open(str(path), "a") as handle:
            handle.write('{"torn": \n[1]\n')
        self.assertEqual(script_utils.read_jsonl(path), [{"n": 1}, {"n": 2}])
        self.assertEqual(script_utils.read_jsonl(path.parent / "missing.jsonl"), [])

    def test_concurrent_appends_never_interleave_inside_a_row(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = pathlib.Path(directory.name) / "rows.jsonl"
        threads = [threading.Thread(target=lambda n=n: [script_utils.append_jsonl(path, {"n": n, "pad": "x" * 500})
                                                          for _ in range(20)]) for n in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(len(script_utils.read_jsonl(path)), 160)


class NearestFileUpwardTest(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.root = pathlib.Path(temp_dir.name) / "repo"
        (self.root / "pkg/src/deep").mkdir(parents=True)
        (self.root / "pkg/package.json").write_text("{}")

    def test_the_nearest_file_above_the_start_is_found(self):
        found = script_utils.nearest_file_upward(self.root / "pkg/src/deep", "package.json", self.root)

        self.assertEqual(self.root / "pkg/package.json", found)

    def test_a_file_in_the_stop_directory_itself_is_found(self):
        (self.root / "Cargo.toml").write_text("")

        found = script_utils.nearest_file_upward(self.root / "other", "Cargo.toml", self.root)

        self.assertEqual(self.root / "Cargo.toml", found)

    def test_the_search_stops_at_the_stop_directory(self):
        found = script_utils.nearest_file_upward(self.root / "pkg/src", "package.json", self.root / "pkg/src")

        self.assertIsNone(found)

    def test_a_start_that_climbs_out_through_dot_dot_finds_nothing_in_the_sibling_tree(self):
        sibling = self.root.parent / "sibling"
        sibling.mkdir()
        (sibling / "package.json").write_text("{}")

        found = script_utils.nearest_file_upward(self.root / "../sibling", "package.json", self.root)

        self.assertIsNone(found)


class DirectoryRelativeToTest(unittest.TestCase):
    def test_a_directory_under_the_root_reads_as_its_relative_path(self):
        root = pathlib.Path("/work/repo")

        self.assertEqual("crates/api", script_utils.directory_relative_to(root, root / "crates/api"))

    def test_the_root_itself_reads_as_empty_text(self):
        root = pathlib.Path("/work/repo")

        self.assertEqual("", script_utils.directory_relative_to(root, root))


class IsExecutableFileInsideTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = pathlib.Path(directory.name) / "root"
        (self.root / "bin").mkdir(parents=True)

    def make_file(self, path, mode):
        path.write_text("#!/bin/sh\n")
        path.chmod(mode)
        return path

    def test_an_executable_file_under_the_root_is_one_by_a_relative_or_absolute_path(self):
        tool = self.make_file(self.root / "bin" / "tool", 0o755)

        for path in ("bin/tool", "./bin/tool", "bin/../bin/tool", str(tool)):
            with self.subTest(path=path):
                self.assertTrue(script_utils.is_executable_file_inside(self.root, path))

    def test_the_root_may_be_given_as_text(self):
        self.make_file(self.root / "bin" / "tool", 0o755)

        self.assertTrue(script_utils.is_executable_file_inside(str(self.root), "bin/tool"))

    def test_a_file_without_the_execute_bit_a_folder_and_a_missing_file_are_not_one(self):
        self.make_file(self.root / "bin" / "plain", 0o644)

        for path in ("bin/plain", "bin", "bin/missing"):
            with self.subTest(path=path):
                self.assertFalse(script_utils.is_executable_file_inside(self.root, path))

    def test_a_path_that_leaves_the_root_by_dots_by_a_link_or_by_an_absolute_path_is_not_one(self):
        outside = self.make_file(self.root.parent / "outside-tool", 0o755)
        (self.root / "bin" / "link").symlink_to(outside)

        for path in ("../outside-tool", "bin/link", str(outside)):
            with self.subTest(path=path):
                self.assertFalse(script_utils.is_executable_file_inside(self.root, path))


class InsideGitWorkTreeTest(unittest.TestCase):
    def folder(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        return pathlib.Path(temp_dir.name)

    def test_a_file_in_a_repo_is_inside_and_a_file_outside_any_repo_is_not(self):
        repo = self.folder()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        (repo / "a.py").write_text("x\n")
        elsewhere = self.folder()
        (elsewhere / "b.py").write_text("x\n")

        self.assertTrue(script_utils.inside_git_work_tree(str(repo / "a.py")))
        self.assertFalse(script_utils.inside_git_work_tree(str(elsewhere / "b.py")))

    def test_a_path_in_folders_that_do_not_exist_yet_is_judged_from_the_nearest_existing_parent(self):
        repo = self.folder()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        elsewhere = self.folder()

        self.assertTrue(script_utils.inside_git_work_tree(str(repo / "new" / "deeper" / "a.py")))
        self.assertFalse(script_utils.inside_git_work_tree(str(elsewhere / "new" / "deeper" / "b.py")))

    def test_when_git_cannot_run_a_dot_git_entry_in_a_parent_decides(self):
        repo = self.folder()
        (repo / ".git").mkdir()
        (repo / "src").mkdir()
        elsewhere = self.folder()

        with unittest.mock.patch.dict(os.environ, {"PATH": str(self.folder())}):
            self.assertTrue(script_utils.inside_git_work_tree(str(repo / "src" / "a.py")))
            self.assertFalse(script_utils.inside_git_work_tree(str(elsewhere / "b.py")))

    def test_a_file_symlink_from_outside_a_repo_into_a_repo_is_inside(self):
        repo = self.folder()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        (repo / "a.py").write_text("x\n")
        elsewhere = self.folder()
        link = elsewhere / "link.py"
        link.symlink_to(repo / "a.py")

        self.assertTrue(script_utils.inside_git_work_tree(str(link)))

    def test_a_repo_root_folder_passed_in_is_inside(self):
        repo = self.folder()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)

        self.assertTrue(script_utils.inside_git_work_tree(str(repo)))

    def test_when_git_refuses_the_folder_a_dot_git_entry_in_a_parent_decides(self):
        repo = self.folder()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        (repo / "a.py").write_text("x\n")
        elsewhere = self.folder()
        (elsewhere / "b.py").write_text("x\n")

        with unittest.mock.patch.dict(os.environ, {"GIT_TEST_ASSUME_DIFFERENT_OWNER": "1"}):
            refused = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=str(repo),
                                     capture_output=True)
            self.assertNotEqual(0, refused.returncode)
            self.assertTrue(script_utils.inside_git_work_tree(str(repo / "a.py")))
            self.assertFalse(script_utils.inside_git_work_tree(str(elsewhere / "b.py")))

    def test_the_inside_of_a_dot_git_folder_is_not_a_work_tree_with_or_without_git(self):
        repo = self.folder()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        hook = repo / ".git" / "hooks" / "x.sh"
        hook.write_text("x\n")

        self.assertFalse(script_utils.inside_git_work_tree(str(hook)))
        with unittest.mock.patch.dict(os.environ, {"PATH": str(self.folder())}):
            self.assertFalse(script_utils.inside_git_work_tree(str(hook)))

    def test_the_inside_of_a_bare_repo_is_not_a_work_tree_with_or_without_git(self):
        bare = self.folder()
        subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
        hook = bare / "hooks" / "x.sh"
        hook.write_text("x\n")

        self.assertFalse(script_utils.inside_git_work_tree(str(hook)))
        with unittest.mock.patch.dict(os.environ, {"PATH": str(self.folder())}):
            self.assertFalse(script_utils.inside_git_work_tree(str(hook)))


class IsGitIgnoredTest(unittest.TestCase):
    def folder(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return pathlib.Path(tmp.name)

    def test_an_ignored_path_is_ignored_even_before_it_exists_and_a_tracked_one_is_not(self):
        repo = self.folder()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        (repo / ".gitignore").write_text("probe/\n")
        (repo / "probe").mkdir()
        (repo / "probe" / "tracked.py").write_text("x\n")
        subprocess.run(["git", "-C", str(repo), "add", "-f", "probe/tracked.py"], check=True)

        self.assertTrue(script_utils.is_git_ignored(str(repo / "probe" / "new" / "a.py")))
        self.assertFalse(script_utils.is_git_ignored(str(repo / "probe" / "tracked.py")))
        self.assertFalse(script_utils.is_git_ignored(str(repo / "other.py")))

    def test_a_path_outside_a_repo_or_with_git_missing_is_not_ignored(self):
        repo = self.folder()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        (repo / ".gitignore").write_text("probe/\n")
        elsewhere = self.folder()

        self.assertFalse(script_utils.is_git_ignored(str(elsewhere / "a.py")))
        with unittest.mock.patch.dict(os.environ, {"PATH": str(self.folder())}):
            self.assertFalse(script_utils.is_git_ignored(str(repo / "probe" / "a.py")))


class LeadingEnvAssignmentsTest(unittest.TestCase):
    def test_a_line_gives_the_assignments_it_starts_with_as_written(self):
        self.assertEqual(["A=1", "B=/x/y.py"], script_utils.leading_env_assignments(["A=1 B=/x/y.py cargo test"]))

    def test_a_quoted_value_with_spaces_is_kept_whole(self):
        self.assertEqual(['GREETING="a b"'], script_utils.leading_env_assignments(['GREETING="a b" bash -c true']))

    def test_the_first_line_to_set_a_name_decides_its_value_and_order_is_first_seen(self):
        lines = ["B=1 make", "A=2 make", "B=3 make"]

        self.assertEqual(["B=1", "A=2"], script_utils.leading_env_assignments(lines))

    def test_a_line_with_no_leading_assignment_or_only_an_assignment_sets_nothing(self):
        lines = ["cargo test", "echo A=1", "A=1", "  ", ""]

        self.assertEqual([], script_utils.leading_env_assignments(lines))

    def test_an_assignment_after_the_command_is_not_a_leading_one(self):
        self.assertEqual([], script_utils.leading_env_assignments(["cargo test A=1", "cargo test A=1 --quiet"]))

    def test_no_lines_give_no_assignments(self):
        self.assertEqual([], script_utils.leading_env_assignments([]))

    def test_an_assignment_whose_value_the_shell_would_run_or_expand_is_not_a_setting(self):
        lines = ['n=$(ledger count) && test "$n" = 3', "S=...; cargo test", "PATH=/x/bin:$PATH cargo test",
                 "T=$(find . -name x) cargo test", "Q=`date` cargo test", "A=1&&cargo test", "B=x|cargo test",
                 "C=<in cargo test", 'D="a $HOME" cargo test', "E='a;b' cargo test", "F=1 && cargo test",
                 "G=1 ; cargo test", "H=1 | cat", "I=1 # note", "J=1 > out.txt", "K=1 (cargo test)", "L=1 {cargo test}",
                 "M=1 ! cargo test", 'N="x\\" cmd"', 'O="a\\b" cargo test', "X=~/a cargo test",
                 "X=a:~/b cargo test"]

        self.assertEqual([], script_utils.leading_env_assignments(lines))

    def test_a_literal_assignment_followed_by_one_the_shell_would_expand_gives_nothing(self):
        self.assertEqual([], script_utils.leading_env_assignments(["A=1 B=$(x) cargo test"]))

    def test_a_quoted_literal_value_and_a_path_value_are_settings(self):
        lines = ['LEDGER_ORACLE="on" cargo test', "ROOT='/x/y z' cargo test", "HOOK=/home/u/dotfiles/a.sh bash t.sh"]

        self.assertEqual(['LEDGER_ORACLE="on"', "ROOT='/x/y z'", "HOOK=/home/u/dotfiles/a.sh"],
                         script_utils.leading_env_assignments(lines))

    def test_a_span_of_only_assignments_is_prose_not_a_setting(self):
        self.assertEqual(
            [], script_utils.leading_env_assignments(["src=index pass=done", "src=index", "src=index ", "A=1  "])
        )

    def test_a_span_of_assignments_then_a_word_gives_the_assignments(self):
        self.assertEqual(["src=index"], script_utils.leading_env_assignments(["src=index pass"]))


class FirstCommandWordTest(unittest.TestCase):
    def test_the_word_after_the_leading_assignments_is_the_command(self):
        self.assertEqual("RUN", script_utils.first_command_word("FOO=1 RUN x"))
        self.assertEqual("cargo", script_utils.first_command_word("A=1 B='x y' cargo test"))
        self.assertEqual("npm", script_utils.first_command_word("  npm test "))
        self.assertEqual("cargo", script_utils.first_command_word("CARGO_BUILD_JOBS=4 cargo test --lib a::b"))
        self.assertEqual(["CARGO_BUILD_JOBS=4"], script_utils.leading_env_assignments(
            ["CARGO_BUILD_JOBS=4 cargo test --test side_streams"]))

    def test_a_command_of_only_blanks_has_no_first_word(self):
        self.assertEqual("", script_utils.first_command_word("   "))

    def test_the_command_after_an_assignment_that_runs_or_expands_something_is_the_command(self):
        commands = {"T=$(find . -name x) cargo test": "cargo",
                    "LEDGER_REAL_DOTFILES=$HOME/dotfiles cargo test --test x": "cargo",
                    "PATH=/x/bin:$PATH cargo test": "cargo",
                    'DATABASE_URL="$TEST_DB" pytest -q': "pytest",
                    "A=1 B=$(x) C='y z' make all": "make"}
        for command, word in commands.items():
            with self.subTest(command=command):
                self.assertEqual(word, script_utils.first_command_word(command))

    def test_an_assignment_followed_by_a_control_operator_has_no_command_after_it(self):
        for command in ("A=1 && cargo test", "A=1 ; cargo test", "A=1 | cat", "A=1 # note", "S=...; cargo test"):
            with self.subTest(command=command):
                self.assertEqual(command, script_utils.without_leading_env_assignments(command))

    def test_the_command_after_the_assignments_is_given_back(self):
        self.assertEqual("npm test", script_utils.without_leading_env_assignments(" CI=1 npm test"))
        self.assertEqual("npm test", script_utils.without_leading_env_assignments("npm test"))
        self.assertEqual("cargo test", script_utils.without_leading_env_assignments('PATH=/x:$PATH A="$B" cargo test'))


class BacktickedSpansTest(unittest.TestCase):
    def test_backticked_spans_are_the_text_between_backticks_in_order(self):
        self.assertEqual(["a b", "c"], script_utils.backticked_spans("x `a b` y `c` z"))
        self.assertEqual([], script_utils.backticked_spans("no code here"))


class WriteTextAtomicallyTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.folder = pathlib.Path(directory.name)

    def test_the_text_replaces_the_old_file_and_no_temp_file_stays(self):
        target = self.folder / "state.json"
        target.write_text("old")

        script_utils.write_text_atomically(target, "new")

        self.assertEqual("new", target.read_text())
        self.assertEqual(["state.json"], sorted(path.name for path in self.folder.iterdir()))

    def test_a_new_file_gets_the_mode_that_write_text_gives_under_the_umask(self):
        for umask, expected_mode in ((0o022, 0o644), (0o077, 0o600), (0o002, 0o664)):
            with self.subTest(umask=oct(umask)):
                target = self.folder / f"state-{umask:o}.json"
                previous_umask = os.umask(umask)
                try:
                    script_utils.write_text_atomically(target, "new")
                finally:
                    os.umask(previous_umask)

                self.assertEqual(expected_mode, target.stat().st_mode & 0o777)

    def test_an_existing_file_keeps_its_mode(self):
        for mode in (0o600, 0o664, 0o755):
            with self.subTest(mode=oct(mode)):
                target = self.folder / f"state-{mode:o}.json"
                target.write_text("old")
                target.chmod(mode)

                script_utils.write_text_atomically(target, "new")

                self.assertEqual("new", target.read_text())
                self.assertEqual(mode, target.stat().st_mode & 0o777)

    def test_a_failed_replace_keeps_the_old_file_and_removes_the_temp_file(self):
        target = self.folder / "state.json"
        target.write_text("old")

        with unittest.mock.patch("os.replace", side_effect=OSError("disk full")), self.assertRaises(OSError):
            script_utils.write_text_atomically(target, "new")

        self.assertEqual("old", target.read_text())
        self.assertEqual(["state.json"], sorted(path.name for path in self.folder.iterdir()))


class AgentTranscriptPathTest(unittest.TestCase):
    def test_the_path_the_event_names_wins_over_the_one_built_from_the_session_transcript(self):
        named = {"agent_transcript_path": "/t/named.jsonl", "transcript_path": "/t/s.jsonl", "agent_id": "a1"}
        built = {"transcript_path": "/t/s.jsonl", "agent_id": "a1"}
        self.assertEqual("/t/named.jsonl", script_utils.agent_transcript_path(named))
        self.assertEqual("/t/s/subagents/agent-a1.jsonl", script_utils.agent_transcript_path(built))


class PopOptionTest(unittest.TestCase):
    def test_flag_and_value_are_removed_wherever_they_sit(self):
        cases = [
            ("flag first", ["--by", "session", "accepted"], (["accepted"], "session")),
            ("flag last with value", ["accepted", "--by", "user"], (["accepted"], "user")),
            ("flag in the middle", ["a", "--by", "x", "b"], (["a", "b"], "x")),
            ("flag absent", ["a", "b"], (["a", "b"], None)),
            ("flag with no value", ["a", "--by"], (["a"], "")),
        ]
        for message, arguments, expected in cases:
            with self.subTest(message):
                self.assertEqual(expected, script_utils.pop_option(arguments, "--by"))

    def test_the_given_list_is_not_changed(self):
        arguments = ["a", "--by", "x"]

        script_utils.pop_option(arguments, "--by")

        self.assertEqual(["a", "--by", "x"], arguments)

    def test_pop_repeated_option_takes_every_value_in_order(self):
        cases = [
            ("two values", ["pass", "--e", "a b", "--e", "c"], (["pass"], ["a b", "c"])),
            ("flag absent", ["pass"], (["pass"], [])),
            ("flag with no value", ["pass", "--e"], (["pass"], [""])),
        ]
        for message, arguments, expected in cases:
            with self.subTest(message):
                self.assertEqual(expected, script_utils.pop_repeated_option(arguments, "--e"))


class PreloadedSkillsPromptTest(unittest.TestCase):
    def claude_home(self, agent_text, skill_texts):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        home = pathlib.Path(folder.name)
        (home / "agents").mkdir()
        (home / "agents" / "coder.md").write_text(agent_text)
        for name, skill_text in skill_texts.items():
            (home / "skills" / name).mkdir(parents=True)
            (home / "skills" / name / "SKILL.md").write_text(skill_text)
        return home

    def test_each_preloaded_skill_comes_without_its_frontmatter_under_its_base_directory(self):
        skill_texts = {"coder-core": "---\nname: coder-core\n---\n\n# Core\nRule one.\n", "extra": "# Extra\n"}
        home = self.claude_home("---\nname: coder\nskills:\n  - coder-core\n  - extra\n---\n\nBody.\n", skill_texts)

        prompt = script_utils.preloaded_skills_prompt("coder", home)

        self.assertEqual(f"Base directory for this skill: {home}/skills/coder-core\n\n# Core\nRule one.\n\n"
                         f"Base directory for this skill: {home}/skills/extra\n\n# Extra", prompt)

    def test_an_inline_skills_value_raises(self):
        with self.assertRaises(ValueError):
            script_utils.frontmatter_skills("---\nskills: [coder-core]\n---\n")

    def test_an_inline_skills_value_raises_naming_the_agent_file(self):
        home = self.claude_home("---\nname: coder\nskills: [coder-core]\n---\n\nBody.\n", {})

        with self.assertRaises(ValueError) as raised:
            script_utils.preloaded_skills_prompt("coder", home)

        self.assertIn(str(home / "agents" / "coder.md"), str(raised.exception))

    def test_a_missing_skill_raises_naming_the_agent_file_and_the_skill_path(self):
        home = self.claude_home("---\nname: coder\nskills:\n  - gone\n---\n\nBody.\n", {})

        with self.assertRaises(FileNotFoundError) as raised:
            script_utils.preloaded_skills_prompt("coder", home)

        self.assertIn(str(home / "agents" / "coder.md"), str(raised.exception))
        self.assertIn(str(home / "skills" / "gone" / "SKILL.md"), str(raised.exception))

    def test_no_skills_key_or_no_agent_file_gives_no_prompt(self):
        home = self.claude_home("---\nname: coder\n---\n\nBody.\n", {})

        self.assertEqual("", script_utils.preloaded_skills_prompt("coder", home))
        self.assertEqual("", script_utils.preloaded_skills_prompt("code-reviewer", home))
        self.assertEqual([], script_utils.frontmatter_skills("---\nname: coder\n---\n\nskills:\n  - body-text\n"))

    def test_json_string_list_reads_only_a_json_list_of_strings(self):
        self.assertEqual(["a", "b"], script_utils.json_string_list('["a", "b"]'))
        self.assertEqual([], script_utils.json_string_list("[]"))
        for text in ("not json", '["a", 1]', '{"a": "b"}', '"a"', "null"):
            with self.subTest(text):
                self.assertIsNone(script_utils.json_string_list(text))


class IsBlockerTest(unittest.TestCase):
    def test_a_mapping_is_a_blocker_only_when_its_blocker_field_reads_true_or_yes(self):
        for value in (True, "true", "Yes", " YES "):
            with self.subTest(value=value):
                self.assertTrue(script_utils.is_blocker({"blocker": value}))
        for item in ({"blocker": False}, {"blocker": "no"}, {}, "blocker: yes", None):
            with self.subTest(item=item):
                self.assertFalse(script_utils.is_blocker(item))


class EndsOnApiErrorTest(unittest.TestCase):
    def test_only_a_last_record_flagged_as_an_api_error_counts(self):
        fixture = pathlib.Path(__file__).resolve().parent / "fixtures" / "subagent_api_error_last_record.json"
        error = json.dumps(json.loads(fixture.read_text(encoding="utf-8")))
        work = json.dumps({"type": "assistant"})
        cases = {"error last": ([work, error, ""], True), "error then blank lines": ([error, "", ""], True),
                 "work after error": ([error, work], False),
                 "no error": ([work], False), "empty": ([], False), "torn last line": ([error, "{"], False)}
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        for name, (lines, expected) in cases.items():
            with self.subTest(name):
                transcript = pathlib.Path(folder.name, "agent.jsonl")
                transcript.write_text("\n".join(lines), encoding="utf-8")
                stderr = io.StringIO()
                with contextlib.redirect_stderr(stderr):
                    self.assertEqual(script_utils.ends_on_api_error(transcript), expected)
                self.assertEqual(stderr.getvalue(), "")

    def test_a_directory_in_place_of_a_transcript_is_not_an_api_error_and_is_reported_on_stderr(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        stderr = io.StringIO()

        with contextlib.redirect_stderr(stderr):
            self.assertFalse(script_utils.ends_on_api_error(folder.name))

        self.assertIn("could not read", stderr.getvalue())

    def test_sibling_transcript_path_shares_the_subagent_file_name(self):
        session = "/p/sess.jsonl"
        subagent = script_utils.subagent_transcript_path(session, "abc")

        self.assertEqual(script_utils.sibling_transcript_path(subagent, "def"), "/p/sess/subagents/agent-def.jsonl")

    def test_a_missing_transcript_is_not_an_api_error(self):
        stderr = io.StringIO()

        with contextlib.redirect_stderr(stderr):
            self.assertFalse(script_utils.ends_on_api_error("/nonexistent/agent.jsonl"))

        self.assertEqual(stderr.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
