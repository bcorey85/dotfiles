"""Tests for phase_asks.py (the ruling on a /code phase review's asks) and the open row that `code_wait.py review`
writes for them."""
import contextlib
import fcntl
import importlib.util
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest
import unittest.mock
from typing import ClassVar

import fake_ledger
import isolated_state
import test_review_loop_script as loop_script
import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
import approval_asks_store
import ask_outcome_words
import capped_review
import file_lock
import handback
import handback_store
import phase_asks
import review_asks
import reviewed_tree
import script_utils
import stop_file_names

SCRIPT = pathlib.Path(os.environ.get("PHASE_ASKS_SCRIPT") or toolkit_paths.REVIEW_DIR / "phase_asks.py")
CLAUDE_DIR = pathlib.Path(os.environ.get("REVIEW_FIX_CLAUDE_DIR") or toolkit_paths.CLAUDE_DIR)
SESSION = "11111111-aaaa-bbbb-cccc-222222222222"
GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@example.com", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}
FIRST_ID = "0ff295856f1a9ccc"
SECOND_ID = "1aa295856f1a9ddd"
CONTEXT = {"branch": "main", "lane": "code", "scope": "phase", "iter": 2, "review_round": 2, "phase": "3"}
PLAN_IMPACT_QUESTION = "PLAN-IMPACT: the retry the plan asks for cannot work. Change the plan?"


def ask(question, finding_id, line):
    return {"question": question, "file_line": f"src/a.py:{line}", "change": "make the change", "gate": "code-reviewer",
            "class": "correctness", "finding_id": finding_id}


def user_only_ask(path, finding_id, line):
    """The ask of a coder's edit to the approval-only file `path`, marked for the user alone."""
    text = f"A fix coder edited `{path}`, an approval-only file."
    return {**ask(text, finding_id, line), ask_outcome_words.USER_ONLY_KEY: True}


ASKS = [ask("Should an empty list count as none?", FIRST_ID, 3), ask("Should the cap be 3?", SECOND_ID, 9)]


def packet_with(asks):
    return json.dumps({"status": "converged", "iter": 2, "review_round": 2, "fixed": [], "skipped_fp": [],
                       "blockers": [], "findings_remaining": [], "ask": asks, "class_closure": "n/a - fixed[] empty",
                       "files_touched": [], "nit": [], "full_check": "passed",
                       "full_check_command": "bash tests/run.sh", "full_check_summary": "1 tests, 0 failed"})


class StoreCase(unittest.TestCase):
    """A git repo, a hand-back store of its own, and the stand-in ledger."""

    def setUp(self):
        isolated_state.isolate_state_root(self)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.temp_root = pathlib.Path(temp.name)
        self.repo = self.temp_root / "myrepo"
        self.repo.mkdir()
        for argv in (["init", "-q", "-b", "main"], ["commit", "-q", "--allow-empty", "-m", "init"]):
            subprocess.run(["git", *argv], cwd=self.repo, env={**os.environ, **GIT_ENV}, check=True,
                           capture_output=True)
        self.repo_top = str(self.repo.resolve())
        self.store_dir = self.temp_root / "store"
        self.ledger_env = fake_ledger.install(self.temp_root)
        patcher = unittest.mock.patch.dict(os.environ, {"HANDBACK_STORE_DIR": str(self.store_dir),
                                                        "CLAUDE_CODE_SESSION_ID": SESSION})
        patcher.start()
        self.addCleanup(patcher.stop)

    def seed_handback(self):
        """A review dispatch of the repo and its hand-back; returns the hand-back row's time."""
        handback_store.record(SESSION, "dispatch", repo=self.repo_top, no_review=False)
        return handback_store.record(SESSION, "handback", status="converged", message="", tree=None)["ts"]

    def store_rows(self, kind):
        return handback_store.session_rows(SESSION, kind)

    def environment(self, **extra):
        return {**os.environ, **GIT_ENV, **self.ledger_env, "REVIEW_FIX_CLAUDE_DIR": str(CLAUDE_DIR),
                "CLAUDE_TOOLKIT_TELEMETRY": "1", **extra}

    def run_script(self, *args, **extra):
        done = subprocess.run(["python3", "-I", str(SCRIPT), *args], cwd=self.repo, text=True, capture_output=True,
                              env=self.environment(**extra))
        return done.returncode, done.stdout, done.stderr

    def outcome_rows(self):
        return [row for row in fake_ledger.recorded_rows(self.ledger_env) if "ask_outcome" in row]


class ScriptRunCase(StoreCase):
    """A store holding one open row of ASKS, and helpers that run phase_asks.py against it."""

    def setUp(self):
        super().setUp()
        self.seed_handback()
        self.open_asks(ASKS)

    def open_asks(self, asks):
        handback_store.record_phase_asks_open(SESSION, self.repo_top, [dict(item) for item in asks], CONTEXT,
                                              "loop-a:2")


