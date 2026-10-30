"""Checks that the readers of producer packets run on packets a real producer wrote.

The fixtures under fixtures/packets are captured by tools/capture_packets.py: review-loop hand-backs (with the
full-check fields they carry) from the hand-back store, and coder reports from a bench run tree. A producer that changes
its format breaks a test here, where a hand-written input would still pass.

run: python3 tests/scripts/test_producer_packets.py
"""
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

import fake_ledger
import toolkit_paths

for folder in (toolkit_paths.REVIEW_DIR, toolkit_paths.LIB_DIR, toolkit_paths.CODE_DIR):
    sys.path.insert(0, str(folder))
import code_step_report  # noqa: E402
import full_check  # noqa: E402
import handback  # noqa: E402

PACKETS_DIR = pathlib.Path(__file__).resolve().parent / "fixtures" / "packets"
REVIEW_FIX = pathlib.Path(os.environ.get("REVIEW_FIX_SCRIPT") or toolkit_paths.REVIEW_DIR / "review_fix.py")
SESSION = "22222222-aaaa-bbbb-cccc-333333333333"
GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@example.com", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}


def captured(name):
    return (PACKETS_DIR / f"{name}.txt").read_text(encoding="utf-8")


def captured_names(prefix):
    return sorted(path.stem for path in PACKETS_DIR.glob(f"{prefix}*.txt"))


class CaptureFolderTest(unittest.TestCase):
    def test_every_capture_group_is_present(self):
        review = set(captured_names("review-loop-"))
        self.assertGreaterEqual(review, {"review-loop-converged-clean", "review-loop-converged-fixed",
                                         "review-loop-converged-asks", "review-loop-cap-reached",
                                         "review-loop-plan-impact", "review-loop-critical-blocker"})
        self.assertGreaterEqual(len(captured_names("full-check-")), 3)
        self.assertGreaterEqual(len(captured_names("coder-")), 3)

    def test_no_capture_names_the_real_home_directory(self):
        home = str(pathlib.Path.home())
        for path in PACKETS_DIR.glob("*.txt"):
            self.assertNotIn(home, path.read_text(encoding="utf-8"), path.name)


class ReviewLoopPacketTest(unittest.TestCase):
    def test_handback_reads_the_status_each_capture_was_stored_under(self):
        expected = {"review-loop-cap-reached": "cap-reached", "review-loop-plan-impact": "plan-impact",
                    "review-loop-critical-blocker": "critical-blocker", "review-loop-converged-clean": "converged",
                    "review-loop-converged-fixed": "converged", "review-loop-converged-asks": "converged"}
        for name, status in expected.items():
            with self.subTest(name):
                self.assertEqual(handback.load(captured(name))["status"], status)

    def test_a_converged_capture_is_a_clean_status_and_a_cap_or_blocker_is_not(self):
        self.assertIn(handback.load(captured("review-loop-converged-clean"))["status"], handback.CLEAN_STATUSES)
        for name in ("review-loop-cap-reached", "review-loop-critical-blocker", "review-loop-plan-impact"):
            self.assertNotIn(handback.load(captured(name))["status"], handback.CLEAN_STATUSES, name)

    def test_the_lists_the_loop_filled_come_back_as_entries_with_their_text(self):
        fixed = handback.load(captured("review-loop-converged-fixed"))["fixed"]
        self.assertTrue(fixed)
        self.assertTrue(all(entry["finding"] and entry["file_line"] for entry in fixed))

        asks = handback.load(captured("review-loop-converged-asks"))["ask"]
        self.assertTrue(asks)
        self.assertTrue(all(entry["question"] and entry["finding_id"] for entry in asks))

        remaining = handback.load(captured("review-loop-cap-reached"))["findings_remaining"]
        self.assertTrue(remaining)
        self.assertTrue(all(entry["finding"] for entry in remaining))

    def test_a_blocker_status_capture_names_its_blockers_and_a_plan_impact_capture_its_plan_impact(self):
        blockers = handback.load(captured("review-loop-critical-blocker"))["blockers"]
        self.assertTrue(blockers)
        self.assertTrue(handback.load(captured("review-loop-plan-impact"))["plan_impact"])

    def test_a_parsed_capture_renders_for_the_user(self):
        for name in captured_names("review-loop-"):
            with self.subTest(name):
                rendered = handback.render(handback.load(captured(name)), "review")
                self.assertTrue(rendered.strip())


