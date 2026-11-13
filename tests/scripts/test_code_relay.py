"""Tests for code_relay.py: the main session's word-for-word relay of the /code fork's last stop."""
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
import unittest.mock

import toolkit_paths

sys.path[:0] = [str(toolkit_paths.REVIEW_DIR), str(toolkit_paths.LIB_DIR)]
import handback_store  # noqa: E402
import reviewed_tree  # noqa: E402

SCRIPT = pathlib.Path(os.environ.get("CODE_RELAY_SCRIPT") or toolkit_paths.CODE_DIR / "code_relay.py")
SESSION = "relay-session"
RE_REVIEW_FEEDBACK = ("Re-run the review round on the current tree: files changed after the review "
                      "converged.")
UNREVIEWED_NOTE = "The tree changed after the converged review; this stop is unreviewed."
STOP = "Phase 2 complete. Stopped for your review.\n\nTo go on: /code resume <your feedback>"


class RelayTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.repo = pathlib.Path(folder.name)
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        self.run_folder = self.repo / ".git" / "code-phase"

    def write_stop(self, text):
        self.run_folder.mkdir(exist_ok=True)
        (self.run_folder / "stop.md").write_text(text)

    def relay(self):
        return subprocess.run([sys.executable, str(SCRIPT)], cwd=self.repo, capture_output=True, text=True,
                              check=False)

    def test_a_new_stop_prints_word_for_word_between_markers_under_the_no_tool_rule(self):
        self.write_stop(STOP + "\n")

        result = self.relay()

        self.assertEqual(result.returncode, 0, result.stderr)
        rule, body = result.stdout.split("-----BEGIN USER TEXT-----\n")
        self.assertIn("Make no other tool call", rule)
        self.assertEqual(body, STOP + "\n-----END USER TEXT-----\n")

    def test_a_stop_relayed_already_exits_1_and_says_to_relay_the_skill_result(self):
        self.write_stop(STOP)
        self.relay()

        result = self.relay()

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("relayed already", result.stderr)
        self.assertIn("Skill result word for word", result.stderr)

    def test_a_rewritten_stop_relays_again(self):
        self.write_stop(STOP)
        self.relay()
        os.utime(self.run_folder / "stop.md", ns=(1, 1))

        result = self.relay()

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_a_newer_review_stop_relays_in_place_of_the_code_stop(self):
        self.write_stop(STOP)
        os.utime(self.run_folder / "stop.md", ns=(1, 1))
        review_stop = "Review converged.\n\nTo go on: /review resume <your feedback>"
        (self.run_folder / "review-stop.md").write_text(review_stop)

        result = self.relay()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(review_stop, result.stdout)
        self.assertNotIn("Phase 2 complete", result.stdout)

    def test_a_finished_stop_says_to_go_on_with_the_invoking_skill(self):
        self.run_folder.mkdir()
        (self.run_folder / "review-stop.md").write_text("Review converged. Nothing is outstanding.\n")

        result = self.relay()

        self.assertEqual(result.returncode, 0, result.stderr)
        rule = result.stdout.split("-----BEGIN USER TEXT-----\n")[0]
        self.assertIn("go on with that skill's next step", rule)
        self.assertNotIn("Make no other tool call before", rule)

    def test_a_stop_moved_aside_by_phase_start_is_not_replaced_by_an_older_review_stop(self):
        self.run_folder.mkdir()
        review_stop = self.run_folder / "review-stop.md"
        review_stop.write_text("Review converged.\n\nTo go on: /review resume <your feedback>")
        os.utime(review_stop, ns=(1, 1))
        self.relay()
        self.write_stop(STOP)
        self.relay()
        relayed_before = (self.run_folder / "relayed").read_text()
        # phase_start moves the stale stop.md aside; os.replace keeps its mtime.
        os.replace(self.run_folder / "stop.md", self.run_folder / "stop.prev.md")

        result = self.relay()

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("stop.prev.md is the stop phase_start moved aside", result.stderr)
        self.assertEqual((self.run_folder / "relayed").read_text(), relayed_before)

    def test_only_a_moved_aside_stop_exits_1_and_relays_nothing(self):
        self.run_folder.mkdir()
        (self.run_folder / "stop.prev.md").write_text(STOP)

        result = self.relay()

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertFalse((self.run_folder / "relayed").exists())

    def test_a_review_stop_newer_than_the_moved_aside_stop_relays_normally(self):
        self.write_stop(STOP)
        os.replace(self.run_folder / "stop.md", self.run_folder / "stop.prev.md")
        os.utime(self.run_folder / "stop.prev.md", ns=(1, 1))
        review_stop = "Review converged.\n\nTo go on: /review resume <your feedback>"
        (self.run_folder / "review-stop.md").write_text(review_stop)

        result = self.relay()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(review_stop, result.stdout)
        self.assertTrue((self.run_folder / "relayed").exists())

    def test_no_stop_file_exits_1_and_says_to_relay_the_skill_result(self):
        result = self.relay()

        self.assertEqual(result.returncode, 1)
        self.assertIn("no stop file", result.stderr)