class PhaseAsksCommandTest(ScriptRunCase):
    def test_list_numbers_the_open_asks_and_prints_the_rule_command(self):
        code, output, _ = self.run_script("list")

        self.assertEqual(code, 0)
        self.assertIn("\n".join(review_asks.numbered_ask_lines(ASKS)), output)
        self.assertIn("2. Should the cap be 3?", output)
        self.assertIn("phase_asks.py rule 'accepted|rejected:<one-line reason>' 'accepted|rejected:<one-line reason>'",
                      output)

    def test_list_says_the_asks_are_ruled_once_they_are(self):
        self.run_script("rule", "accepted:a", "rejected:b")

        code, output, _ = self.run_script("list")

        self.assertEqual(code, 0)
        self.assertIn("already ruled", output)
        self.assertNotIn("Rule on all", output)

    def test_an_ask_with_no_finding_id_is_logged_and_ruled_under_one_minted_id(self):
        self.run_script("rule", "accepted:a", "rejected:b")
        idless = {key: value for key, value in ASKS[0].items() if key != "finding_id"}
        handback_store.record_phase_asks_open(SESSION, self.repo_top, [idless], CONTEXT, "loop-b:2")

        code, _, _ = self.run_script("rule", "accepted:fixes a defect in scope")

        self.assertEqual(code, 0)
        ruled = self.store_rows(handback_store.PHASE_ASKS_RULED)[-1]
        minted = ruled["rulings"][0]["finding_id"]
        self.assertTrue(minted)
        self.assertEqual([row["finding_id"] for row in self.outcome_rows()][2:], [minted])

    def test_a_second_packet_opened_before_any_ruling_carries_the_first_packets_asks(self):
        third_id = "2bb295856f1a9eee"
        later_packet = {**json.loads(packet_with([ask("Should it log?", third_id, 12)])), "iter": 5,
                        "review_round": 5}
        for call in ("first", "repeat"):
            lines = phase_asks.record_open(SESSION, self.repo_top, later_packet, {"lane": "code", "phase": "3"},
                                           "loop-b:5")
            self.assertEqual(len(lines), 1, call)
            self.assertIn("3 finding ask(s) await your ruling", lines[0], call)
            self.assertEqual(lines[0].count(ask_outcome_words.OUTCOME_PLACEHOLDER), 3, call)

        unruled = handback_store.unruled_phase_asks(self.repo_top)
        self.assertEqual([item["finding_id"] for item in unruled["asks"]], [FIRST_ID, SECOND_ID, third_id])
        code, _, _ = self.run_script("rule", "accepted:a", "rejected:b", "accepted:c")

        self.assertEqual(code, 0)
        self.assertIsNone(handback_store.unruled_phase_asks(self.repo_top))
        rows = {row["finding_id"]: row for row in self.outcome_rows()}
        self.assertEqual(set(rows), {FIRST_ID, SECOND_ID, third_id})
        self.assertEqual(rows[FIRST_ID]["iter"], "2")
        self.assertEqual(rows[third_id]["iter"], "5")

    def test_the_same_packet_opened_twice_writes_one_row(self):
        self.open_asks(ASKS)

        self.assertEqual(len(self.store_rows(handback_store.PHASE_ASKS_OPEN)), 1)

    def test_a_packet_opened_again_after_a_second_one_is_not_carried_twice(self):
        handback_store.record_phase_asks_open(SESSION, self.repo_top, [ask("Should it log?", "2bb295856f1a9eee", 12)],
                                              CONTEXT, "loop-b:5")
        self.open_asks(ASKS)

        unruled = handback_store.unruled_phase_asks(self.repo_top)
        self.assertEqual(len(unruled["asks"]), 3)

    def test_a_packet_opened_after_a_ruling_holds_only_its_own_asks(self):
        self.run_script("rule", "accepted:a", "rejected:b")
        third = ask("Should it log?", "2bb295856f1a9eee", 12)
        handback_store.record_phase_asks_open(SESSION, self.repo_top, [third], CONTEXT, "loop-b:5")

        unruled = handback_store.unruled_phase_asks(self.repo_top)
        self.assertEqual([item["finding_id"] for item in unruled["asks"]], [third["finding_id"]])

    def test_rule_logs_each_outcome_decided_by_the_session_under_the_asks_finding_id(self):
        code, output, _ = self.run_script("rule", "accepted:fixes a defect in scope", "rejected:changes a criterion")

        self.assertEqual(code, 0, output)
        rows = self.outcome_rows()
        self.assertEqual([(row["finding_id"], row["ask_outcome"], row["ask_decided_by"]) for row in rows],
                         [(FIRST_ID, "accepted", "session"), (SECOND_ID, "rejected", "session")])
        self.assertEqual({(row["lane"], row["scope"]) for row in rows}, {("code", "phase")})
        ruled = self.store_rows(handback_store.PHASE_ASKS_RULED)
        self.assertEqual([(item["outcome"], item["reason"]) for item in ruled[0]["rulings"]],
                         [("accepted", "fixes a defect in scope"), ("rejected", "changes a criterion")])

    def test_a_reason_with_quotes_semicolons_and_backticks_is_stored_verbatim(self):
        reason = 'don\'t run "make test"; use `make check`'

        code, _, _ = self.run_script("rule", f"accepted:{reason}", "rejected:b")

        self.assertEqual(code, 0)
        ruled = self.store_rows(handback_store.PHASE_ASKS_RULED)[-1]
        self.assertEqual(ruled["rulings"][0]["reason"], reason)

    def test_rule_refuses_a_call_that_does_not_give_every_ask_one_outcome_and_a_reason(self):
        refused = {
            "wrong count": (["accepted:ok"], "2 finding ask(s) are open but 1 outcome(s)"),
            "no reason": (["accepted:ok", "rejected:"], "outcome 2 ('rejected:') has no reason"),
            "blank reason": (["accepted:  ", "rejected:no"], "outcome 1 ('accepted:  ') has no reason"),
            "bad word": (["accepted:ok", "modified:other"], "outcome 2 ('modified:other') must start with"),
            "no colon": (["accepted", "rejected:no"], "outcome 1 ('accepted') has no reason"),
        }
        for case, (words, expected) in refused.items():
            with self.subTest(case):
                code, _, errors = self.run_script("rule", *words)

                self.assertEqual(code, 2)
                self.assertIn(expected, errors)
                self.assertIn("phase_asks.py rule", errors)
                self.assertEqual(self.outcome_rows(), [])
                self.assertEqual(self.store_rows(handback_store.PHASE_ASKS_RULED), [])

    def test_the_ruling_stands_when_the_logger_fails(self):
        failing_claude = self.temp_root / "claude"
        logger = failing_claude / "skills/review/log-review-finding"
        logger.parent.mkdir(parents=True)
        logger.write_text("#!/usr/bin/env bash\necho logger down >&2\nexit 1\n")

        code, _, errors = self.run_script("rule", "accepted:a", "rejected:b", REVIEW_FIX_CLAUDE_DIR=str(failing_claude))

        self.assertEqual(code, 0)
        self.assertIn("outcome row not logged, ask 1", errors)
        self.assertEqual(len(self.store_rows(handback_store.PHASE_ASKS_RULED)), 1)

    def test_the_ruling_stands_with_telemetry_off(self):
        code, _, _ = self.run_script("rule", "accepted:a", "rejected:b", CLAUDE_TOOLKIT_TELEMETRY="0")

        self.assertEqual(code, 0)
        self.assertEqual(len(self.store_rows(handback_store.PHASE_ASKS_RULED)), 1)

    def test_a_second_rule_call_says_ruled_and_logs_nothing_again(self):
        self.run_script("rule", "accepted:a", "rejected:b")
        logged = len(self.outcome_rows())

        code, output, _ = self.run_script("rule", "rejected:c", "rejected:d")

        self.assertEqual(code, 0)
        self.assertIn("already ruled", output)
        self.assertEqual(len(self.outcome_rows()), logged)
        self.assertEqual(len(self.store_rows(handback_store.PHASE_ASKS_RULED)), 1)

    def test_a_session_with_a_new_id_lists_and_rules_the_asks_an_earlier_session_opened(self):
        later = {"CLAUDE_CODE_SESSION_ID": "99999999-aaaa-bbbb-cccc-000000000000"}

        list_code, listed, _ = self.run_script("list", **later)
        rule_code, _, errors = self.run_script("rule", "accepted:a", "rejected:b", **later)

        self.assertEqual(list_code, 0)
        self.assertIn("2. Should the cap be 3?", listed)
        self.assertEqual(rule_code, 0, errors)
        _, relisted, _ = self.run_script("list")
        self.assertIn("already ruled", relisted)

    def test_the_ruled_row_names_the_ruling_session_apart_from_the_opener(self):
        ruling_session = "99999999-aaaa-bbbb-cccc-000000000000"

        code, _, errors = self.run_script("rule", "accepted:a", "rejected:b", CLAUDE_CODE_SESSION_ID=ruling_session)

        self.assertEqual(code, 0, errors)
        ruled = self.store_rows(handback_store.PHASE_ASKS_RULED)[-1]
        self.assertEqual(ruled["ruled_by"], ruling_session)
        self.assertEqual(ruled["session_id"], SESSION)

    def test_a_ruling_does_not_settle_an_open_row_that_was_written_while_it_logged(self):
        newer_ask = ask("Should it log?", "2bb295856f1a9eee", 12)

        def open_while_logging(*_args):
            # A row written outside the lock (a producer waits for it): the ruling must still leave it open.
            handback_store.record(SESSION, handback_store.PHASE_ASKS_OPEN, repo=self.repo_top, asks=[newer_ask],
                                  contexts=[CONTEXT], packet_keys=["loop-b:5"])
            return phase_asks.OutcomeLog([], [])

        with unittest.mock.patch.object(phase_asks, "log_outcomes", open_while_logging), \
                unittest.mock.patch("pathlib.Path.cwd", return_value=self.repo), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(phase_asks.command_rule(["accepted:a", "rejected:b"]), 0)

        code, listed, _ = self.run_script("list")
        self.assertEqual(code, 0)
        self.assertIn("Rule on all", listed)
        self.assertIn("Should it log?", listed)

    def test_a_packet_that_was_ruled_and_is_opened_again_after_a_later_packet_opens_nothing(self):
        self.run_script("rule", "accepted:a", "rejected:b")
        handback_store.record_phase_asks_open(SESSION, self.repo_top, [ask("Should it log?", "2bb295856f1a9eee", 12)],
                                              CONTEXT, "loop-b:5")
        self.run_script("rule", "accepted:c")

        self.open_asks(ASKS)

        self.assertEqual(len(self.store_rows(handback_store.PHASE_ASKS_OPEN)), 2)
        _code, listed, _ = self.run_script("list")
        self.assertIn("already ruled", listed)

    def test_a_logger_that_hangs_is_cut_off_and_the_ruling_stands_with_the_command_to_log_it_later(self):
        hanging = self.temp_root / "hanging-logger"
        hanging.write_text("#!/usr/bin/env bash\nsleep 4\n")
        errors = io.StringIO()

        with unittest.mock.patch.object(phase_asks, "ASK_LOGGER", hanging), \
                unittest.mock.patch.object(review_asks.handback, "LOGGER_TIMEOUT_SECONDS", 1), \
                unittest.mock.patch("pathlib.Path.cwd", return_value=self.repo), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
            code = phase_asks.command_rule(["accepted:a", "rejected:b"])

        self.assertEqual(code, 0)
        self.assertIn("outcome row not logged, ask 1", errors.getvalue())
        self.assertIn("timed out after 1 seconds", errors.getvalue())
        self.assertIn(f"bash {hanging} kind=finding finding_id={FIRST_ID}", errors.getvalue())
        self.assertEqual(len(self.store_rows(handback_store.PHASE_ASKS_RULED)), 1)

    def test_a_logger_that_hangs_is_called_no_more_after_its_first_timeout_and_every_ask_is_still_reported(self):
        idless = {key: value for key, value in ask("Should it log?", FIRST_ID, 12).items() if key != "finding_id"}
        handback_store.record_phase_asks_open(SESSION, self.repo_top, [idless], CONTEXT, "loop-b:2")
        hanging = self.temp_root / "hanging-logger"
        hanging.write_text("#!/usr/bin/env bash\nsleep 4\n")
        errors = io.StringIO()
        timeout_seconds = 1

        with unittest.mock.patch.object(phase_asks, "ASK_LOGGER", hanging), \
                unittest.mock.patch.object(review_asks.handback, "LOGGER_TIMEOUT_SECONDS", timeout_seconds), \
                unittest.mock.patch("pathlib.Path.cwd", return_value=self.repo), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
            started = time.monotonic()
            code = phase_asks.command_rule(["accepted:a", "rejected:b", "accepted:c"])
            elapsed = time.monotonic() - started

        self.assertEqual(code, 0)
        self.assertEqual(len(self.store_rows(handback_store.PHASE_ASKS_RULED)), 2)
        self.assertEqual(errors.getvalue().count("outcome row not logged"), 3)
        self.assertLess(elapsed, 2 * timeout_seconds)

    def test_a_damaged_row_stops_list_and_rule_with_the_file_the_line_and_the_expected_form(self):
        store_file = handback_store.session_file(SESSION)
        damaged = {**self.store_rows(handback_store.PHASE_ASKS_OPEN)[0], "asks": "not a list"}
        store_file.write_text(store_file.read_text() + json.dumps(damaged) + "\n")
        damaged_line = len(store_file.read_text().splitlines())

        for args in (("list",), ("rule", "accepted:a", "rejected:b")):
            with self.subTest(args[0]):
                code, _, errors = self.run_script(*args)

                self.assertEqual(code, 1)
                self.assertNotIn("Traceback", errors)
                self.assertIn(f"{store_file}:{damaged_line}", errors)
                self.assertIn('"asks" a list of objects', errors)
        self.assertEqual(self.outcome_rows(), [])

    def test_a_row_cut_inside_the_repo_value_is_skipped_and_list_still_prints_the_asks(self):
        store_file = handback_store.session_file(SESSION)
        torn = '{"kind": "phase-asks-open", "repo": "' + self.repo_top[:-2]
        store_file.write_text(store_file.read_text() + torn + "\n")
        torn_line = len(store_file.read_text().splitlines())

        code, output, errors = self.run_script("list")

        self.assertEqual(code, 0)
        self.assertIn("2. Should the cap be 3?", output)
        self.assertIn("handback_store: skipped damaged", errors)
        self.assertIn(f"{store_file}:{torn_line}", errors)

    @unittest.skipIf(os.geteuid() == 0, "root writes to a read-only folder")
    def test_a_store_that_cannot_be_written_stops_rule_before_it_logs_anything(self):
        store_file = handback_store.session_file(SESSION)
        os.chmod(store_file, 0o444)
        os.chmod(store_file.parent, 0o555)
        self.addCleanup(os.chmod, store_file.parent, 0o755)

        code, _, errors = self.run_script("rule", "accepted:a", "rejected:b")

        self.assertEqual(code, 1)
        self.assertNotIn("Traceback", errors)
        self.assertIn(str(store_file), errors)
        self.assertEqual(self.outcome_rows(), [])

    def test_a_newer_hand_back_leaves_the_asks_open_until_they_are_ruled(self):
        handback_store.record(SESSION, "handback", status="converged", message="", tree=None)

        list_code, list_output, _ = self.run_script("list")
        self.assertEqual(list_code, 0)
        self.assertIn("Rule on all 2 in order", list_output)
        self.assertIsNotNone(handback_store.unruled_phase_asks(self.repo_top))

        rule_code, _, _ = self.run_script("rule", "accepted:a", "rejected:b")

        self.assertEqual(rule_code, 0)
        self.assertIsNone(handback_store.unruled_phase_asks(self.repo_top))

    def test_rule_with_no_session_id_is_refused_naming_the_variable_and_logs_nothing(self):
        code, _, errors = self.run_script("rule", "accepted:a", "rejected:b", CLAUDE_CODE_SESSION_ID="")

        self.assertEqual(code, 2)
        self.assertNotIn("Traceback", errors)
        self.assertEqual(errors.count("\n"), 1)
        self.assertIn("CLAUDE_CODE_SESSION_ID", errors)
        self.assertEqual(self.outcome_rows(), [])
        self.assertIsNotNone(handback_store.unruled_phase_asks(self.repo_top))

    def test_list_with_no_session_id_still_prints_the_asks(self):
        code, output, errors = self.run_script("list", CLAUDE_CODE_SESSION_ID="")

        self.assertEqual(code, 0, errors)
        self.assertIn("2. Should the cap be 3?", output)

    def test_a_ruling_stays_when_the_ruling_sessions_own_file_is_deleted(self):
        ruler = "99999999-aaaa-bbbb-cccc-000000000000"
        code, _, errors = self.run_script("rule", "accepted:a", "rejected:b", CLAUDE_CODE_SESSION_ID=ruler)
        self.assertEqual(code, 0, errors)

        for store_file in self.store_dir.glob("*.jsonl"):
            if store_file != handback_store.session_file(SESSION):
                store_file.unlink()

        self.assertIsNone(handback_store.unruled_phase_asks(self.repo_top))

    def test_a_ruling_stays_when_the_file_of_a_newer_open_row_that_carried_the_asks_is_pruned(self):
        second_opener = "88888888-aaaa-bbbb-cccc-000000000000"
        handback_store.record_phase_asks_open(second_opener, self.repo_top, [dict(ASKS[0])], CONTEXT, "loop-b:2")
        code, _, errors = self.run_script("rule", "accepted:a", "rejected:b", "accepted:c")
        self.assertEqual(code, 0, errors)

        handback_store.session_file(second_opener).unlink()

        self.assertIsNone(handback_store.unruled_phase_asks(self.repo_top))

    def test_an_unwritable_file_of_a_carried_open_row_refuses_the_ruling_before_anything_is_logged(self):
        second_opener = "88888888-aaaa-bbbb-cccc-000000000000"
        handback_store.record_phase_asks_open(second_opener, self.repo_top, [dict(ASKS[0])], CONTEXT, "loop-b:2")
        first_file = handback_store.session_file(SESSION)
        first_file.chmod(0o400)
        self.addCleanup(first_file.chmod, 0o600)

        code, _, errors = self.run_script("rule", "accepted:a", "rejected:b", "accepted:c")

        self.assertEqual(code, 1)
        self.assertIn(str(first_file), errors)
        self.assertEqual(self.outcome_rows(), [])

    def test_an_unknown_verb_prints_the_usage_and_exits_two(self):
        code, _, errors = self.run_script("frobnicate")

        self.assertEqual(code, 2)
        self.assertIn("phase_asks.py rule", errors)

    def test_the_printed_usage_has_no_line_over_120_characters(self):
        code, _, errors = self.run_script("frobnicate")

        self.assertEqual(code, 2)
        for line in errors.splitlines():
            self.assertLessEqual(len(line), 120, line)


