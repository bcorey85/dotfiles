"""Tests for phase_asks.py (the ruling on a /code phase review's asks) and the open row that `code_wait.py review`
writes for them."""
import contextlib
import importlib.util
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
import unittest.mock

import fake_ledger
import isolated_state
import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
import handback_store
import phase_asks
import review_asks
import reviewed_tree

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


class PhaseAsksCommandTest(StoreCase):
    def setUp(self):
        super().setUp()
        self.handback_ts = self.seed_handback()
        self.open_asks(ASKS)

    def open_asks(self, asks):
        handback_store.record_phase_asks_open(SESSION, self.repo_top, self.handback_ts, [dict(item) for item in asks],
                                              CONTEXT, "loop-a:2")

    def environment(self, **extra):
        return {**os.environ, **GIT_ENV, **self.ledger_env, "REVIEW_FIX_CLAUDE_DIR": str(CLAUDE_DIR),
                "CLAUDE_TOOLKIT_TELEMETRY": "1", **extra}

    def run_script(self, *args, **extra):
        done = subprocess.run(["python3", "-I", str(SCRIPT), *args], cwd=self.repo, text=True, capture_output=True,
                              env=self.environment(**extra))
        return done.returncode, done.stdout, done.stderr

    def outcome_rows(self):
        return [row for row in fake_ledger.recorded_rows(self.ledger_env) if "ask_outcome" in row]

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
        self.handback_ts = self.seed_handback()
        idless = {key: value for key, value in ASKS[0].items() if key != "finding_id"}
        handback_store.record_phase_asks_open(SESSION, self.repo_top, self.handback_ts, [idless], CONTEXT, "loop-b:2")

        code, _, _ = self.run_script("rule", "accepted:fixes a defect in scope")

        self.assertEqual(code, 0)
        ruled = self.store_rows(handback_store.PHASE_ASKS_RULED)[-1]
        minted = ruled["rulings"][0]["finding_id"]
        self.assertTrue(minted)
        self.assertEqual([row["finding_id"] for row in self.outcome_rows()], [minted])

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

    def test_a_newer_hand_back_leaves_the_asks_open_until_they_are_ruled(self):
        handback_store.record(SESSION, "handback", status="converged", message="", tree=None)

        list_code, list_output, _ = self.run_script("list")
        self.assertEqual(list_code, 0)
        self.assertIn("Rule on all 2 in order", list_output)
        self.assertIsNotNone(handback_store.unruled_phase_asks(SESSION, self.repo_top))

        rule_code, _, _ = self.run_script("rule", "accepted:a", "rejected:b")

        self.assertEqual(rule_code, 0)
        self.assertIsNone(handback_store.unruled_phase_asks(SESSION, self.repo_top))

    def test_an_unknown_verb_prints_the_usage_and_exits_two(self):
        code, _, errors = self.run_script("frobnicate")

        self.assertEqual(code, 2)
        self.assertIn("phase_asks.py rule", errors)