class ReviewedTreeRelayTest(unittest.TestCase):
    """A stop that waits on the user, after a converged review, in a tree whose source changed since."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.tmp = pathlib.Path(folder.name)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.run_folder = self.repo / ".git" / "code-phase"
        self.git("init", "-q")
        (self.repo / "app.py").write_text("x = 1\n")
        self.commit("first", "2000-01-01T00:00:00Z")

        environment = unittest.mock.patch.dict(os.environ, {"HOME": str(self.home)})
        environment.start()
        self.addCleanup(environment.stop)
        self.top = str(self.repo.resolve())
        self.hand_back_clean_review()
        self.write_stop(STOP)

    def git(self, *args, **extra_env):
        env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
               "GIT_COMMITTER_EMAIL": "t@t", **extra_env}
        subprocess.run(["git", "-C", str(self.repo), *args], check=True, env=env, capture_output=True)

    def commit(self, message, when):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message, GIT_COMMITTER_DATE=when, GIT_AUTHOR_DATE=when)

    def hand_back_clean_review(self):
        handback_store.record(SESSION, "dispatch", repo=self.top, tool_use_id="toolu_1")
        handback_store.record(SESSION, "dispatch-ran", tool_use_id="toolu_1")
        handback_store.record_handback(SESSION, status="converged", message="")
        reviewed_tree.record_reviewed(SESSION, self.repo)

    def write_stop(self, text):
        self.run_folder.mkdir(exist_ok=True)
        (self.run_folder / "stop.md").write_text(text)

    def relay(self, session=SESSION, cwd=None):
        env = {**os.environ, "HOME": str(self.home)}
        env.pop("CLAUDE_CODE_SESSION_ID", None)
        if session:
            env["CLAUDE_CODE_SESSION_ID"] = session
        return subprocess.run([sys.executable, str(SCRIPT)], cwd=cwd or self.repo, capture_output=True, text=True,
                              check=False, env=env)

    def assert_relayed(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("-----BEGIN USER TEXT-----", result.stdout)
        self.assertTrue((self.run_folder / "relayed").exists())

    def test_a_stop_in_the_reviewed_tree_relays_as_before(self):
        result = self.relay()

        self.assert_relayed(result)

    def test_a_source_edit_after_the_review_sends_the_stop_back_for_review_and_leaves_relayed_unwritten(self):
        (self.repo / "app.py").write_text("x = 2\n")

        result = self.relay()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(RE_REVIEW_FEEDBACK, result.stdout)
        self.assertIn(STOP.splitlines()[-1], result.stdout)
        self.assertNotIn("USER TEXT", result.stdout)
        self.assertFalse((self.run_folder / "relayed").exists())

    def test_a_stop_bounced_once_relays_when_the_resume_wrote_no_new_stop(self):
        (self.repo / "app.py").write_text("x = 2\n")
        bounced = self.relay()
        self.assertIn(RE_REVIEW_FEEDBACK, bounced.stdout)

        result = self.relay()

        self.assert_relayed(result)
        self.assertIn(UNREVIEWED_NOTE, result.stdout.split("-----BEGIN USER TEXT-----\n")[1].split(STOP)[0])

    def test_a_bounced_stop_moved_aside_by_phase_start_relays_once_with_the_unreviewed_note(self):
        (self.repo / "app.py").write_text("x = 2\n")
        self.assertIn(RE_REVIEW_FEEDBACK, self.relay().stdout)
        # phase_start moves the stop.md aside on resume; os.replace keeps its mtime.
        os.replace(self.run_folder / "stop.md", self.run_folder / "stop.prev.md")

        result = self.relay()

        self.assert_relayed(result)
        self.assertIn(UNREVIEWED_NOTE, result.stdout.split("-----BEGIN USER TEXT-----\n")[1].split(STOP)[0])
        self.assertEqual(self.relay().returncode, 1)

    def bounce_and_move_stop_aside(self):
        (self.repo / "app.py").write_text("x = 2\n")
        self.assertIn(RE_REVIEW_FEEDBACK, self.relay().stdout)
        os.replace(self.run_folder / "stop.md", self.run_folder / "stop.prev.md")

    def test_a_bounced_stop_moved_aside_relays_without_the_note_once_the_tree_is_reverted(self):
        self.bounce_and_move_stop_aside()
        (self.repo / "app.py").write_text("x = 1\n")

        result = self.relay()

        self.assert_relayed(result)
        self.assertNotIn(UNREVIEWED_NOTE, result.stdout)

    def test_a_moved_aside_stop_exits_1_when_bounced_holds_another_stamp_or_it_was_relayed(self):
        self.bounce_and_move_stop_aside()
        stamp = (self.run_folder / "bounced").read_text()
        cases = {"stale bounced stamp": ("bounced", "stop.md 1\n"),
                 "stop already relayed": ("relayed", stamp)}
        for name, (file_name, text) in cases.items():
            with self.subTest(name):
                (self.run_folder / "bounced").write_text(stamp)
                (self.run_folder / "relayed").unlink(missing_ok=True)
                (self.run_folder / file_name).write_text(text)

                self.assertEqual(self.relay().returncode, 1)

    def test_a_handback_stored_within_a_second_before_a_commit_does_not_count_as_after_it(self):
        stored_at = handback_store.latest_for_repo(SESSION, self.top)["handback"]["ts"]
        (self.repo / "app.py").write_text("x = 2\n")
        self.commit("second", f"{int(stored_at)} +0000")
        (self.repo / "app.py").write_text("x = 3\n")

        result = self.relay()

        self.assert_relayed(result)
        self.assertNotIn(UNREVIEWED_NOTE, result.stdout)

    def test_a_new_stop_written_after_a_bounce_bounces_again(self):
        (self.repo / "app.py").write_text("x = 2\n")
        self.assertIn(RE_REVIEW_FEEDBACK, self.relay().stdout)
        os.utime(self.run_folder / "stop.md", ns=(1, 1))

        result = self.relay()

        self.assertIn(RE_REVIEW_FEEDBACK, result.stdout)

    def test_a_tree_that_cannot_be_fingerprinted_relays(self):
        (self.repo / "app.py").write_text("x = 2\n")
        # An untracked nested repository makes the fingerprint fail.
        nested = self.repo / "nested"
        nested.mkdir()
        subprocess.run(["git", "init", "-q", str(nested)], check=True)
        self.assertIsNone(reviewed_tree.reviewed_fingerprint(self.repo))

        result = self.relay()

        self.assert_relayed(result)

    def test_a_notes_edit_after_the_review_relays(self):
        (self.repo / "docs" / "plans").mkdir(parents=True)
        (self.repo / "docs" / "plans" / "x.md").write_text("notes\n")
        status = subprocess.run(["git", "-C", str(self.repo), "status", "--porcelain", "--untracked-files=all"],
                                capture_output=True, text=True, check=True).stdout
        self.assertIn("?? docs/plans/x.md", status)
        self.assertTrue(reviewed_tree.is_reviewed(SESSION, self.repo))

        result = self.relay()

        self.assert_relayed(result)

    def test_a_commit_after_the_review_relays(self):
        (self.repo / "app.py").write_text("x = 2\n")
        self.commit("second", "2090-01-01T00:00:00Z")

        result = self.relay()

        self.assert_relayed(result)

    def test_no_session_id_relays(self):
        (self.repo / "app.py").write_text("x = 2\n")

        result = self.relay(session=None)

        self.assert_relayed(result)

    def test_a_finished_stop_in_an_edited_tree_relays_as_finished(self):
        (self.repo / "app.py").write_text("x = 2\n")
        self.write_stop("Review converged. Nothing is outstanding.\n")

        result = self.relay()

        self.assert_relayed(result)
        self.assertIn("go on with that skill's next step", result.stdout)

    def test_a_blocked_hand_back_in_an_edited_tree_relays(self):
        handback_store.record("blocked-session", "dispatch", repo=self.top, tool_use_id="toolu_2")
        handback_store.record("blocked-session", "dispatch-ran", tool_use_id="toolu_2")
        handback_store.record_handback("blocked-session", status="blocked", message="")
        (self.repo / "app.py").write_text("x = 2\n")

        result = self.relay(session="blocked-session")

        self.assert_relayed(result)

    def test_a_session_with_no_hand_back_in_an_edited_tree_relays(self):
        (self.repo / "app.py").write_text("x = 2\n")

        result = self.relay(session="other")

        self.assert_relayed(result)

    def test_a_repo_with_no_commit_relays(self):
        empty = self.tmp / "empty"
        empty.mkdir()
        subprocess.run(["git", "init", "-q", str(empty)], check=True)
        empty_top = str(empty.resolve())
        handback_store.record("empty-session", "dispatch", repo=empty_top, tool_use_id="toolu_3")
        handback_store.record("empty-session", "dispatch-ran", tool_use_id="toolu_3")
        handback_store.record_handback("empty-session", status="converged", message="")
        (empty / "app.py").write_text("x = 1\n")
        self.run_folder = empty / ".git" / "code-phase"
        self.write_stop(STOP)

        result = self.relay(session="empty-session", cwd=empty)

        self.assert_relayed(result)


if __name__ == "__main__":
    unittest.main()
