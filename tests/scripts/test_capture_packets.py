"""Checks for capture_packets.py: the scrub, the secret filter, the category choice and where it writes."""
import contextlib
import importlib.util
import io
import json
import os
import pathlib
import tempfile
import unittest

import toolkit_paths

SCRIPT = pathlib.Path(os.environ.get("CAPTURE_PACKETS_SCRIPT") or toolkit_paths.TOOLS_DIR / "capture_packets.py")
spec = importlib.util.spec_from_file_location("capture_packets_under_test", str(SCRIPT))
capture_packets = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture_packets)

CLEAN_PACKET = json.dumps({"status": "converged", "iter": 1, "fixed": [], "ask": [], "class_closure": "n/a"})
FIXED_PACKET = json.dumps({"status": "converged", "iter": 1, "class_closure": "all uses read",
                           "fixed": [{"finding": "a bug in /home/someone/repo/a.py", "file_line": "a.py:1"}],
                           "files_touched": ["a.py"]})
CHECKED_PACKET = json.dumps({"status": "converged", "iter": 2, "class_closure": "all uses read",
                             "fixed": [{"finding": "another bug", "file_line": "b.py:1"}],
                             "files_touched": ["b.py"], "full_check": "not run (CI)"})
CODER_REPORT = ("Done.\n\nBEHAVIOR: orders answer 409\nWHY: src/a.py 3-9 — the guard sits first\n"
                "REVIEW: recommended — src/a.py")