class OpenPhaseAsksTest(StoreCase):
    """`code_wait.py review` opens the asks of the phase packet once."""

    def setUp(self):
        super().setUp()
        module_spec = importlib.util.spec_from_file_location("code_wait", toolkit_paths.CODE_DIR / "code_wait.py")
        self.code_wait = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(self.code_wait)
        self.handback_ts = self.seed_handback()
        self.phase_dir = self.code_wait.phase_dir(self.repo)
        self.phase_dir.mkdir()
        (self.phase_dir / "pid").write_text("999999999")
        (self.phase_dir / self.code_wait.REVIEW_OUTPUT).write_text("packet printed\n")
        self.loop_folder = self.temp_root / "loop"
        self.loop_folder.mkdir()
        (self.phase_dir / self.code_wait.LOOP_DIR_FILE).write_text(f"{self.loop_folder}\n")
        self.code_wait.write_phase_run(self.repo, "code", "3")

    def wait(self, asks):
        (self.loop_folder / self.code_wait.reviewer_dispatch.PACKET_FILE).write_text(packet_with(asks))
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = self.code_wait.wait_review(self.repo)
        return code, output.getvalue()

    def test_a_packet_with_finding_asks_opens_one_row_however_often_the_wait_runs(self):
        for _call in range(2):
            code, output = self.wait(ASKS)
            self.assertEqual(code, 0)
            self.assertIn("2 finding ask(s) await your ruling", output)

        rows = self.store_rows(handback_store.PHASE_ASKS_OPEN)
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["repo"], rows[0]["handback_ts"]), (self.repo_top, self.handback_ts))
        self.assertEqual(rows[0]["context"]["lane"], "code")
        self.assertEqual(rows[0]["context"]["phase"], "3")
        self.assertEqual([item["file_line"] for item in rows[0]["asks"]], ["src/a.py:3", "src/a.py:9"])

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
        handback_store.record(SESSION, handback_store.PHASE_ASKS_RULED, repo=self.repo_top,
                              handback_ts=self.handback_ts, rulings=[])
        handback_store.record(SESSION, "handback", status="converged", message="", tree=None)

        code, output = self.wait(ASKS)

        self.assertEqual(code, 0)
        self.assertNotIn("await your ruling", output)
        self.assertEqual(len(self.store_rows(handback_store.PHASE_ASKS_OPEN)), 1)
        self.assertIsNone(handback_store.unruled_phase_asks(SESSION, self.repo_top))

    def test_a_packet_of_a_new_loop_opens_a_second_row(self):
        self.wait(ASKS)
        handback_store.record(SESSION, handback_store.PHASE_ASKS_RULED, repo=self.repo_top,
                              handback_ts=self.handback_ts, rulings=[])
        newer_ts = handback_store.record(SESSION, "handback", status="converged", message="", tree=None)["ts"]
        newer_loop = self.temp_root / "loop-newer"
        newer_loop.mkdir()
        (self.phase_dir / self.code_wait.LOOP_DIR_FILE).write_text(f"{newer_loop}\n")
        (newer_loop / self.code_wait.reviewer_dispatch.PACKET_FILE).write_text(packet_with(ASKS))

        with contextlib.redirect_stdout(io.StringIO()):
            self.code_wait.wait_review(self.repo)

        rows = self.store_rows(handback_store.PHASE_ASKS_OPEN)
        self.assertEqual([row["handback_ts"] for row in rows], [self.handback_ts, newer_ts])
        self.assertEqual(handback_store.unruled_phase_asks(SESSION, self.repo_top)["handback_ts"], newer_ts)

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

        context = self.store_rows(handback_store.PHASE_ASKS_OPEN)[0]["context"]
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

    def test_a_cap_reached_packet_with_asks_opens_nothing(self):
        packet = json.loads(packet_with(ASKS))
        packet["status"] = "cap-reached"
        packet.update({"open_classes": [], "unrun_reviewer": [], "full_check_tree": ""})

        lines = phase_asks.record_open(SESSION, self.repo_top, packet, {}, "loop-c:2")

        self.assertEqual(lines, [])
        self.assertEqual(self.store_rows(handback_store.PHASE_ASKS_OPEN), [])

    def test_a_cap_reached_packet_that_reads_as_deferred_opens_its_asks(self):
        packet = json.loads(packet_with(ASKS))
        packet["status"] = "cap-reached"
        packet.update({"open_classes": [], "unrun_reviewer": [],
                       "full_check_tree": reviewed_tree.fingerprint(self.repo_top)[1]})

        lines = phase_asks.record_open(SESSION, self.repo_top, packet, {}, "loop-c:2")

        self.assertTrue(lines)
        self.assertEqual(len(self.store_rows(handback_store.PHASE_ASKS_OPEN)), 1)


class RecordOpenWithNoHandbackTest(StoreCase):
    def test_a_repo_with_no_stored_hand_back_opens_nothing_and_says_so_on_stderr(self):
        errors = io.StringIO()

        with contextlib.redirect_stderr(errors):
            lines = phase_asks.record_open(SESSION, self.repo_top, json.loads(packet_with(ASKS)), {}, "loop-d:2")

        self.assertEqual(lines, [])
        self.assertIn("no stored hand-back", errors.getvalue())
        self.assertEqual(self.store_rows(handback_store.PHASE_ASKS_OPEN), [])


if __name__ == "__main__":
    unittest.main()