class FullCheckResultTest(unittest.TestCase):
    def packet(self, name):
        return handback.load(captured(name))

    def test_each_full_check_capture_reads_as_the_result_its_name_says(self):
        results = {name: self.packet(name)["full_check"] for name in captured_names("full-check-")}
        self.assertEqual(results["full-check-passed"], full_check.PASSED)
        self.assertTrue(full_check.is_failure(results["full-check-failed"]), results["full-check-failed"])
        self.assertTrue(full_check.is_unverified(results["full-check-unverified"]))
        self.assertTrue(results["full-check-not-run"].startswith("not run"))

    def test_the_result_predicates_agree_with_the_captured_results(self):
        self.assertFalse(full_check.is_failure(self.packet("full-check-passed")["full_check"]))
        self.assertFalse(full_check.is_unverified(self.packet("full-check-passed")["full_check"]))
        self.assertFalse(full_check.is_check_not_run(self.packet("full-check-unverified")["full_check"]))
        self.assertFalse(full_check.is_check_not_run(self.packet("full-check-not-run")["full_check"]))

    def test_a_passed_capture_carries_the_runner_summary_the_producer_wrote(self):
        packet = self.packet("full-check-passed")
        self.assertTrue(packet["full_check_summary"])

    def test_the_user_lines_follow_the_captured_result(self):
        passed = handback.full_check_lines(self.packet("full-check-passed"))
        self.assertEqual([line for line in passed if line.startswith("Full check:")], [])

        not_run = handback.full_check_lines(self.packet("full-check-not-run"))
        self.assertTrue(any(line.startswith("Full check: not run") for line in not_run), not_run)

        unverified = handback.full_check_lines(self.packet("full-check-unverified"))
        self.assertTrue(any(line.startswith("Full check: unverified") for line in unverified), unverified)

        failed = handback.full_check_lines(self.packet("full-check-failed"))
        self.assertEqual([line for line in failed if line.startswith("Full check:")], [])


class ReviewFixPacketTest(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.temp_root = pathlib.Path(temp_dir.name)
        self.repo = self.temp_root / "repo"
        self.repo.mkdir()
        self.ledger_env = fake_ledger.install(self.temp_root)
        git_env = {**os.environ, **GIT_ENV}
        subprocess.run(["git", "init", "-q"], cwd=self.repo, env=git_env, check=True, capture_output=True)

    def run_packet(self, name, skill="review"):
        environment = {**os.environ, **GIT_ENV, **self.ledger_env, "HANDBACK_STORE_DIR": str(self.temp_root / "store"),
                       "CLAUDE_CODE_SESSION_ID": SESSION, "CLAUDE_TOOLKIT_TELEMETRY": "1"}
        done = subprocess.run(["python3", "-I", str(REVIEW_FIX), "packet", "--skill", skill], cwd=self.repo,
                              input=captured(name), text=True, capture_output=True, env=environment)
        return done.returncode, done.stdout + done.stderr

    def test_a_converged_clean_capture_renders_and_finishes(self):
        code, output = self.run_packet("review-loop-converged-clean")
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: render-and-finish", output)

    def test_a_capture_with_asks_presents_them(self):
        code, output = self.run_packet("review-loop-converged-asks")
        self.assertEqual(code, 0, output)
        self.assertNotIn("stop-parse-failure", output)
        self.assertIn("ACTION: present-asks", output)

    def test_no_capture_stops_for_a_parse_failure(self):
        for name in captured_names("review-loop-"):
            with self.subTest(name):
                _, output = self.run_packet(name)
                self.assertNotIn("stop-parse-failure", output)
                self.assertIn("ACTION:", output)

    def test_a_plan_impact_capture_is_presented_as_a_plan_impact(self):
        code, output = self.run_packet("review-loop-plan-impact")
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: redispatch", output)


class CoderReportTest(unittest.TestCase):
    def test_the_plan_impact_capture_yields_its_block(self):
        block = code_step_report.plan_impact_block(captured("coder-plan-impact"))
        self.assertTrue(block.startswith("PLAN-IMPACT:\n"), block)
        for key in ("assumed:", "found:", "changes:"):
            self.assertIn(key, block)

    def test_a_report_without_the_block_yields_none(self):
        self.assertIsNone(code_step_report.plan_impact_block(captured("coder-behavior")))
        self.assertIsNone(code_step_report.plan_impact_block(captured("coder-why")))

    def test_the_behavior_line_is_read_and_none_is_dropped(self):
        behavior = code_step_report.behavior_lines(captured("coder-behavior"))
        self.assertEqual(behavior, ["Finalizing an invoice returns its detail without a second database read of the "
                                    "lines inside the transaction."])
        self.assertEqual(code_step_report.behavior_lines(captured("coder-plan-impact")), [])

    def test_the_why_line_is_grouped_by_file_with_its_line_range(self):
        grouped = code_step_report.why_by_file(captured("coder-why"))
        self.assertEqual(len(grouped), 1)
        (path, notes), = grouped.items()
        self.assertTrue(path.endswith("spec.md"), path)
        self.assertEqual(notes[0]["lines"], "2497-2519")
        self.assertTrue(notes[0]["note"])
        self.assertEqual(code_step_report.why_by_file(captured("coder-behavior")), {})

    def test_a_report_with_no_marker_line_neither_escalates_nor_asks(self):
        # No stored coder report carries an OPEN QUESTIONS line or the escalation marker, so the capture proves only
        # that the readers leave a real report alone: prose that mentions /eng-spec is not the marker.
        for name in captured_names("coder-"):
            with self.subTest(name):
                self.assertEqual(code_step_report.open_questions(captured(name)), [])
                self.assertFalse(code_step_report.recommends_eng_spec(captured(name)))


if __name__ == "__main__":
    unittest.main()