class CapturePacketsTest(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.root = pathlib.Path(temp_dir.name)
        self.store = self.root / "store"
        self.store.mkdir()
        self.out = self.root / "out"

    def write_store(self, *messages):
        rows = [{"kind": "handback", "message": message} for message in messages]
        rows.insert(0, {"kind": "dispatch", "message": "not a hand-back"})
        (self.store / "s1.jsonl").write_text("\n".join(json.dumps(row) for row in rows) + "\n")

    def write_tree(self, report):
        row = {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "SubagentHandback", "input": {"message": report}}]}}
        (self.root / "tree").mkdir(exist_ok=True)
        (self.root / "tree" / "main.jsonl").write_text(json.dumps(row) + "\n")

    def test_full_check_category_maps_each_full_check_result(self):
        full_check = capture_packets.full_check
        expected = {
            full_check.PASSED: "full-check-passed",
            full_check.CHECK_ONLY_PASSED: None,
            full_check.UNVERIFIED: "full-check-unverified",
            full_check.PRE_EXISTING: None,
            "failed (exit 1)": "full-check-failed",
            "not run (CI)": "full-check-not-run",
        }
        for result, category in expected.items():
            with self.subTest(result=result):
                self.assertEqual(capture_packets.full_check_category(result), category)

    def test_a_store_capture_writes_one_scrubbed_file_per_category(self):
        self.write_store(CLEAN_PACKET, FIXED_PACKET, CHECKED_PACKET)
        written = capture_packets.capture("store", self.store, self.out)
        self.assertEqual([path.name for path in written],
                         ["full-check-not-run.txt", "review-loop-converged-clean.txt",
                          "review-loop-converged-fixed.txt"])
        fixed = (self.out / "review-loop-converged-fixed.txt").read_text()
        self.assertIn("/home/captured/repo/a.py", fixed)
        self.assertNotIn("/home/someone", fixed)

    def test_a_category_keeps_the_shortest_packet_that_fits_it(self):
        long_packet = json.dumps({"status": "converged", "iter": 1, "fixed": [], "ask": [], "class_closure": "n/a",
                                  "nit": [{"finding": "a long nit " * 20, "file_line": "a.py:1"}]})
        self.write_store(long_packet, CLEAN_PACKET)
        capture_packets.capture("store", self.store, self.out)
        self.assertEqual((self.out / "review-loop-converged-clean.txt").read_text(), CLEAN_PACKET)

    def test_a_store_capture_files_asks_and_non_converged_statuses_and_a_failed_check(self):
        asks = json.dumps({"status": "converged", "iter": 1, "fixed": [], "class_closure": "n/a",
                           "ask": [{"question": "which one?", "finding_id": "F1", "file_line": "a.py:1",
                                    "change": "rename it"}]})
        cap_reached = json.dumps({"status": "cap-reached", "iter": 2, "fixed": [], "class_closure": "n/a",
                                  "findings_remaining": [{"disposition": "fix", "finding": "left over"}]})
        failed_check = json.dumps({"status": "critical-blocker", "iter": 1, "fixed": [], "class_closure": "n/a",
                                   "blockers": ["the check fails with a long reason"], "full_check": "failed (exit 1)"})
        plan_impact = json.dumps({"status": "plan-impact", "iter": 1, "fixed": [], "class_closure": "n/a",
                                  "plan_impact": "PLAN-IMPACT:\nassumed: a\nfound: b\nchanges: c"})
        blocker = json.dumps({"status": "critical-blocker", "iter": 1, "fixed": [], "class_closure": "n/a",
                              "blockers": ["a blocker"]})
        self.write_store(asks, cap_reached, plan_impact, blocker, failed_check)
        written = capture_packets.capture("store", self.store, self.out)
        self.assertEqual([path.name for path in written],
                         ["full-check-failed.txt", "review-loop-cap-reached.txt", "review-loop-converged-asks.txt",
                          "review-loop-critical-blocker.txt", "review-loop-plan-impact.txt"])

    def test_a_tree_capture_reads_the_handback_report_row_form(self):
        row = {"handback_report": {"text": CODER_REPORT}}
        (self.root / "tree").mkdir(exist_ok=True)
        (self.root / "tree" / "main.jsonl").write_text(json.dumps(row) + "\n")
        written = capture_packets.capture("tree", self.root / "tree", self.out)
        self.assertEqual([path.name for path in written], ["coder-behavior.txt"])

    def test_a_packet_that_quotes_a_secret_is_dropped(self):
        leaking = json.dumps({"status": "converged", "iter": 1, "fixed": [], "ask": [], "class_closure": "n/a",
                              "nit": [{"finding": "mail ops@example.com", "file_line": "a.py:1"}]})
        self.write_store(leaking)
        self.assertEqual(capture_packets.capture("store", self.store, self.out), [])

    def test_the_old_free_text_form_is_not_captured(self):
        self.write_store("status: converged\niter: 1\nfixed: []\nask: []\nclass_closure: n/a\n")
        self.assertEqual(capture_packets.capture("store", self.store, self.out), [])

    def test_a_coder_report_in_two_categories_is_written_once_under_the_first(self):
        self.write_tree(CODER_REPORT)
        written = capture_packets.capture("tree", self.root / "tree", self.out)
        self.assertEqual(sorted(path.name for path in written), ["coder-behavior.txt"])
        self.assertEqual(capture_packets.coder_categories(CODER_REPORT), ["coder-why", "coder-behavior"])

    def test_coder_categories_tell_a_found_plan_impact_block_from_the_bare_fallback_line(self):
        found = "Done.\n\nPLAN-IMPACT:\n  assumed: a\n  found: b\n  changes: c\n"
        self.assertEqual(capture_packets.coder_categories(found), ["coder-plan-impact"])
        self.assertEqual(capture_packets.coder_categories("Done.\n\nPLAN-IMPACT: yes\n"), [])

    def test_coder_categories_catch_open_questions_only_when_a_question_is_listed(self):
        self.assertEqual(capture_packets.coder_categories('OPEN QUESTIONS: ["which table?"]\n'),
                         ["coder-open-questions"])
        self.assertEqual(capture_packets.coder_categories("OPEN QUESTIONS: none\n"), [])

    def test_a_slashed_eng_spec_marker_falls_into_coder_eng_spec(self):
        report = "Too large for one agent.\n\nRECOMMEND: /eng-spec\n"
        self.assertEqual(capture_packets.coder_categories(report), ["coder-eng-spec"])

    def test_main_prints_each_file_it_wrote_and_nothing_else_leaves_the_fixtures_folder(self):
        self.write_store(CLEAN_PACKET)
        self.assertEqual(capture_packets.FIXTURES_DIR.parts[-4:], ("tests", "scripts", "fixtures", "packets"))
        self.addCleanup(setattr, capture_packets, "FIXTURES_DIR", capture_packets.FIXTURES_DIR)
        capture_packets.FIXTURES_DIR = self.out
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = capture_packets.main(["capture_packets.py", "store", str(self.store)])
        self.assertEqual(code, 0)
        lines = output.getvalue().splitlines()
        self.assertEqual(lines, [f"wrote {self.out / 'review-loop-converged-clean.txt'}"])
        outside_store = sorted(p.name for p in self.root.rglob("*") if p.is_file() and self.store not in p.parents)
        self.assertEqual(outside_store, ["review-loop-converged-clean.txt"])

    def test_main_rejects_tree_with_no_path_and_a_bad_verb_with_the_usage(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(capture_packets.main(["capture_packets.py", "tree"]), 2)
            self.assertEqual(capture_packets.main(["capture_packets.py", "bogus"]), 2)

    def test_main_exits_1_when_no_packet_fits_a_category(self):
        self.write_store("status: converged\niter: 1\nfixed: []\nask: []\nclass_closure: n/a\n")
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = capture_packets.main(["capture_packets.py", "store", str(self.store)])
        self.assertEqual(code, 1)
        self.assertEqual(output.getvalue(), "")
        self.assertIn("no packet fit a category", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
