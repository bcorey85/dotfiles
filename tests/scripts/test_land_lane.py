"""Tests for tools/land_lane.py: a lane branch lands on master in one run."""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from toolkit_paths import LAND_LANE_SCRIPT, TOOLS_DIR

if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
import land_lane
import suite_receipt

SUITE_RECEIPT_SCRIPT = TOOLS_DIR / "suite_receipt.py"

GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


class LandLaneTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.tmp = pathlib.Path(temp.name)
        # pull_keep_index.py, which land_lane.py runs last, reads the session folder and id.
        config_dir = self.tmp / "claude-config"
        (config_dir / "sessions").mkdir(parents=True)
        environment = {**GIT_ENV, "CLAUDE_CONFIG_DIR": str(config_dir), "CLAUDE_CODE_SESSION_ID": "self-id"}
        patcher = unittest.mock.patch.dict(os.environ, environment)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.marker = self.tmp / "suite-ran"
        self.remote = self.tmp / "origin.git"
        self.git(self.tmp, "init", "-q", "--bare", "-b", "master", str(self.remote))
        self.main = self.clone("main")
        self.write(self.main, "shared.txt", "1\n")
        self.write(self.main, "other.txt", "1\n")
        self.git(self.main, "add", "-A")
        self.git(self.main, "commit", "-qm", "one")
        self.git(self.main, "push", "-q", "-u", "origin", "HEAD:master")
        # A lane is a worktree of the main checkout, so the two share one object store.
        self.lane = self.tmp / "lane"
        self.git(self.main, "worktree", "add", "-q", "-b", "lane", str(self.lane))
        self.write_suite(f"touch {self.marker}")

    def git(self, folder, *arguments):
        finished = subprocess.run(["git", "-C", str(folder), *arguments], capture_output=True, text=True)
        self.assertEqual(finished.returncode, 0, finished.stderr)
        return finished.stdout.strip()

    def clone(self, name):
        folder = self.tmp / name
        self.git(self.tmp, "clone", "-q", str(self.remote), str(folder))
        return folder

    def write(self, folder, name, text):
        (folder / name).write_text(text)

    def lane_commit(self, name, text):
        self.write(self.lane, name, text)
        self.git(self.lane, "add", name)
        self.git(self.lane, "commit", "-qm", f"lane {name}")

    def push_from_elsewhere(self, name, text):
        other = self.clone("elsewhere")
        self.write(other, name, text)
        self.git(other, "add", name)
        self.git(other, "commit", "-qm", f"elsewhere {name}")
        self.git(other, "push", "-q", "origin", "HEAD:master")
        shutil.rmtree(other)

    def write_suite(self, commands):
        """Commit the lane's own tests/run.sh, the suite land_lane.py runs."""
        (self.lane / "tests").mkdir(exist_ok=True)
        self.write(self.lane / "tests", "run.sh", commands + "\n")
        self.git(self.lane, "add", "tests/run.sh")
        self.git(self.lane, "commit", "-qm", "lane suite")

    def land(self, suite=None, extra_env=None, extra_arguments=()):
        if suite:
            self.write_suite(suite)
        env = {**os.environ, **(extra_env or {})}
        return subprocess.run([sys.executable, str(LAND_LANE_SCRIPT), str(self.lane), "--main", str(self.main),
                               *extra_arguments], capture_output=True, text=True, env=env)

    def origin_master(self):
        return self.git(self.remote, "rev-parse", "master")

    def test_origin_ahead_lands_in_one_run(self):
        self.lane_commit("lane.txt", "lane\n")
        self.push_from_elsewhere("elsewhere.txt", "e\n")
        finished = self.land()
        self.assertEqual(finished.returncode, 0, finished.stdout + finished.stderr)
        self.assertEqual(self.origin_master(), self.git(self.lane, "rev-parse", "HEAD"))
        self.assertTrue(self.marker.exists())
        self.assertTrue((self.main / "lane.txt").exists())
        short_hash = self.git(self.lane, "rev-parse", "--short", "HEAD")
        self.assertIn(f"land_lane: merged, suite ran; pushed {short_hash} to origin/master", finished.stdout)

    def test_merge_leaving_the_tree_unchanged_runs_the_suite_without_a_receipt(self):
        self.lane_commit("lane.txt", "lane\n")
        # The same change reaches master by another commit, so the merge adds nothing to the lane tree.
        self.push_from_elsewhere("lane.txt", "lane\n")
        finished = self.land()
        self.assertEqual(finished.returncode, 0, finished.stdout + finished.stderr)
        self.assertTrue(self.marker.exists())
        self.assertIn("merged, suite ran", finished.stdout)
        self.assertEqual(self.origin_master(), self.git(self.lane, "rev-parse", "HEAD"))

    def test_main_changes_to_lane_files_stop_before_the_push(self):
        self.write(self.lane, "shared.txt", "lane\n")
        (self.lane / "other.txt").unlink()
        self.git(self.lane, "add", "-A")
        self.git(self.lane, "commit", "-qm", "lane edits")
        before = self.origin_master()
        self.git(self.main, "rm", "-q", "other.txt")
        self.write(self.main, "shared.txt", "dirty\n")
        finished = self.land()
        self.assertEqual(finished.returncode, 1)
        self.assertIn("other.txt", finished.stdout)
        self.assertIn("shared.txt", finished.stdout)
        self.assertEqual(self.origin_master(), before)

    def test_staged_deletion_and_dirty_built_page_print_the_fix_and_start_no_merge(self):
        built_page = "docs/changes/changelog.md"
        (self.main / "docs" / "changes").mkdir(parents=True)
        self.write(self.main, built_page, "built\n")
        self.git(self.main, "add", "-A")
        self.git(self.main, "commit", "-qm", "built page")
        self.git(self.main, "push", "-q", "origin", "HEAD:master")
        self.git(self.lane, "merge", "-q", "--no-edit", "master")
        self.write(self.lane, built_page, "built by the lane\n")
        (self.lane / "other.txt").unlink()
        self.git(self.lane, "add", "-A")
        self.git(self.lane, "commit", "-qm", "lane edits")
        # Origin is one commit ahead of the lane, so a merge would start if the preflight let the run through.
        self.push_from_elsewhere("elsewhere.txt", "e\n")
        self.git(self.main, "rm", "-q", "other.txt")
        self.write(self.main, built_page, "dirty built page\n")
        lane_head = self.git(self.lane, "rev-parse", "HEAD")
        before = self.origin_master()
        finished = self.land()
        self.assertEqual(finished.returncode, 1, finished.stdout + finished.stderr)
        self.assertIn("other.txt", finished.stdout)
        self.assertIn(built_page, finished.stdout)
        self.assertIn("commit them or set them aside", finished.stdout + finished.stderr)
        self.assertEqual(self.git(self.lane, "rev-parse", "HEAD"), lane_head)
        # A lane is a worktree, so its MERGE_HEAD lives at the path git names, not under a .git folder.
        merge_head_path = self.git(self.lane, "rev-parse", "--path-format=absolute", "--git-path", "MERGE_HEAD")
        self.assertFalse(pathlib.Path(merge_head_path).exists())
        self.assertFalse(self.marker.exists())
        self.assertEqual(self.origin_master(), before)

    def test_origin_ahead_on_a_file_main_holds_dirty_stops_before_any_push(self):
        self.lane_commit("lane.txt", "lane\n")
        self.push_from_elsewhere("other.txt", "elsewhere\n")
        # The lane never touches other.txt, but the pull into main brings in origin's change to it.
        self.write(self.main, "other.txt", "dirty\n")
        before = self.origin_master()
        finished = self.land()
        self.assertEqual(finished.returncode, 1, finished.stdout + finished.stderr)
        self.assertIn("other.txt", finished.stdout)
        self.assertFalse(self.marker.exists())
        self.assertEqual(self.origin_master(), before)

    def test_main_switching_branch_during_the_suite_stops_before_the_push(self):
        self.lane_commit("lane.txt", "lane\n")
        before = self.origin_master()
        finished = self.land(suite=f"git -C {self.main} checkout -q -b side")
        self.assertEqual(finished.returncode, 1, finished.stdout + finished.stderr)
        self.assertIn("side", finished.stdout)
        self.assertEqual(self.origin_master(), before)

    def test_unrelated_dirty_file_in_main_does_not_stop(self):
        self.lane_commit("lane.txt", "lane\n")
        self.write(self.main, "unrelated.txt", "x\n")
        finished = self.land()
        self.assertEqual(finished.returncode, 0, finished.stdout + finished.stderr)
        self.assertEqual(self.origin_master(), self.git(self.lane, "rev-parse", "HEAD"))

    def test_merge_conflict_aborts_and_names_the_file(self):
        self.write(self.lane, "shared.txt", "lane\n")
        self.git(self.lane, "commit", "-qam", "lane edit")
        self.push_from_elsewhere("shared.txt", "elsewhere\n")
        before = self.origin_master()
        lane_head = self.git(self.lane, "rev-parse", "HEAD")
        finished = self.land()
        self.assertEqual(finished.returncode, 1)
        self.assertIn("shared.txt", finished.stdout)
        self.assertIn("merge aborted", finished.stdout)
        self.assertIn("rerun: ", finished.stdout)
        self.assertEqual(self.git(self.lane, "rev-parse", "HEAD"), lane_head)
        merge_head_path = self.git(self.lane, "rev-parse", "--path-format=absolute", "--git-path", "MERGE_HEAD")
        self.assertFalse(pathlib.Path(merge_head_path).exists())
        self.assertEqual(self.origin_master(), before)

    def test_failing_suite_stops_before_the_push(self):
        self.lane_commit("lane.txt", "lane\n")
        self.push_from_elsewhere("elsewhere.txt", "e\n")
        before = self.origin_master()
        finished = self.land(suite="echo suite-broke; exit 3")
        self.assertEqual(finished.returncode, 1)
        self.assertIn("suite-broke", finished.stdout)
        self.assertIn("nothing was pushed", finished.stdout)
        self.assertEqual(self.origin_master(), before)

    def test_staged_rename_in_main_of_a_lane_file_stops(self):
        self.write(self.lane, "shared.txt", "lane\n")
        self.git(self.lane, "commit", "-qam", "lane edit")
        self.git(self.main, "mv", "shared.txt", "moved.txt")
        finished = self.land()
        self.assertEqual(finished.returncode, 1)
        self.assertIn("shared.txt", finished.stdout)

    def test_lane_rename_old_name_dirty_in_main_stops_and_names_both(self):
        self.git(self.lane, "mv", "shared.txt", "moved.txt")
        self.git(self.lane, "commit", "-qm", "lane rename")
        self.write(self.main, "shared.txt", "dirty\n")
        finished = self.land()
        self.assertEqual(finished.returncode, 1)
        self.assertIn("shared.txt", finished.stdout)

    def test_file_names_with_spaces_are_matched_whole(self):
        self.write(self.lane, "a b.txt", "lane\n")
        self.git(self.lane, "add", "a b.txt")
        self.git(self.lane, "commit", "-qm", "spaced")
        self.write(self.main, "a b.txt", "dirty\n")
        finished = self.land()
        self.assertEqual(finished.returncode, 1)
        self.assertIn("a b.txt", finished.stdout)

    def test_merge_failing_without_a_conflict_is_reported_as_itself(self):
        self.lane_commit("lane.txt", "lane\n")
        self.push_from_elsewhere("elsewhere.txt", "e\n")
        # An empty committer name makes the merge commit fail with no conflicted path.
        finished = self.land(extra_env={"GIT_COMMITTER_NAME": ""})
        self.assertEqual(finished.returncode, 1)
        self.assertIn("without a conflict", finished.stdout)
        self.assertNotIn("merge aborted", finished.stdout)
        self.assertIn("rerun: ", finished.stdout)

    def test_dirty_lane_stops_before_anything_else(self):
        self.lane_commit("lane.txt", "lane\n")
        self.write(self.lane, "shared.txt", "uncommitted\n")
        before = self.origin_master()
        finished = self.land()
        self.assertEqual(finished.returncode, 1)
        self.assertIn("uncommitted changes", finished.stdout)
        self.assertEqual(self.origin_master(), before)

    def test_untracked_file_in_the_lane_stops_before_anything_else(self):
        self.lane_commit("lane.txt", "lane\n")
        self.write(self.lane, "forgotten.py", "x = 1\n")
        before = self.origin_master()
        finished = self.land()
        self.assertEqual(finished.returncode, 1)
        self.assertIn("uncommitted changes", finished.stdout)
        self.assertFalse(self.marker.exists())
        self.assertEqual(self.origin_master(), before)

    def test_git_failure_stops_with_inspect_hint_and_no_traceback(self):
        self.lane_commit("lane.txt", "lane\n")
        finished = self.land(extra_arguments=("--remote", "nosuchremote"))
        self.assertEqual(finished.returncode, 1)
        self.assertIn("inspect with", finished.stdout)
        self.assertIn("rerun: ", finished.stdout)
        self.assertNotIn("Traceback", finished.stderr)

    def test_rejected_push_retries_and_lands_both_commits(self):
        self.lane_commit("lane.txt", "lane\n")
        self.push_from_elsewhere("first.txt", "1\n")
        # The suite moves origin once, after the fetch, so the first push is rejected.
        mover = self.tmp / "mover.sh"
        flag = self.tmp / "moved"
        other = self.tmp / "mover-clone"
        mover.write_text(
            f"[ -e {flag} ] && exit 0\ntouch {flag}\n"
            f"git clone -q {self.remote} {other} && cd {other} && echo x > moved.txt && git add moved.txt && "
            "git commit -qm moved && git push -q origin HEAD:master\n")
        finished = self.land(suite=f"bash {mover}")
        self.assertEqual(finished.returncode, 0, finished.stdout + finished.stderr)
        self.assertEqual(self.origin_master(), self.git(self.lane, "rev-parse", "HEAD"))
        files = self.git(self.remote, "ls-tree", "--name-only", "master").split()
        self.assertIn("moved.txt", files)
        self.assertIn("lane.txt", files)

    def test_push_rejected_every_attempt_stops(self):
        self.lane_commit("lane.txt", "lane\n")
        self.push_from_elsewhere("first.txt", "1\n")
        hook = self.remote / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\necho '! [remote rejected] non-fast-forward' >&2\nexit 1\n")
        hook.chmod(0o755)
        before = self.origin_master()
        finished = self.land()
        self.assertEqual(finished.returncode, 1)
        self.assertIn("rerun: ", finished.stdout)
        self.assertIn("moved during all 3 attempts", finished.stdout)
        self.assertEqual(self.origin_master(), before)

    def test_push_failing_for_another_reason_stops_at_once(self):
        self.lane_commit("lane.txt", "lane\n")
        hook = self.remote / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\necho 'denied by policy' >&2\nexit 1\n")
        hook.chmod(0o755)
        before = self.origin_master()
        finished = self.land()
        self.assertEqual(finished.returncode, 1)
        self.assertIn("the push of", finished.stdout)
        self.assertIn("rerun: ", finished.stdout)
        self.assertNotIn("moved during all", finished.stdout)
        self.assertEqual(self.origin_master(), before)

    def test_suite_log_is_removed_when_green_and_kept_when_failing(self):
        log_folder = self.tmp / "suite-logs"
        log_folder.mkdir()
        self.lane_commit("lane.txt", "lane\n")
        passed = self.land(extra_env={"TMPDIR": str(log_folder)})
        self.assertEqual(passed.returncode, 0, passed.stdout + passed.stderr)
        self.assertEqual(list(log_folder.glob("land-lane-suite-*.log")), [])
        self.git(self.lane, "reset", "-q", "--hard", "HEAD~1")
        self.lane_commit("second.txt", "2\n")
        failed = self.land(suite="exit 3", extra_env={"TMPDIR": str(log_folder)})
        self.assertEqual(failed.returncode, 1)
        self.assertEqual(len(list(log_folder.glob("land-lane-suite-*.log"))), 1)

    def test_unreadable_suite_receipt_stops_before_the_push(self):
        self.lane_commit("lane.txt", "lane\n")
        common_dir = self.git(self.lane, "rev-parse", "--path-format=absolute", "--git-common-dir")
        (pathlib.Path(common_dir) / suite_receipt.RECEIPTS_FILE).write_text("not json\n")
        before = self.origin_master()
        finished = self.land()
        self.assertEqual(finished.returncode, 1)
        self.assertIn("is not a JSON receipt row", finished.stdout)
        self.assertIn("; repair or remove that row", finished.stdout)
        self.assertNotIn("inspect with", finished.stdout)
        self.assertIn("rerun: ", finished.stdout)
        self.assertNotIn("Traceback", finished.stderr)
        self.assertFalse(self.marker.exists())
        self.assertEqual(self.origin_master(), before)

    def test_receipt_row_that_is_not_a_complete_object_stops_before_the_push(self):
        self.lane_commit("lane.txt", "lane\n")
        common_dir = self.git(self.lane, "rev-parse", "--path-format=absolute", "--git-common-dir")
        receipts_file = pathlib.Path(common_dir) / suite_receipt.RECEIPTS_FILE
        before = self.origin_master()
        for row_text in ("[]", '{"tree": "abc"}'):
            with self.subTest(row=row_text):
                receipts_file.write_text(row_text + "\n")
                finished = self.land()
                self.assertEqual(finished.returncode, 1, finished.stdout + finished.stderr)
                self.assertIn("; repair or remove that row", finished.stdout)
                self.assertNotIn("Traceback", finished.stderr)
                self.assertFalse(self.marker.exists())
                self.assertEqual(self.origin_master(), before)

    def test_main_that_is_not_a_repository_stops_as_a_git_step_not_a_detached_head(self):
        self.lane_commit("lane.txt", "lane\n")
        not_a_repo = self.tmp / "plain-folder"
        not_a_repo.mkdir()
        finished = self.land(extra_arguments=("--main", str(not_a_repo)))
        self.assertEqual(finished.returncode, 1, finished.stdout + finished.stderr)
        self.assertNotIn("detached", finished.stdout)
        self.assertIn("inspect with", finished.stdout)
        self.assertNotIn("Traceback", finished.stderr)

    def test_main_changed_during_the_suite_stops_before_the_push(self):
        self.write(self.lane, "shared.txt", "lane\n")
        self.git(self.lane, "commit", "-qam", "lane edit")
        self.push_from_elsewhere("elsewhere.txt", "e\n")
        before = self.origin_master()
        finished = self.land(suite=f"echo x > {self.main}/shared.txt")
        self.assertEqual(finished.returncode, 1)
        self.assertIn("shared.txt", finished.stdout)
        self.assertEqual(self.origin_master(), before)

    def test_suite_that_commits_in_the_lane_stops_before_the_push(self):
        self.lane_commit("lane.txt", "lane\n")
        before = self.origin_master()
        finished = self.land(suite="git commit --allow-empty -qm untested")
        self.assertEqual(finished.returncode, 1, finished.stdout + finished.stderr)
        self.assertIn("moved during the suite", finished.stdout)
        self.assertIn("rerun: ", finished.stdout)
        self.assertEqual(self.origin_master(), before)

    def test_suite_that_dirties_the_lane_stops_before_the_push(self):
        self.lane_commit("lane.txt", "lane\n")
        before = self.origin_master()
        finished = self.land(suite="echo x > untested.txt")
        self.assertEqual(finished.returncode, 1, finished.stdout + finished.stderr)
        self.assertIn("uncommitted changes", finished.stdout)
        self.assertEqual(self.origin_master(), before)

    def test_main_on_another_branch_stops_before_any_merge_or_push(self):
        self.lane_commit("lane.txt", "lane\n")
        self.push_from_elsewhere("elsewhere.txt", "e\n")
        before = self.origin_master()
        lane_head = self.git(self.lane, "rev-parse", "HEAD")
        self.git(self.main, "checkout", "-q", "-b", "side")
        finished = self.land()
        self.assertEqual(finished.returncode, 1, finished.stdout + finished.stderr)
        self.assertIn("side", finished.stdout)
        self.assertIn("master", finished.stdout)
        self.assertEqual(self.git(self.lane, "rev-parse", "HEAD"), lane_head)
        self.assertFalse(self.marker.exists())
        self.assertEqual(self.origin_master(), before)

    def test_main_with_a_detached_head_stops(self):
        self.lane_commit("lane.txt", "lane\n")
        before = self.origin_master()
        self.git(self.main, "checkout", "-q", "--detach")
        finished = self.land()
        self.assertEqual(finished.returncode, 1, finished.stdout + finished.stderr)
        self.assertIn("detached", finished.stdout)
        self.assertEqual(self.origin_master(), before)

    def test_rerun_line_uses_resolved_paths_and_the_given_options(self):
        self.lane_commit("lane.txt", "lane\n")
        self.write_suite("exit 3")
        finished = subprocess.run([sys.executable, str(LAND_LANE_SCRIPT), "lane", "--main", "main", "--remote",
                                   "origin"], capture_output=True, text=True, cwd=self.tmp)
        self.assertEqual(finished.returncode, 1, finished.stdout + finished.stderr)
        rerun_line = next(line for line in finished.stdout.splitlines() if line.startswith("rerun: "))
        self.assertIn(str(self.lane), rerun_line)
        self.assertIn(str(self.main), rerun_line)
        self.assertIn("--base master", rerun_line)
        self.assertIn("--remote origin", rerun_line)

    def test_git_failure_reading_the_receipt_is_a_git_step_not_a_row_repair(self):
        failure = suite_receipt.ReceiptError("git rev-parse failed in lane: boom")
        patched_check = unittest.mock.patch.object(land_lane.suite_receipt, "check", side_effect=failure)
        with patched_check, self.assertRaises(land_lane.GitStepError) as raised:
            land_lane.receipt_covers_tree("lane", "origin/master")
        self.assertNotIn("repair or remove", str(raised.exception))

    def record_green_receipt(self):
        """A green suite receipt for the lane's work tree, written through suite_receipt.py record."""
        tree = subprocess.run([sys.executable, str(SUITE_RECEIPT_SCRIPT), "tree", str(self.lane)],
                              capture_output=True, text=True, check=True).stdout.strip()
        summary = self.tmp / "summary.json"
        summary.write_text(json.dumps({"tests": 5, "failed_files": []}))
        subprocess.run([sys.executable, str(SUITE_RECEIPT_SCRIPT), "record", str(self.lane), "--tree", tree,
                        "--exit", "0", "--scope", "full", "--summary", str(summary)], check=True)

    def test_lane_already_up_to_date_with_no_proof_runs_the_suite(self):
        self.lane_commit("lane.txt", "lane\n")
        finished = self.land()
        self.assertEqual(finished.returncode, 0, finished.stdout + finished.stderr)
        self.assertTrue(self.marker.exists())
        self.assertIn("no merge, suite ran", finished.stdout)
        self.assertEqual(self.origin_master(), self.git(self.lane, "rev-parse", "HEAD"))

    def test_green_receipt_skips_the_suite_with_no_merge(self):
        self.lane_commit("lane.txt", "lane\n")
        self.record_green_receipt()
        finished = self.land()
        self.assertEqual(finished.returncode, 0, finished.stdout + finished.stderr)
        self.assertFalse(self.marker.exists())
        self.assertIn("suite skipped on receipt", finished.stdout)

    def test_green_receipt_for_the_merged_tree_skips_the_suite(self):
        self.lane_commit("lane.txt", "lane\n")
        self.push_from_elsewhere("elsewhere.txt", "e\n")
        self.git(self.lane, "fetch", "-q", "origin")
        self.git(self.lane, "merge", "-q", "--no-edit", "origin/master")
        self.record_green_receipt()
        # The lane already holds the merge, so the receipt on its tree is the proof.
        finished = self.land()
        self.assertEqual(finished.returncode, 0, finished.stdout + finished.stderr)
        self.assertFalse(self.marker.exists())
        self.assertIn("suite skipped on receipt", finished.stdout)

    def test_exit_code_comes_from_the_pull_into_main(self):
        self.lane_commit("lane.txt", "lane\n")
        self.push_from_elsewhere("other.txt", "elsewhere\n")
        # main holds a local commit on other.txt, not a dirty edit, so the preflight passes but the pull conflicts.
        self.write(self.main, "other.txt", "dirty\n")
        self.git(self.main, "commit", "-qam", "local other")
        finished = self.land()
        self.assertEqual(self.origin_master(), self.git(self.lane, "rev-parse", "HEAD"))
        output = finished.stdout + finished.stderr
        self.assertNotEqual(finished.returncode, 0, output)
        self.assertIn("other.txt", output)
        # The pull puts main's edit back as a conflict, so the edit survives next to the incoming text.
        main_text = (self.main / "other.txt").read_text()
        self.assertIn("dirty", main_text)
        self.assertIn("elsewhere", main_text)

    def test_help_exits_zero_and_bad_arguments_exit_two(self):
        helped = subprocess.run([sys.executable, str(LAND_LANE_SCRIPT), "--help"], capture_output=True, text=True)
        self.assertEqual(helped.returncode, 0)
        self.assertIn("Usage:", helped.stdout)
        bad = subprocess.run([sys.executable, str(LAND_LANE_SCRIPT), "--bogus"], capture_output=True, text=True)
        self.assertEqual(bad.returncode, 2)


if __name__ == "__main__":
    unittest.main()
