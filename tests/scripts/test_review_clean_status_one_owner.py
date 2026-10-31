"""Every site that judges whether a review ended clean gives the same answer for the same stored hand-back rows,
because each one asks handback.py: the `review-gate-mark clean` hook, the commit credit of a hand-back, and the
/code phase's review gate.

run: python3 tests/scripts/test_review_clean_status_one_owner.py
"""
import contextlib
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

import toolkit_paths

for folder in (toolkit_paths.LIB_DIR, toolkit_paths.REVIEW_DIR, toolkit_paths.CODE_DIR):
    sys.path.insert(0, str(folder))
import code_step_boundary  # noqa: E402
import code_step_state  # noqa: E402
import handback  # noqa: E402
import handback_store  # noqa: E402
import review_commit_gate  # noqa: E402
import reviewed_tree  # noqa: E402

SESSION = "s1"
DISPATCH = {"kind": "dispatch", "session_id": SESSION}


def handback_row(status, **extra):
    return {"kind": "handback", "session_id": SESSION, "status": status, "ts": time.time(), **extra}


# Stored rows after the dispatch, and whether the review counts as clean.
STORED_ROWS = {
    "converged": ([handback_row("converged")], True),
    "deferred": ([handback_row("deferred")], True),
    "cap-reached": ([handback_row("cap-reached", message=json.dumps({
        "status": "cap-reached", "iter": 2, "fixed": [],
        "findings_remaining": [{"disposition": "fix", "finding": "edge case", "file_line": "a.py:1"}]}))], False),
    "plan-impact": ([handback_row("plan-impact")], False),
    "converged with no reviewer run": ([handback_row("converged", no_reviewer=True)], False),
    "no hand-back yet": ([], False),
    "dispatched again after the hand-back": ([handback_row("converged"), DISPATCH], False),
}


class CleanStatusOneOwnerTest(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = pathlib.Path(temp_dir.name)
        self.home = root / "home"
        self.home.mkdir()
        self.repo = root / "repo"
        self.repo.mkdir()
        env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
               "GIT_COMMITTER_EMAIL": "t@t"}
        for argv in (["init", "-q"], ["commit", "-q", "--allow-empty", "-m", "base"]):
            subprocess.run(["git", "-C", str(self.repo), *argv], check=True, capture_output=True, env=env)
        self.repo = self.repo.resolve()
        self.state_file = root / "gate-state"
        self.store = root / "store"
        self.store.mkdir()
        for patcher in (mock.patch.object(pathlib.Path, "home", return_value=self.home),
                        mock.patch.dict(os.environ, {"HANDBACK_STORE_DIR": str(self.store)}),
                        mock.patch.object(code_step_boundary, "session_pin", lambda: SESSION)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def store_rows(self, rows, dispatch_repo=True):
        """The rows after a dispatch of this repo (`dispatch_repo`) or after a dispatch row that names no repo."""
        dispatch = {**DISPATCH, "repo": str(self.repo)} if dispatch_repo else dict(DISPATCH)
        all_rows = [dispatch, *rows]
        (self.store / f"{SESSION}.jsonl").write_text("".join(json.dumps(row) + "\n" for row in all_rows))

    def clean_by_commit_credit(self):
        return review_commit_gate.review_handed_back_since(SESSION, 0, str(self.repo))

    def clean_by_phase_gate(self):
        # The /code run stores the effective status of the packet it read as review_status.
        seen = handback_store.latest(SESSION)
        review_status = handback.stored_effective_status(seen) if seen["handback"] else None
        state = code_step_state.RunState(stage="review", session_id=SESSION, review_status=review_status)
        with contextlib.redirect_stdout(io.StringIO()), mock.patch.object(code_step_boundary, "save_state"):
            return code_step_boundary.mark_review_gate_clean(self.repo, state)

    def sites(self):
        return {"owner": lambda: handback.false_clean_reason(SESSION) is None,
                "record_clean_review": lambda: handback.record_clean_review(SESSION)[0] is None,
                "commit credit": self.clean_by_commit_credit,
                "phase review gate": self.clean_by_phase_gate}

    def cap_row(self, tree="current", **packet_fields):
        """A stored cap-reached hand-back whose passed full check covered `tree` ("current": the repo's tree now)."""
        if tree == "current":
            tree = reviewed_tree.fingerprint(self.repo)[1]
        packet = {"status": "cap-reached", "iter": 2, "fixed": [], "full_check": "passed", "full_check_tree": tree,
                  "findings_remaining": [{"disposition": "fix", "finding": "edge case", "file_line": "a.py:1",
                                          "blocker": False}], **packet_fields}
        return handback_row("cap-reached", message=json.dumps(packet))

    def test_a_capped_review_with_no_blocker_and_a_passed_check_of_the_final_tree_is_clean_at_every_site(self):
        self.store_rows([self.cap_row()])
        for site, judge in self.sites().items():
            with self.subTest(site=site):
                self.assertTrue(judge())

    def test_a_capped_review_stays_capped_when_the_check_is_old_or_not_passed_or_a_blocker_is_open(self):
        blocker = {"disposition": "fix", "finding": "bug", "file_line": "a.py:1", "blocker": True}
        cases = {
            "check older than the last fix": self.cap_row(tree="sha256:0"),
            "check with no tree": self.cap_row(tree=""),
            "check unverified": self.cap_row(full_check="unverified (exit 0, no runner summary)"),
            "check not run": self.cap_row(full_check="not run (timeout)"),
            "check only, CI runs the suite": self.cap_row(full_check="passed (check only; CI runs the full suite)"),
            "open blocker item": self.cap_row(findings_remaining=[blocker]),
            "blockers entry": self.cap_row(blockers=["the gate is red"]),
            "open class": self.cap_row(open_classes=["a log with a trailing blank line"]),
            "scoped reviewer that could not run": self.cap_row(unrun_reviewer="the reviewer was refused"),
            "dispatch that names no repo": self.cap_row(),
        }
        for label, row in cases.items():
            self.store_rows([row], dispatch_repo=label != "dispatch that names no repo")
            for site, judge in self.sites().items():
                with self.subTest(case=label, site=site):
                    self.assertFalse(judge())

    def test_a_fix_after_the_passed_check_turns_a_deferrable_cap_back_to_capped(self):
        self.store_rows([self.cap_row()])
        (self.repo / "late_fix.py").write_text("x = 1\n")

        self.assertIn("cap-reached", handback.false_clean_reason(SESSION))

    def test_every_site_gives_the_one_answer_of_the_owner_for_the_same_rows(self):
        sites = self.sites()
        for label, (rows, expected) in STORED_ROWS.items():
            self.store_rows(rows)
            for site, judge in sites.items():
                with self.subTest(rows=label, site=site):
                    self.assertEqual(expected, judge())

    def test_a_clean_review_records_the_dispatch_repo_tree_and_a_refused_one_records_nothing(self):
        for label, (rows, expected) in STORED_ROWS.items():
            with self.subTest(rows=label):
                self.store_rows(rows)
                reviewed_tree.reviewed_file(SESSION).unlink(missing_ok=True)

                handback.record_clean_review(SESSION)

                self.assertEqual(expected, reviewed_tree.is_reviewed(SESSION, self.repo))


if __name__ == "__main__":
    unittest.main()