PRODUCER_CODE = """
import pathlib, sys, time
import handback_store
index, repo, go_file = sys.argv[1], sys.argv[2], pathlib.Path(sys.argv[3])
original_read = handback_store.read_phase_ask_rows
def slow_read(repo_top):
    rows = original_read(repo_top)
    time.sleep(0.3)
    return rows
handback_store.read_phase_ask_rows = slow_read
for _ in range(1000):
    if go_file.exists():
        break
    time.sleep(0.01)
new_ask = {"question": "q" + index, "file_line": "src/a.py:" + index, "change": "c", "gate": "code-reviewer",
           "class": "correctness", "finding_id": "id" + index}
context = {"branch": "main", "lane": "code", "scope": "phase", "iter": 2, "review_round": 2, "phase": "3"}
handback_store.record_phase_asks_open("sess" + index, repo, [new_ask], context, "loop-" + index + ":1")
"""


class ConcurrentPhaseAsksTest(ScriptRunCase):
    def test_four_producers_started_together_end_with_every_ask_in_the_latest_open_row(self):
        go_file = self.temp_root / "go"
        scripts = [toolkit_paths.LIB_DIR, toolkit_paths.REVIEW_DIR]
        env = {**self.environment(), "PYTHONPATH": os.pathsep.join(str(folder) for folder in scripts)}
        producers = [subprocess.Popen([sys.executable, "-c", PRODUCER_CODE, str(index), self.repo_top, str(go_file)],
                                      env=env, stderr=subprocess.PIPE, text=True) for index in range(4)]
        go_file.write_text("go")
        errors = [producer.communicate(timeout=60)[1] for producer in producers]

        self.assertEqual([producer.returncode for producer in producers], [0] * 4, errors)
        unruled = handback_store.unruled_phase_asks(self.repo_top)
        self.assertEqual(len(unruled["asks"]), len(ASKS) + 4)

    def test_two_rule_calls_started_together_log_and_rule_once(self):
        calls = [subprocess.Popen(["python3", "-I", str(SCRIPT), "rule", "accepted:a", "rejected:b"], cwd=self.repo,
                                  env=self.environment(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                 for _call in range(2)]
        results = [call.communicate(timeout=60) for call in calls]

        self.assertEqual([call.returncode for call in calls], [0, 0], results)
        self.assertEqual(len(self.store_rows(handback_store.PHASE_ASKS_RULED)), 1)
        self.assertEqual(len(self.outcome_rows()), len(ASKS))

    def hold_lock(self, repo):
        lock_path = handback_store.phase_asks_lock_path(repo)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_file = lock_path.open("a")
        self.addCleanup(lock_file.close)
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        return lock_path

    def test_a_lock_held_for_another_repo_does_not_block_this_one(self):
        self.hold_lock(str(self.temp_root / "other-repo"))
        new_ask = ask("q?", "3cc295856f1a9fff", 1)

        with unittest.mock.patch.object(handback_store, "PHASE_ASKS_LOCK_TIMEOUT_SECONDS", 0.2):
            handback_store.record_phase_asks_open(SESSION, self.repo_top, [new_ask], CONTEXT, "loop-z:1")
        code, _, errors = self.run_script("rule", "accepted:a", "rejected:b", "accepted:c",
                                          HANDBACK_LOCK_TIMEOUT_SECONDS="0.3")

        self.assertEqual(code, 0, errors)

    def test_each_repo_has_its_own_lock_file_and_it_is_no_hand_back_store_file(self):
        first = handback_store.phase_asks_lock_path(self.repo_top)
        second = handback_store.phase_asks_lock_path(self.repo_top + "-other")

        self.assertNotEqual(first, second)
        self.assertEqual(first, handback_store.phase_asks_lock_path(self.repo_top))
        self.assertEqual(first.parent, handback_store.store_dir())
        self.assertNotEqual(first.suffix, ".jsonl")

    def test_rule_while_the_lock_is_held_fails_naming_the_lock_file_and_writes_nothing(self):
        lock_path = self.hold_lock(self.repo_top)
        before = len(self.store_rows(handback_store.PHASE_ASKS_RULED))

        code, _, errors = self.run_script("rule", "accepted:a", "rejected:b", HANDBACK_LOCK_TIMEOUT_SECONDS="0.3")

        self.assertEqual(code, 1)
        self.assertNotIn("Traceback", errors)
        self.assertIn(str(lock_path), errors)
        self.assertEqual(len(self.store_rows(handback_store.PHASE_ASKS_RULED)), before)
        self.assertEqual(self.outcome_rows(), [])

    def test_opening_asks_while_the_lock_is_held_raises_naming_the_lock_file_and_writes_nothing(self):
        lock_path = self.hold_lock(self.repo_top)
        rows_before = len(self.store_rows(handback_store.PHASE_ASKS_OPEN))

        new_ask = ask("q?", "3cc295856f1a9fff", 1)
        with unittest.mock.patch.object(handback_store, "PHASE_ASKS_LOCK_TIMEOUT_SECONDS", 0.2), \
                self.assertRaises(file_lock.LockTimeoutError) as raised:
            handback_store.record_phase_asks_open(SESSION, self.repo_top, [new_ask], CONTEXT, "loop-z:1")

        self.assertIn(str(lock_path), str(raised.exception))
        self.assertEqual(len(self.store_rows(handback_store.PHASE_ASKS_OPEN)), rows_before)


class WaitCase(StoreCase):
    """A repo with a finished phase review loop, and `wait` to run `code_wait.py review` over a packet."""

    def setUp(self):
        super().setUp()
        module_spec = importlib.util.spec_from_file_location("code_wait", toolkit_paths.CODE_DIR / "code_wait.py")
        self.code_wait = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(self.code_wait)
        self.seed_handback()
        self.phase_dir = self.code_wait.phase_dir(self.repo)
        self.phase_dir.mkdir()
        (self.phase_dir / "pid").write_text("999999999")
        (self.phase_dir / self.code_wait.REVIEW_OUTPUT).write_text("packet printed\n")
        self.loop_folder = self.temp_root / "loop"
        self.loop_folder.mkdir()
        (self.phase_dir / stop_file_names.LOOP_DIR_FILE).write_text(f"{self.loop_folder}\n")
        self.code_wait.write_phase_run(self.repo, "code", "3")

    def wait(self, asks):
        (self.loop_folder / self.code_wait.reviewer_dispatch.PACKET_FILE).write_text(packet_with(asks))
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = self.code_wait.wait_review(self.repo)
        return code, output.getvalue()


class OpenPhaseAsksTest(WaitCase):
    """`code_wait.py review` opens the asks of the phase packet once."""

    def test_a_packet_with_finding_asks_opens_one_row_however_often_the_wait_runs(self):
        for _call in range(2):
            code, output = self.wait(ASKS)
            self.assertEqual(code, 0)
            self.assertIn("2 finding ask(s) await your ruling", output)

        rows = self.store_rows(handback_store.PHASE_ASKS_OPEN)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["repo"], self.repo_top)
        self.assertNotIn("handback_ts", rows[0])
        self.assertEqual(rows[0]["contexts"][0]["lane"], "code")
        self.assertEqual(rows[0]["contexts"][0]["phase"], "3")
        self.assertEqual([item["file_line"] for item in rows[0]["asks"]], ["src/a.py:3", "src/a.py:9"])

    def test_a_repo_outside_a_work_tree_opens_nothing_and_names_no_repo(self):
        (self.loop_folder / self.code_wait.reviewer_dispatch.PACKET_FILE).write_text(packet_with(ASKS))

        with unittest.mock.patch.object(self.code_wait.script_utils, "repo_root", return_value=None):
            lines = self.code_wait.phase_asks_notice(self.repo, self.code_wait.read_phase_packet(self.repo))

        self.assertEqual(lines, [])
        self.assertEqual(self.store_rows(handback_store.PHASE_ASKS_OPEN), [])

    def wait_while_the_lock_is_held(self):
        """(lock file, exit code, output) of a wait whose repo lock another process holds."""
        lock_path = handback_store.phase_asks_lock_path(self.repo_top)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a") as held, \
                unittest.mock.patch.object(handback_store, "PHASE_ASKS_LOCK_TIMEOUT_SECONDS", 0.2):
            fcntl.flock(held, fcntl.LOCK_EX)
            code, output = self.wait(ASKS)
        return lock_path, code, output

    def test_asks_that_cannot_be_opened_fail_the_wait_and_its_last_line_names_the_rerun(self):
        lock_path, code, output = self.wait_while_the_lock_is_held()

        self.assertEqual(code, 1)
        self.assertIn(str(lock_path), output)
        self.assertEqual(output.splitlines()[-1],
                         f"Run `{self.code_wait.REVIEW_COMMAND}` again to open them for ruling.")
        self.assertEqual(self.store_rows(handback_store.PHASE_ASKS_OPEN), [])

    def test_a_wait_run_again_after_the_failure_opens_the_asks(self):
        self.wait_while_the_lock_is_held()

        code, output = self.wait(ASKS)

        self.assertEqual(code, 0)
        self.assertIn("2 finding ask(s) await your ruling", output)

    def test_a_packet_with_only_plan_impact_asks_opens_nothing(self):
        plan_impact = ask(PLAN_IMPACT_QUESTION, FIRST_ID, 3)

        _code, output = self.wait([plan_impact])

        self.assertEqual(self.store_rows(handback_store.PHASE_ASKS_OPEN), [])
        self.assertNotIn("await your ruling", output)

    def test_a_plan_impact_ask_next_to_a_finding_ask_is_left_out_of_the_open_row(self):
        self.wait([ask(PLAN_IMPACT_QUESTION, FIRST_ID, 3), ASKS[1]])

        rows = self.store_rows(handback_store.PHASE_ASKS_OPEN)
        self.assertEqual([item["finding_id"] for item in rows[0]["asks"]], [SECOND_ID])

    def test_a_newer_hand_back_from_another_review_does_not_reopen_the_ruled_packet(self):
        self.wait(ASKS)
        first_open = self.store_rows(handback_store.PHASE_ASKS_OPEN)[0]
        handback_store.record(SESSION, handback_store.PHASE_ASKS_RULED, repo=self.repo_top, rulings=[],
                              **{handback_store.RULED_OPEN_TS_KEY: first_open["ts"]})
        handback_store.record(SESSION, "handback", status="converged", message="", tree=None)

        code, output = self.wait(ASKS)

        self.assertEqual(code, 0)
        self.assertNotIn("await your ruling", output)
        self.assertEqual(len(self.store_rows(handback_store.PHASE_ASKS_OPEN)), 1)
        self.assertIsNone(handback_store.unruled_phase_asks(self.repo_top))

    def test_a_packet_of_a_new_loop_opens_a_second_row(self):
        self.wait(ASKS)
        first_open = self.store_rows(handback_store.PHASE_ASKS_OPEN)[0]
        handback_store.record(SESSION, handback_store.PHASE_ASKS_RULED, repo=self.repo_top, rulings=[],
                              **{handback_store.RULED_OPEN_TS_KEY: first_open["ts"]})
        newer_loop = self.temp_root / "loop-newer"
        newer_loop.mkdir()
        (self.phase_dir / stop_file_names.LOOP_DIR_FILE).write_text(f"{newer_loop}\n")
        (newer_loop / self.code_wait.reviewer_dispatch.PACKET_FILE).write_text(packet_with(ASKS))

        with contextlib.redirect_stdout(io.StringIO()):
            self.code_wait.wait_review(self.repo)

        rows = self.store_rows(handback_store.PHASE_ASKS_OPEN)
        self.assertEqual(len(rows), 2)
        self.assertEqual(handback_store.unruled_phase_asks(self.repo_top)["packet_keys"],
                         rows[1]["packet_keys"])

    def test_a_wait_on_a_launched_loop_opens_nothing(self):
        launched = self.temp_root / "launched"
        launched.mkdir()
        (launched / self.code_wait.reviewer_dispatch.PID_FILE).write_text("999999999")
        (launched / self.code_wait.reviewer_dispatch.PACKET_FILE).write_text(packet_with(ASKS))
        (self.loop_folder / self.code_wait.reviewer_dispatch.PACKET_FILE).write_text(packet_with(ASKS))
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            code = self.code_wait.wait_review(self.repo, (), str(launched))

        self.assertEqual(code, 0)
        self.assertEqual(self.store_rows(handback_store.PHASE_ASKS_OPEN), [])
        self.assertNotIn("await your ruling", output.getvalue())

    def test_a_wait_that_ends_with_a_stop_code_opens_nothing(self):
        packet = json.loads(packet_with(ASKS))
        packet["status"] = self.code_wait.handback.FIX_REMOVED_CHANGE
        packet["blockers"] = ["the fix passes removed half of the change"]
        packet_text = json.dumps(packet)
        self.code_wait.handback.load(packet_text)
        (self.loop_folder / self.code_wait.reviewer_dispatch.PACKET_FILE).write_text(packet_text)
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            code = self.code_wait.wait_review(self.repo)

        self.assertEqual(code, 1)
        self.assertEqual(self.store_rows(handback_store.PHASE_ASKS_OPEN), [])
        self.assertNotIn("await your ruling", output.getvalue())

    def test_no_session_id_opens_nothing_and_does_not_fail(self):
        with unittest.mock.patch.dict(os.environ, {"CLAUDE_CODE_SESSION_ID": ""}):
            code, _output = self.wait(ASKS)

        self.assertEqual(code, 0)
        self.assertEqual(self.store_rows(handback_store.PHASE_ASKS_OPEN), [])


    def test_a_run_record_that_is_not_the_expected_json_object_stops_the_wait_and_opens_nothing(self):
        bad_records = {"invalid json": "not json", "json that is not an object": "[1]"}
        for case, text in bad_records.items():
            with self.subTest(case):
                (self.phase_dir / self.code_wait.PHASE_RUN_FILE).write_text(text)

                with self.assertRaises(SystemExit) as stopped:
                    self.wait(ASKS)

                self.assertIn(self.code_wait.PHASE_RUN_FILE, str(stopped.exception.code))
                self.assertEqual(self.store_rows(handback_store.PHASE_ASKS_OPEN), [])

    def test_a_missing_run_record_opens_the_row_with_lane_none_and_no_phase(self):
        (self.phase_dir / self.code_wait.PHASE_RUN_FILE).unlink()

        self.wait(ASKS)

        context = self.store_rows(handback_store.PHASE_ASKS_OPEN)[0]["contexts"][0]
        self.assertEqual(context["lane"], "none")
        self.assertNotIn("phase", context)

    def test_a_packet_that_does_not_parse_still_returns_zero_prints_why_and_opens_nothing(self):
        (self.loop_folder / self.code_wait.reviewer_dispatch.PACKET_FILE).write_text("garbage, not a packet")
        errors = io.StringIO()
        output = io.StringIO()

        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = self.code_wait.wait_review(self.repo)

        self.assertEqual(code, 0)
        self.assertIn("the packet does not parse", errors.getvalue())
        self.assertEqual(self.store_rows(handback_store.PHASE_ASKS_OPEN), [])

    def test_a_packet_that_is_not_clean_opens_nothing(self):
        packet = json.loads(packet_with(ASKS))
        packet["status"] = "critical-blocker"

        lines = phase_asks.record_open(SESSION, self.repo_top, packet, {}, "loop-c:2")

        self.assertEqual(lines, [])
        self.assertEqual(self.store_rows(handback_store.PHASE_ASKS_OPEN), [])

    def reject_the_first_ask_of(self, packet):
        """Opens `packet`'s asks, has the session reject the first one through `rule`, and returns the asks the
        review loop reads back as rejected for this session."""
        self.seed_handback()
        phase_asks.record_open(SESSION, self.repo_top, packet, {}, "loop-c:2")
        code, _output, error = self.run_script("rule", "rejected:not needed")
        self.assertEqual(code, 0, error)
        return handback_store.rejected_ask_texts(SESSION, handback_store.ruled_rows_repo(self.repo_top))

    def test_a_cap_reached_packet_with_asks_opens_them_and_a_session_rejection_is_stored(self):
        packet = json.loads(packet_with(ASKS[:1]))
        packet["status"] = "cap-reached"
        packet.update({"open_classes": [], "unrun_reviewer": [], "full_check_tree": ""})

        stored = self.reject_the_first_ask_of(packet)

        self.assertEqual(len(self.store_rows(handback_store.PHASE_ASKS_OPEN)), 1)
        self.assertEqual(stored, [f"src/a.py:3 {ASKS[0]['question']}"])
        self.assertNotIn(capped_review.effective_status(packet, self.repo_top), handback.CLEAN_STATUSES,
                         "ruling a capped packet's asks never reads the run as clean")

    def test_a_cap_reached_packet_that_reads_as_deferred_opens_its_asks(self):
        packet = json.loads(packet_with(ASKS))
        packet["status"] = "cap-reached"
        packet.update({"open_classes": [], "unrun_reviewer": [],
                       "full_check_tree": reviewed_tree.fingerprint(self.repo_top)[1]})

        lines = phase_asks.record_open(SESSION, self.repo_top, packet, {}, "loop-c:2")

        self.assertTrue(lines)
        self.assertEqual(len(self.store_rows(handback_store.PHASE_ASKS_OPEN)), 1)


class RecordOpenWithNoHandbackTest(StoreCase):
    def test_a_clean_packet_with_asks_and_no_stored_hand_back_still_opens_the_asks(self):
        lines = phase_asks.record_open(SESSION, self.repo_top, json.loads(packet_with(ASKS)), {}, "loop-d:2")

        self.assertTrue(lines)
        self.assertEqual(len(self.store_rows(handback_store.PHASE_ASKS_OPEN)), 1)
        self.assertIsNotNone(handback_store.unruled_phase_asks(self.repo_top))


class OutsideARepoTest(StoreCase):
    def run_outside(self, *args):
        outside = self.temp_root / "not-a-repo"
        outside.mkdir(exist_ok=True)
        done = subprocess.run(["python3", "-I", str(SCRIPT), *args], cwd=outside, text=True, capture_output=True,
                              env={**os.environ, **GIT_ENV, "GIT_CEILING_DIRECTORIES": str(self.temp_root)})
        return done.returncode, done.stdout, done.stderr

    def test_both_verbs_refuse_outside_a_work_tree_and_name_the_cwd(self):
        for args in (("list",), ("rule", "accepted:a")):
            with self.subTest(args[0]):
                code, output, errors = self.run_outside(*args)

                self.assertEqual(code, 2)
                self.assertIn("phase_asks: run from the repo root", errors)
                self.assertIn("not-a-repo", errors)
                self.assertNotIn("None", output + errors)


class PlaceholderRefusalTest(unittest.TestCase):
    def test_the_printed_placeholder_is_refused_with_a_replace_it_instruction(self):
        placeholder = "accepted|rejected:<one-line reason>"

        rulings, refusal = phase_asks.read_rulings([placeholder], 1)

        self.assertIsNone(rulings)
        self.assertIn("replace it with accepted or rejected", refusal)

    def test_another_unknown_word_keeps_the_plain_refusal(self):
        _rulings, refusal = phase_asks.read_rulings(["modified:x"], 1)

        self.assertIn("must start with", refusal)


class UserOnlyAskTest(ScriptRunCase):
    """An ask marked `user_only` (a coder's edit to an approval-only file) is ruled by the user, never a session."""

    def setUp(self):
        super().setUp()
        self.run_script("rule", "accepted:a", "rejected:b")
        open_ask = user_only_ask("CLAUDE.md", "3cc295856f1a9fff", 1)
        handback_store.record_phase_asks_open(SESSION, self.repo_top, [open_ask], CONTEXT, "loop-c:3")
        self.rows_before = self.outcome_rows()

    def test_a_session_ruling_on_a_revert_ask_is_refused_and_logs_nothing(self):
        code, _, error = self.run_script("rule", "rejected:keep the edit")

        self.assertEqual(code, 2)
        self.assertIn("ask(s) 1 are user_only: only the user rules them, never the session", error)
        self.assertIn("record the user's outcome with `--by user`: `rule --by user ...`", error)
        self.assertEqual(self.outcome_rows(), self.rows_before)
        self.assertIsNotNone(handback_store.unruled_phase_asks(self.repo_top))

    def test_the_open_message_hands_a_user_only_ask_to_the_user(self):
        packet = {**json.loads(packet_with([user_only_ask("CLAUDE.md", "4dd295856f1a9fff", 1)])),
                  "iter": 4, "review_round": 4}

        lines = phase_asks.record_open(SESSION, self.repo_top, packet, {"lane": "code", "phase": "3"}, "loop-d:4")

        self.assertEqual(len(lines), 1)
        self.assertIn("hand ask(s) ", lines[0])
        self.assertIn("--by user", lines[0])

    def test_a_wrong_outcome_count_by_the_user_hints_the_by_user_line(self):
        code, _, error = self.run_script("rule", "--by", "user", "rejected:a", "rejected:b")

        self.assertEqual(code, 2)
        self.assertIn("rule --by user ", error)

    def test_list_marks_the_user_only_ask_and_prints_the_by_user_line(self):
        code, output, error = self.run_script("list")

        self.assertEqual(code, 0, error)
        self.assertIn("1. [user only] ", output)
        self.assertIn("rule --by user ", output)
        self.assertIn("hand ask(s) 1 (a fix coder edited an approval-only file) to the user", output)

    def test_by_may_follow_the_outcome_words(self):
        code, _, error = self.run_script("rule", "rejected:keep the edit", "--by", "user")

        self.assertEqual(code, 0, error)
        self.assertEqual(self.outcome_rows()[-1]["ask_decided_by"], "user")

    def test_a_bare_by_is_refused(self):
        code, _, error = self.run_script("rule", "rejected:keep the edit", "--by")

        self.assertEqual(code, 2)
        self.assertIn("--by takes only", error)
        self.assertEqual(self.outcome_rows(), self.rows_before)

    def test_one_user_only_ask_among_two_refuses_the_call_and_names_that_ask(self):
        plain_ask = ask("Should it log?", "4dd295856f1a9fff", 2)
        handback_store.record_phase_asks_open(SESSION, self.repo_top,
                                              [plain_ask, user_only_ask("CLAUDE.md", "5ee295856f1a9fff", 1)],
                                              CONTEXT, "loop-c:4")
        rows_before = self.outcome_rows()

        code, _, error = self.run_script("rule", "accepted:a", "rejected:b", "rejected:c")

        self.assertEqual(code, 2)
        # ask 2 is the plain ask; the open asks carried from setUp's row hold the other user-only ask
        self.assertIn("ask(s) 1, 3 are user_only: only the user rules them", error)
        self.assertEqual(self.outcome_rows(), rows_before)

    def test_a_ruling_marked_as_the_users_is_logged_decided_by_the_user(self):
        code, _, error = self.run_script("rule", "--by", "user", "rejected:keep the edit")

        self.assertEqual(code, 0, error)
        row = self.outcome_rows()[-1]
        self.assertEqual((row["ask_outcome"], row["ask_decided_by"]), ("rejected", "user"))
        self.assertIsNone(handback_store.unruled_phase_asks(self.repo_top))

    def test_a_user_ruling_is_the_users_only_on_the_user_only_ask(self):
        self.run_script("rule", "--by", "user", "rejected:keep the edit")
        plain_ask = ask("Should it log?", "4dd295856f1a9fff", 2)
        handback_store.record_phase_asks_open(SESSION, self.repo_top,
                                              [user_only_ask("AGENTS.md", "5ee295856f1a9fff", 1), plain_ask],
                                              CONTEXT, "loop-c:4")

        code, _, error = self.run_script("rule", "--by", "user", "rejected:keep the edit", "accepted:log it")

        self.assertEqual(code, 0, error)
        decided_by = {row["finding_id"]: row["ask_decided_by"] for row in self.outcome_rows()[-2:]}
        self.assertEqual(decided_by, {"5ee295856f1a9fff": "user", "4dd295856f1a9fff": "session"})

    def test_an_unknown_ruler_is_refused(self):
        code, _, error = self.run_script("rule", "--by", "robot", "rejected:keep the edit")

        self.assertEqual(code, 2)
        self.assertIn("--by takes only", error)
        self.assertEqual(self.outcome_rows(), self.rows_before)

    def open_approval_ask_for(self, path):
        approval_ask = {**user_only_ask(path, "6ff295856f1a9fff", 1),
                        "change": approval_asks_store.approval_change(path)}
        handback_store.record_phase_asks_open(SESSION, self.repo_top, [approval_ask], CONTEXT, "loop-c:5")

    def test_a_user_rejection_drops_the_path_even_with_a_space_in_a_folder_name(self):
        self.open_approval_ask_for("docs dir/CLAUDE.md")
        approval_asks_store.write_saved_asks(self.repo_top, {"docs dir/CLAUDE.md": None, "AGENTS.md": None}, [])

        # Every open ask is rejected: the ask carried from setUp's row names no saved path.
        code, _, error = self.run_script("rule", "--by", "user", "rejected:keep", "rejected:keep")

        self.assertEqual(code, 0, error)
        self.assertEqual(list(approval_asks_store.read_approval_paths(self.repo_top)), ["AGENTS.md"])

    def save_pre_pass_base_then_edit(self, base=None):
        """CLAUDE.md holds an uncommitted user line and a coder line; the saved path names the blob of the user line
        text, or `base`."""
        claude_md = self.repo / "CLAUDE.md"
        claude_md.write_text("rules\nuser line\n")
        pre_pass_blob = script_utils.work_tree_blob(self.repo_top, "CLAUDE.md", keep_object=True)
        claude_md.write_text("rules\nuser line\ncoder line\n")
        approval_asks_store.write_saved_asks(self.repo_top, {"CLAUDE.md": base or pre_pass_blob}, [])
        return claude_md

    def test_a_user_acceptance_restores_the_pre_pass_text_and_keeps_the_user_lines(self):
        self.open_approval_ask_for("CLAUDE.md")
        claude_md = self.save_pre_pass_base_then_edit()

        # Every open ask is ruled: the ask carried from setUp's row names no saved path.
        code, output, error = self.run_script("rule", "--by", "user", "accepted:revert it", "accepted:revert it")

        self.assertEqual(code, 0, error)
        self.assertIn("Restored `CLAUDE.md` to its text from before the fix pass; "
                      "commit it with the rest of the change.", output)
        self.assertEqual(claude_md.read_text(), "rules\nuser line\n")
        self.assertEqual(approval_asks_store.read_approval_paths(self.repo_top), {})

    def test_an_unknown_base_is_left_for_the_coder_on_acceptance(self):
        self.open_approval_ask_for("CLAUDE.md")
        claude_md = self.save_pre_pass_base_then_edit(approval_asks_store.UNKNOWN_BASE)

        code, _, error = self.run_script("rule", "--by", "user", "accepted:revert it", "accepted:revert it")

        self.assertEqual(code, 0, error)
        self.assertEqual(claude_md.read_text(), "rules\nuser line\ncoder line\n")

    def test_a_restore_that_fails_exits_non_zero_naming_the_file_and_logs_nothing(self):
        self.open_approval_ask_for("CLAUDE.md")
        missing_blob = "0123456789abcdef0123456789abcdef01234567"
        claude_md = self.save_pre_pass_base_then_edit(missing_blob)
        rows_before = self.outcome_rows()

        code, _, error = self.run_script("rule", "--by", "user", "accepted:revert it", "accepted:revert it")

        self.assertEqual(code, 1)
        self.assertIn("CLAUDE.md", error)
        self.assertIn(missing_blob, error)
        self.assertEqual(self.outcome_rows(), rows_before)
        self.assertEqual(claude_md.read_text(), "rules\nuser line\ncoder line\n")
        self.assertIsNotNone(handback_store.unruled_phase_asks(self.repo_top))

    def test_a_damaged_saved_file_stops_a_rejection_with_nothing_logged(self):
        self.open_approval_ask_for("CLAUDE.md")
        saved = approval_asks_store.approval_paths_file(self.repo_top)
        saved.parent.mkdir(parents=True, exist_ok=True)
        saved.write_text("{")
        rows_before = self.outcome_rows()

        code, _, error = self.run_script("rule", "--by", "user", "rejected:keep", "rejected:keep")

        self.assertEqual(code, 1)
        self.assertIn("approval-asks.json", error)
        self.assertEqual(self.outcome_rows(), rows_before)
        self.assertIsNotNone(handback_store.unruled_phase_asks(self.repo_top))


CRITERION_QUESTION = "Should the retry count change what AC2 asks for?"


def wanted_ask(path, finding_id, line):
    """A user-only ask for a wanted change to the approval-only file `path`."""
    change = f"add the rule to the file {approval_asks_store.wanted_edit_target(path)}"
    return {**user_only_ask(path, finding_id, line), "wanted_change": True, "change": change}


def revert_ask(path, finding_id, line):
    return {**user_only_ask(path, finding_id, line), "change": approval_asks_store.approval_change(path)}


class SessionRejectsWantedChangeTest(ScriptRunCase):
    """A session may reject a user-only ask for a wanted change to an approval-only file; nothing else passes."""

    def setUp(self):
        super().setUp()
        self.run_script("rule", "accepted:a", "rejected:b")
        self.rows_before = self.outcome_rows()

    def open_one(self, open_ask):
        handback_store.record_phase_asks_open(SESSION, self.repo_top, [open_ask], CONTEXT, "loop-d:3")

    def test_a_session_rejection_of_a_wanted_change_is_logged_decided_by_the_session(self):
        for number, path in enumerate(("CLAUDE.md", "CLAUDE.local.md", "AGENTS.md")):
            with self.subTest(path=path):
                self.open_one(wanted_ask(path, f"7aa295856f1a9f{number:02d}", 1))

                code, _, error = self.run_script("rule", "rejected:not wanted")

                self.assertEqual(code, 0, error)
                row = self.outcome_rows()[-1]
                self.assertEqual((row["ask_outcome"], row["ask_decided_by"]), ("rejected", "session"))

    def test_a_session_accept_of_a_wanted_change_is_refused_and_logs_nothing(self):
        for number, path in enumerate(("CLAUDE.md", "CLAUDE.local.md", "AGENTS.md")):
            with self.subTest(path=path):
                self.open_one(wanted_ask(path, f"7bb295856f1a9f{number:02d}", 1))
                rows_before = self.outcome_rows()

                code, _, error = self.run_script("rule", "accepted:wanted")

                self.assertEqual(code, 2)
                self.assertIn("ask(s) 1 are user_only", error)
                self.assertEqual(self.outcome_rows(), rows_before)

    def test_a_session_rejection_of_a_revert_ask_is_refused(self):
        self.open_one(revert_ask("CLAUDE.md", "7cc295856f1a9fff", 1))

        code, _, error = self.run_script("rule", "rejected:keep it")

        self.assertEqual(code, 2)
        self.assertIn("ask(s) 1 are user_only", error)
        self.assertEqual(self.outcome_rows(), self.rows_before)

    def test_a_session_rejection_of_a_criteria_ask_is_refused(self):
        criteria_ask = {**wanted_ask("CLAUDE.md", "7dd295856f1a9fff", 1), ask_outcome_words.CRITERIA_KEY: ["AC1"]}
        self.open_one(criteria_ask)

        code, _, error = self.run_script("rule", "rejected:no")

        self.assertEqual(code, 2)
        self.assertIn("ask(s) 1 are user_only", error)
        self.assertEqual(self.outcome_rows(), self.rows_before)

    def test_a_mixed_batch_is_refused_and_names_only_the_revert_ask(self):
        handback_store.record_phase_asks_open(
            SESSION, self.repo_top,
            [wanted_ask("CLAUDE.md", "7ee295856f1a9fff", 1), revert_ask("AGENTS.md", "7ff295856f1a9fff", 2)],
            CONTEXT, "loop-d:4")

        code, _, error = self.run_script("rule", "rejected:no", "rejected:no")

        self.assertEqual(code, 2)
        self.assertIn("ask(s) 2 are user_only", error)
        self.assertNotIn("ask(s) 1", error)
        self.assertEqual(self.outcome_rows(), self.rows_before)

    def test_the_instruction_says_a_session_may_reject_a_wanted_change_only_when_every_user_only_ask_is_one(self):
        wanted = [wanted_ask("CLAUDE.md", "7aa295856f1a9fff", 1)]
        mixed = [*wanted, revert_ask("AGENTS.md", "7bb295856f1a9fff", 2)]

        self.assertIn("may reject a wanted change", phase_asks.instruction_for(wanted))
        self.assertNotIn("may reject a wanted change", phase_asks.instruction_for(mixed))


class WantedPathOfChangeTest(unittest.TestCase):
    def test_the_reader_inverts_wanted_edit_target(self):
        change = f"do it {approval_asks_store.wanted_edit_target('docs dir/CLAUDE.md')}"

        self.assertEqual(approval_asks_store.wanted_path_of_change(change), "docs dir/CLAUDE.md")

    def test_other_text_reads_as_none(self):
        for change in (None, "", "make the change", approval_asks_store.approval_change("CLAUDE.md"), "(edit to ``)"):
            with self.subTest(change=change):
                self.assertIsNone(approval_asks_store.wanted_path_of_change(change))


class CriterionAskTest(WaitCase):
    """A phase ask that names a criterion id of the plan's acceptance-criteria.md is held for the user when the user
    owns the criteria."""

    def write_plan(self, ticket):
        plan_folder = self.repo / "docs" / "plans" / "p"
        plan_folder.mkdir(parents=True)
        (plan_folder / "plan.md").write_text("# Plan\n")
        (plan_folder / "acceptance-criteria.md").write_text("- **AC1** — first\n- **AC2** — second\n")
        if ticket:
            (plan_folder / "00-ticket.md").write_text("# Ticket\n\n## Acceptance criteria\n\n- the retry works\n")
        self.code_wait.write_phase_run(self.repo, "code", "3", plan="docs/plans/p/plan.md")

    def open_criterion_ask(self, question=CRITERION_QUESTION):
        code, output = self.wait([ask(question, FIRST_ID, 3)])
        self.assertEqual(code, 0)
        return output

    def test_the_run_record_carries_the_plan_path(self):
        self.write_plan(ticket=True)

        self.assertEqual(self.code_wait.read_phase_run(self.repo)["plan"], "docs/plans/p/plan.md")

    def test_an_ask_naming_a_user_owned_criterion_opens_user_only_with_the_ids(self):
        self.write_plan(ticket=True)

        output = self.open_criterion_ask()

        opened = self.store_rows(handback_store.PHASE_ASKS_OPEN)[0]["asks"][0]
        self.assertTrue(opened[ask_outcome_words.USER_ONLY_KEY])
        self.assertEqual(opened["criteria"], ["AC2"])
        self.assertIn("AC2", output)

    def test_an_already_user_only_ask_that_names_a_criterion_passes_through_unchanged(self):
        self.write_plan(ticket=True)
        asked = {**user_only_ask("CLAUDE.md", FIRST_ID, 3), "question": CRITERION_QUESTION}
        self.wait([asked])

        opened = self.store_rows(handback_store.PHASE_ASKS_OPEN)[0]["asks"][0]
        self.assertEqual(opened, asked)
        code, output, _ = self.run_script("list")
        self.assertEqual(code, 0)
        self.assertIn("a fix coder edited an approval-only file", output)
        self.assertNotIn("ask 1 names", output)

    def test_a_plan_with_no_criteria_file_opens_the_ask_plain_and_the_wait_exits_zero(self):
        self.write_plan(ticket=True)
        (self.repo / "docs" / "plans" / "p" / "acceptance-criteria.md").unlink()

        output = self.open_criterion_ask()

        opened = self.store_rows(handback_store.PHASE_ASKS_OPEN)[0]["asks"][0]
        self.assertNotIn(ask_outcome_words.USER_ONLY_KEY, opened)
        self.assertNotIn("criteria", opened)
        self.assertNotIn("names AC2", output)

    def test_the_change_text_counts_as_naming_the_criterion(self):
        self.write_plan(ticket=True)
        asked = ask("Should the retry count change?", FIRST_ID, 3)
        asked["change"] = "reword AC1 to say three tries"
        self.wait([asked])

        opened = self.store_rows(handback_store.PHASE_ASKS_OPEN)[0]["asks"][0]
        self.assertEqual(opened["criteria"], ["AC1"])

    def test_list_marks_the_ask_user_only_names_the_ids_and_the_next_step(self):
        self.write_plan(ticket=True)
        self.open_criterion_ask()

        code, output, _ = self.run_script("list")

        self.assertEqual(code, 0)
        self.assertIn("[user only]", output)
        self.assertIn("Names criteria: AC2.", output)
        self.assertIn("ask 1 names AC2", output)
        self.assertIn("it names user-owned criteria AC2", output)
        self.assertIn("Do not rule this ask: put it on the phase-end list with its question and criteria; the user "
                      "rules it with `phase_asks.py rule --by user`.", output)

    def test_only_the_ask_that_names_a_criterion_is_held_and_numbered_by_position(self):
        self.write_plan(ticket=True)
        plain = ask("Should the cap be 3?", SECOND_ID, 9)

        code, output = self.wait([plain, ask(CRITERION_QUESTION, FIRST_ID, 3)])

        self.assertEqual(code, 0)
        opened = self.store_rows(handback_store.PHASE_ASKS_OPEN)[0]["asks"]
        self.assertNotIn(ask_outcome_words.USER_ONLY_KEY, opened[0])
        self.assertNotIn("criteria", opened[0])
        self.assertTrue(opened[1][ask_outcome_words.USER_ONLY_KEY])
        self.assertEqual(opened[1]["criteria"], ["AC2"])
        self.assertIn("ask 2 names AC2", output)
        self.assertNotIn("ask 1 names", output)
        code, _, error = self.run_script("rule", "accepted:a", "accepted:b")
        self.assertEqual(code, 2)
        self.assertIn("ask(s) 2 are user_only", error)
        self.assertEqual(self.outcome_rows(), [])

    def test_criteria_the_plan_reader_cannot_parse_fail_the_wait_naming_the_file_and_open_no_row(self):
        self.write_plan(ticket=True)
        criteria_file = self.repo / "docs" / "plans" / "p" / "acceptance-criteria.md"
        criteria_file.write_text("- **AC2** — second\n- **AC2** — again\n")

        code, output = self.wait([ask(CRITERION_QUESTION, FIRST_ID, 3)])

        self.assertEqual(code, 1)
        self.assertIn(str(criteria_file), output)
        self.assertEqual(self.store_rows(handback_store.PHASE_ASKS_OPEN), [])

    def test_the_unreadable_criteria_failure_tells_the_session_to_stop_and_name_the_file(self):
        self.write_plan(ticket=True)
        criteria_file = self.repo / "docs" / "plans" / "p" / "acceptance-criteria.md"
        criteria_file.write_text("- **AC2** — second\n- **AC2** — again\n")

        code, output = self.wait([ask(CRITERION_QUESTION, FIRST_ID, 3)])

        self.assertEqual(code, 1)
        self.assertIn("end the run with a stop to the user that names the file above", output)
        self.assertNotIn("Fix that file", output)

    def test_a_criteria_file_the_run_cannot_open_fails_the_wait_naming_it_and_opens_no_row(self):
        self.write_plan(ticket=True)
        criteria_file = self.repo / "docs" / "plans" / "p" / "acceptance-criteria.md"
        criteria_file.chmod(0o000)
        self.addCleanup(criteria_file.chmod, 0o644)

        code, output = self.wait([ask(CRITERION_QUESTION, FIRST_ID, 3)])

        self.assertEqual(code, 1)
        self.assertIn(str(criteria_file), output)
        self.assertIn("end the run with a stop to the user that names the file above", output)
        self.assertEqual(self.store_rows(handback_store.PHASE_ASKS_OPEN), [])

    def test_a_plan_folder_with_two_tickets_fails_the_wait_naming_the_owner_read_and_opens_no_row(self):
        self.write_plan(ticket=False)
        plan_folder = self.repo / "docs" / "plans" / "p"
        for name in ("a-00-ticket.md", "b-00-ticket.md"):
            (plan_folder / name).write_text("# Ticket\n")

        code, output = self.wait([ask(CRITERION_QUESTION, FIRST_ID, 3)])

        self.assertEqual(code, 1)
        self.assertIn("the criteria owner of", output)
        self.assertIn("several tickets", output)
        self.assertEqual(self.store_rows(handback_store.PHASE_ASKS_OPEN), [])

    def test_a_recorded_plan_that_is_not_a_file_fails_the_wait_naming_it_and_opens_no_row(self):
        self.code_wait.write_phase_run(self.repo, "code", "3", plan="docs/plans/missing/plan.md")

        code, output = self.wait([ask(CRITERION_QUESTION, FIRST_ID, 3)])

        self.assertEqual(code, 1)
        self.assertIn("docs/plans/missing/plan.md", output)
        self.assertIn(self.code_wait.PHASE_RESTART_STEP, output)
        self.assertEqual(self.store_rows(handback_store.PHASE_ASKS_OPEN), [])

    def test_a_session_ruling_is_refused_and_logs_nothing(self):
        self.write_plan(ticket=True)
        self.open_criterion_ask()

        code, _, error = self.run_script("rule", "accepted:fine")

        self.assertEqual(code, 2)
        self.assertIn("user_only", error)
        self.assertEqual(self.outcome_rows(), [])

    def test_a_user_ruling_logs_the_row_decided_by_the_user_and_the_asks_read_as_ruled(self):
        self.write_plan(ticket=True)
        self.open_criterion_ask()

        code, _, error = self.run_script("rule", "--by", "user", "rejected:keep AC2")

        self.assertEqual(code, 0, error)
        row = self.outcome_rows()[-1]
        self.assertEqual((row["ask_outcome"], row["ask_decided_by"]), ("rejected", "user"))
        self.assertIn("ts", self.store_rows(handback_store.PHASE_ASKS_RULED)[0])
        self.assertIsNone(handback_store.unruled_phase_asks(self.repo_top))

    def test_criteria_owned_by_the_plan_open_a_plain_ask(self):
        self.write_plan(ticket=False)

        self.open_criterion_ask()

        opened = self.store_rows(handback_store.PHASE_ASKS_OPEN)[0]["asks"][0]
        self.assertNotIn(ask_outcome_words.USER_ONLY_KEY, opened)
        self.assertNotIn("criteria", opened)

    def test_an_id_the_criteria_file_does_not_hold_opens_a_plain_ask(self):
        self.write_plan(ticket=True)

        self.open_criterion_ask("Should AC9 change?")

        opened = self.store_rows(handback_store.PHASE_ASKS_OPEN)[0]["asks"][0]
        self.assertNotIn(ask_outcome_words.USER_ONLY_KEY, opened)

    def test_a_run_with_no_plan_opens_a_plain_ask(self):
        self.open_criterion_ask()

        opened = self.store_rows(handback_store.PHASE_ASKS_OPEN)[0]["asks"][0]
        self.assertNotIn(ask_outcome_words.USER_ONLY_KEY, opened)


class FreshRunDropsARejectedAskTest(loop_script.ReviewLoopHarness, unittest.TestCase):
    """A session's rejection of an ask on a review packet is stored, and a fresh review loop run whose reviewer raises
    the same ask drops it (the packet lists it under `dropped_asks`)."""

    FINAL_READ = ("## Fix\n- `app.py:5` the last limit skips the unit\n\n## Ask\n- `app.py:3` should the limit be "
                  "configurable?\n\n## Nit\nNone\n\nOverall Assessment: NEEDS CHANGES\n")
    CAPPED_SCENARIO: ClassVar[dict] = {
        "code-reviewer": [{"result": loop_script.FIX_REVIEW}, {"result": loop_script.FIX_REVIEW},
                          {"result": FINAL_READ}],
        "coder": [{"result": "Fixed 1.", "edits": {"app.py": loop_script.APP_FIXED}},
                  {"result": "Fixed 2.", "edits": {"app.py": loop_script.APP_AFTER_EDIT}}],
        "closure": [{"result": loop_script.CLOSED}],
    }
    CONVERGED_SCENARIO: ClassVar[dict] = {
        "code-reviewer": [{"result": ("## Fix\nNone\n\n## Ask\n- `app.py:3` should the limit be configurable?\n\n"
                                      "## Nit\nNone\n\nOverall Assessment: APPROVED\n")}],
    }

    def reject_the_packet_ask_through_phase_asks(self, packet):
        """Opens the packet's asks as code_wait does and rules the first one `rejected` through phase_asks.py."""
        self.assertEqual(len(packet["ask"]), 1, packet["ask"])
        env = {**self.env, "CLAUDE_CODE_SESSION_ID": loop_script.SESSION}
        repo = os.path.realpath(self.repo)
        with unittest.mock.patch.dict(os.environ, {"HANDBACK_STORE_DIR": env["HANDBACK_STORE_DIR"]}):
            lines = phase_asks.record_open(loop_script.SESSION, repo, packet, {}, "loop-x:2")
        self.assertTrue(lines, "the packet's asks were not opened")
        done = subprocess.run(["python3", "-I", str(SCRIPT), "rule", "rejected:not wanted"], cwd=self.repo, env=env,
                              text=True, capture_output=True)
        self.assertEqual(done.returncode, 0, done.stderr)

    def assert_a_fresh_run_drops_the_rejected_ask(self, scenario):
        first = self.run_script(scenario)
        self.assertEqual(first.returncode, 0, first.stderr)
        _row, first_packet = self.stored_packet()
        self.reset_fake_run()
        self.reject_the_packet_ask_through_phase_asks(first_packet)

        second = self.run_script(scenario)

        self.assertEqual(second.returncode, 0, second.stderr)
        _row, packet = self.stored_packet()
        self.assertEqual(packet["ask"], [])
        self.assertEqual(len(packet["dropped_asks"]), 1, packet["dropped_asks"])
        self.assertNotEqual(packet["status"], "critical-blocker")
        return first_packet, packet

    def test_a_fresh_run_drops_an_ask_the_session_rejected_on_a_converged_packet(self):
        first_packet, _packet = self.assert_a_fresh_run_drops_the_rejected_ask(self.CONVERGED_SCENARIO)
        self.assertEqual(first_packet["status"], "converged")

    def test_a_fresh_run_drops_an_ask_the_session_rejected_on_a_cap_reached_packet(self):
        first_packet, packet = self.assert_a_fresh_run_drops_the_rejected_ask(self.CAPPED_SCENARIO)
        self.assertEqual((first_packet["status"], packet["status"]), ("cap-reached", "cap-reached"))


if __name__ == "__main__":
    unittest.main()
