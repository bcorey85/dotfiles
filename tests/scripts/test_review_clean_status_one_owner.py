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
    "cap-reached": ([handback_row("cap-reached")], False),
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

    def store_rows(self, rows):
        all_rows = [{**DISPATCH, "repo": str(self.repo)}, *rows]
        (self.store / f"{SESSION}.jsonl").write_text("".join(json.dumps(row) + "\n" for row in all_rows))

    def clean_by_mark_hook(self):
        try:
            review_commit_gate.apply_mark("clean", SESSION, str(self.state_file))
        except review_commit_gate.DenyError:
            return False
        return True

    def clean_by_commit_credit(self):
        return review_commit_gate.review_handed_back_since(SESSION, 0, str(self.repo))

    def clean_by_phase_gate(self):
        state = code_step_state.RunState(stage="review", session_id=SESSION)
        with contextlib.redirect_stdout(io.StringIO()), mock.patch.object(code_step_boundary, "save_state"):
            return code_step_boundary.mark_review_gate_clean(self.repo, state)

    def test_every_site_gives_the_one_answer_of_the_owner_for_the_same_rows(self):
        sites = {"owner": lambda: handback.false_clean_reason(SESSION) is None,
                 "record_clean_review": lambda: handback.record_clean_review(SESSION)[0] is None,
                 "review-gate-mark clean": self.clean_by_mark_hook,
                 "commit credit": self.clean_by_commit_credit,
                 "phase review gate": self.clean_by_phase_gate}
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
