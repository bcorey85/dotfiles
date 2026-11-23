"""Tests for phase_start.py, the record of the tree a /code phase starts from, and the held files code_review_start.py
reads from it. Set PHASE_START_SCRIPT to run against another copy."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths

PHASE_START = pathlib.Path(os.environ.get("PHASE_START_SCRIPT") or toolkit_paths.CODE_DIR / "phase_start.py")
REVIEW_START = PHASE_START.parent / "code_review_start.py"
ENV = {**os.environ, "CLAUDE_CODE_SESSION_ID": "test-session"}


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
                          capture_output=True, text=True, check=True).stdout.strip()


class PhaseStartTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        scratch = pathlib.Path(folder.name).resolve()
        self.repo = scratch / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        for name in ("mine.py", "theirs.py", "shared.py"):
            (self.repo / name).write_text(f"# {name}\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-q", "-m", "base")
        self.home = scratch / "home"
        self.home.mkdir()
        self.config_dir = scratch / "config"
        (self.config_dir / "sessions").mkdir(parents=True)
        self.handoff = scratch / "handoff.txt"
        self.handoff.write_text("  files:\n    - path: mine.py\n      why: the phase change\n")

    def phase_start(self):
        return self.phase_start_with()

    def phase_start_with(self, *flags):
        return subprocess.run([sys.executable, str(PHASE_START), *flags], cwd=self.repo, capture_output=True,
                              text=True, check=False, env={**ENV, "HOME": str(self.home)})

    def recorded_dirty(self):
        return sorted(json.loads((self.repo / ".git/code-phase/start.json").read_text())["dirty"])

    def test_a_review_start_that_exits_early_leaves_no_earlier_phase_packet_for_the_wait(self):
        phase_dir = self.repo / ".git/code-phase"
        phase_dir.mkdir()
        earlier_loop = self.repo.parent / "earlier-loop"
        earlier_loop.mkdir()
        (earlier_loop / "packet.txt").write_text("status: converged\n")
        (phase_dir / "loop-dir").write_text(f"{earlier_loop}\n")
        (phase_dir / "review.out").write_text("status: converged\n")
        (phase_dir / "run.json").write_text(json.dumps({"lane": "lane-a", "phase": "1", "loop_dir": str(earlier_loop)}))
        self.phase_start()
        env = {**ENV, "CLAUDE_CONFIG_DIR": str(self.config_dir)}
        refused = subprocess.run([sys.executable, str(REVIEW_START), "lane-a", "-", "2", str(self.handoff), "--base",
                                  "no-such-ref", "--detach"], cwd=self.repo, capture_output=True, text=True,
                                 check=False, env=env)

        waited = subprocess.run([sys.executable, str(REVIEW_START.parent / "code_wait.py"), "review"], cwd=self.repo,
                                capture_output=True, text=True, check=False, env=env)

        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("no-such-ref", refused.stderr)
        self.assertFalse((phase_dir / "loop-dir").exists())
        self.assertEqual((phase_dir / "loop-dir.prev").read_text().strip(), str(earlier_loop))
        self.assertEqual(waited.returncode, 1)
        self.assertIn("Run this phase's `code_review_start.py ... --detach` line again", waited.stdout)
        self.assertNotIn("status: converged", waited.stdout)

    def test_a_second_phase_start_at_the_same_head_keeps_the_first_record(self):
        (self.repo / "theirs.py").write_text("# another session's edit\n")
        self.phase_start()
        (self.repo / "mine.py").write_text("# the first phase's file\n")
        (self.repo / ".git/code-phase/handoff.txt").write_text(self.handoff.read_text())

        done = self.phase_start()

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.strip(), git(self.repo, "rev-parse", "HEAD"))
        self.assertEqual(self.recorded_dirty(), ["theirs.py"])

    def test_a_holder_first_dirty_at_a_later_phase_start_is_held_and_the_phases_own_file_is_not(self):
        self.phase_start()
        (self.repo / "mine.py").write_text("# the first phase's file\n")
        (self.repo / "theirs.py").write_text("# an edit another session made during phase one\n")
        (self.repo / ".git/code-phase/handoff.txt").write_text(self.handoff.read_text())

        done = self.phase_start()

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.recorded_dirty(), ["theirs.py"])
        (self.repo / "shared.py").write_text("# the second phase's coder\n")
        self.register_live_session("other-session", self.repo)
        review = self.review_prompt(done.stdout.strip())
        header = review.stdout.partition("\n\n")[0]
        self.assertIn("held files: theirs.py", header.splitlines())

    def test_new_run_replaces_the_record(self):
        (self.repo / "theirs.py").write_text("# another session's edit\n")
        self.phase_start()
        (self.repo / "mine.py").write_text("# a file dirty at the new run's start\n")

        done = self.phase_start_with("--new-run")

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.recorded_dirty(), ["mine.py", "theirs.py"])

    def test_a_moved_head_replaces_the_record(self):
        (self.repo / "theirs.py").write_text("# another session's edit\n")
        self.phase_start()
        git(self.repo, "commit", "-q", "-am", "next")
        (self.repo / "mine.py").write_text("# dirty after the commit\n")

        done = self.phase_start()

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.recorded_dirty(), ["mine.py"])

    def test_a_record_that_does_not_parse_is_replaced_with_a_note_naming_the_file(self):
        self.phase_start()
        record_file = self.repo / ".git/code-phase/start.json"
        record_file.write_text("{}")
        (self.repo / "theirs.py").write_text("# another session's edit\n")

        done = self.phase_start()

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn(str(record_file), done.stderr)
        self.assertEqual(self.recorded_dirty(), ["theirs.py"])

    def test_an_unknown_argument_stops_before_any_record_is_written(self):
        done = self.phase_start_with("--new_run")

        self.assertNotEqual(done.returncode, 0)
        self.assertIn("usage: phase_start.py [--new-run | --resume]", done.stderr)
        self.assertFalse((self.repo / ".git/code-phase/start.json").exists())

    def test_a_stale_stop_file_is_renamed_to_stop_prev_replacing_an_older_one(self):
        run_folder = self.repo / ".git/code-phase"
        run_folder.mkdir()
        (run_folder / "stop.md").write_text("the stale stop\n")
        (run_folder / "stop.prev.md").write_text("an older stop\n")
        (run_folder / "review-stop.md").write_text("a review stop\n")

        done = self.phase_start()

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertFalse((run_folder / "stop.md").exists())
        self.assertEqual((run_folder / "stop.prev.md").read_text(), "the stale stop\n")
        self.assertEqual((run_folder / "review-stop.md").read_text(), "a review stop\n")

    def test_the_last_handoff_is_moved_to_handoff_prev_replacing_an_older_one(self):
        run_folder = self.repo / ".git/code-phase"
        run_folder.mkdir()
        (run_folder / "handoff.txt").write_text("the last phase's hand-off\n")
        (run_folder / "handoff.prev.txt").write_text("an older hand-off\n")

        done = self.phase_start()

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertFalse((run_folder / "handoff.txt").exists())
        self.assertEqual((run_folder / "handoff.prev.txt").read_text(), "the last phase's hand-off\n")

    def test_a_first_phase_with_no_handoff_creates_no_handoff_prev(self):
        run_folder = self.repo / ".git/code-phase"
        run_folder.mkdir()

        done = self.phase_start()

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertFalse((run_folder / "handoff.prev.txt").exists())

    def test_a_failed_handoff_rename_names_phase_start_on_stderr_and_the_script_goes_on(self):
        run_folder = self.repo / ".git/code-phase"
        run_folder.mkdir()
        (run_folder / "handoff.txt").write_text("the last hand-off\n")
        (run_folder / "handoff.prev.txt").mkdir()

        done = self.phase_start()

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("phase_start: could not move", done.stderr)
        self.assertEqual(done.stdout.strip(), git(self.repo, "rev-parse", "HEAD"))

    def test_a_failed_stop_rename_names_phase_start_on_stderr_and_the_script_goes_on(self):
        run_folder = self.repo / ".git/code-phase"
        run_folder.mkdir()
        (run_folder / "stop.md").write_text("the stale stop\n")
        (run_folder / "stop.prev.md").mkdir()

        done = self.phase_start()

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("phase_start: could not move", done.stderr)
        self.assertEqual(done.stdout.strip(), git(self.repo, "rev-parse", "HEAD"))

    def review_prompt(self, base):
        return subprocess.run([sys.executable, str(REVIEW_START), "lane-a", "-", "1", str(self.handoff), "--base", base,
                               "--dry-run"], cwd=self.repo, capture_output=True, text=True, check=False,
                              env={**ENV, "CLAUDE_CONFIG_DIR": str(self.config_dir)})

    def register_live_session(self, session_id, cwd):
        """A live registry row (this test process's pid) for a session working in `cwd`."""
        row = {"pid": os.getpid(), "sessionId": session_id, "name": "lane-b", "cwd": str(cwd)}
        (self.config_dir / "sessions" / f"{session_id}.json").write_text(json.dumps(row))

    def test_the_record_names_head_and_every_dirty_file_and_the_sha_is_printed(self):
        (self.repo / "theirs.py").write_text("# another session's edit\n")
        (self.repo / "new.txt").write_text("untracked\n")

        done = self.phase_start()

        self.assertEqual(done.returncode, 0, done.stderr)
        head = git(self.repo, "rev-parse", "HEAD")
        self.assertEqual(done.stdout.strip(), head)
        record = json.loads((self.repo / ".git/code-phase/start.json").read_text())
        self.assertEqual(record["head"], head)
        self.assertEqual(sorted(record["dirty"]), ["new.txt", "theirs.py"])

    def test_a_file_dirty_at_the_phase_start_with_the_same_bytes_is_held_out_of_the_review(self):
        (self.repo / "theirs.py").write_text("# another session's edit\n")
        (self.repo / "shared.py").write_text("# another session's edit\n")
        base = self.phase_start().stdout.strip()
        (self.repo / "mine.py").write_text("# the phase's coder\n")
        (self.repo / "shared.py").write_text("# the phase's coder edited it too\n")
        self.register_live_session("other-session", self.repo)

        done = self.review_prompt(base)

        self.assertEqual(done.returncode, 0, done.stderr)
        header, _, handoff = done.stdout.partition("\n\n")
        self.assertIn("held files: theirs.py", header.splitlines())
        holders = json.loads(next(line for line in header.splitlines() if line.startswith("held-by: "))[9:])
        self.assertEqual(holders, [{"path": "theirs.py", "session": "lane-b",
                                    "claim": f"dirty at the run start, unchanged now; live session in {self.repo}"}])
        self.assertIn("- path: mine.py", handoff)
        self.assertIn("- path: shared.py", handoff)
        self.assertNotIn("theirs.py", handoff)

    def test_a_dirty_file_with_no_other_live_session_in_the_repo_is_the_runs_own_and_is_reviewed(self):
        (self.repo / "theirs.py").write_text("# an edit nobody else holds\n")
        base = self.phase_start().stdout.strip()
        self.register_live_session("test-session", self.repo)
        self.register_live_session("elsewhere-session", self.repo.parent)

        done = self.review_prompt(base)

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn("held files:", done.stdout)
        self.assertNotIn("held-by:", done.stdout)

    def unrelated_commit(self):
        """A commit on an orphan branch: neither an ancestor nor a descendant of the recorded head."""
        git(self.repo, "checkout", "-q", "--orphan", "other")
        (self.repo / "other.py").write_text("# unrelated\n")
        git(self.repo, "add", "other.py")
        git(self.repo, "commit", "-q", "-m", "unrelated")
        return git(self.repo, "rev-parse", "HEAD")

    def test_a_base_unrelated_to_the_recorded_head_stops_the_review_start_naming_the_flag(self):
        recorded = self.phase_start().stdout.strip()
        unrelated = self.unrelated_commit()

        done = self.review_prompt(unrelated)

        self.assertNotEqual(done.returncode, 0)
        self.assertIn(f"--base {recorded}", done.stderr)
        self.assertIn("ancestor", done.stderr)

    def test_a_base_that_is_an_ancestor_of_the_recorded_head_is_accepted(self):
        merge_base = git(self.repo, "rev-parse", "HEAD")
        git(self.repo, "commit", "-q", "--allow-empty", "-m", "phase one")
        self.phase_start()

        done = self.review_prompt(merge_base)

        self.assertEqual(done.returncode, 0, done.stderr)

    def test_a_resume_base_the_recorded_head_is_an_ancestor_of_is_accepted(self):
        recorded = self.phase_start().stdout.strip()
        git(self.repo, "commit", "-q", "--allow-empty", "-m", "the phase, committed by the user")

        done = self.review_prompt(git(self.repo, "rev-parse", "HEAD"))

        self.assertEqual(recorded, git(self.repo, "rev-parse", "HEAD~"))
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_a_descendant_base_that_is_not_head_is_refused(self):
        self.phase_start()
        git(self.repo, "commit", "-q", "--allow-empty", "-m", "first commit after the start")
        descendant = git(self.repo, "rev-parse", "HEAD")
        git(self.repo, "commit", "-q", "--allow-empty", "-m", "second commit after the start")

        done = self.review_prompt(descendant)

        self.assertNotEqual(done.returncode, 0)
        self.assertIn("phase_start.py did not run", done.stderr)

    def test_resume_after_the_phase_was_committed_prints_the_head_the_run_started_from(self):
        started_from = self.phase_start().stdout.strip()
        (self.repo / "mine.py").write_text("# the phase's change\n")
        git(self.repo, "commit", "-q", "-am", "the phase, committed by the user")

        done = self.phase_start_with("--resume")

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.strip(), started_from)
        self.assertEqual(json.loads((self.repo / ".git/code-phase/start.json").read_text())["head"], started_from)

    def other_repo_with_recorded_stop(self):
        """A second repo whose run folder holds this session's recorded stop; the home is a temp folder."""
        other = self.repo.parent / "other"
        other.mkdir()
        git(other, "init", "-q")
        (other / ".git/code-phase").mkdir()
        (other / ".git/code-phase/stop.md").write_text("Stopped.\n\nTo go on: /code resume <your feedback>\n")
        env = {**ENV, "HOME": str(self.home)}
        subprocess.run([sys.executable, str(PHASE_START.parent / "code_relay.py")], cwd=other, capture_output=True,
                       text=True, check=True, env=env)
        return other, env

    def resume_in_repo(self, env):
        return subprocess.run([sys.executable, str(PHASE_START), "--resume"], cwd=self.repo, capture_output=True,
                              text=True, check=False, env=env)

    def test_resume_in_a_repo_with_no_stop_while_the_session_stopped_in_another_names_both(self):
        other, env = self.other_repo_with_recorded_stop()

        done = self.resume_in_repo(env)

        self.assertNotEqual(done.returncode, 0)
        self.assertIn(str(self.repo / ".git/code-phase"), done.stderr)
        self.assertIn(str(other / ".git/code-phase"), done.stderr)
        self.assertIn(f"To go on: /code resume {other} <your feedback>", done.stderr)

    def test_a_finished_stop_in_another_run_folder_is_refused_with_the_bare_resume_line(self):
        other, env = self.other_repo_with_recorded_stop()
        (other / ".git/code-phase/stop.md").write_text("Run finished.")
        (other / ".git/code-phase/relayed").unlink()
        subprocess.run([sys.executable, str(PHASE_START.parent / "code_relay.py")], cwd=other, capture_output=True,
                       text=True, check=True, env=env)

        done = self.resume_in_repo(env)

        self.assertNotEqual(done.returncode, 0)
        self.assertIn(f"/code resume {other}", done.stderr)

    def test_a_refused_resume_leaves_the_run_folder_untouched(self):
        _, env = self.other_repo_with_recorded_stop()
        run_folder = self.repo / ".git/code-phase"
        run_folder.mkdir()
        (run_folder / "handoff.txt").write_text("a handoff\n")

        done = self.resume_in_repo(env)

        self.assertNotEqual(done.returncode, 0)
        self.assertFalse((run_folder / "start.json").exists())
        self.assertFalse((run_folder / "stop.prev.md").exists())
        self.assertTrue((run_folder / "handoff.txt").is_file())
        self.assertFalse((run_folder / "handoff.prev.txt").exists())

    def test_resume_in_a_repo_whose_own_newer_stop_was_moved_aside_goes_on(self):
        _, env = self.other_repo_with_recorded_stop()
        run_folder = self.repo / ".git/code-phase"
        run_folder.mkdir()
        (run_folder / "stop.prev.md").write_text("Stopped.\n\nTo go on: /code resume <your feedback>\n")

        done = self.resume_in_repo(env)

        self.assertEqual(done.returncode, 0, done.stderr)

    def test_resume_with_a_stop_prev_older_than_the_recorded_stop_is_refused(self):
        _, env = self.other_repo_with_recorded_stop()
        run_folder = self.repo / ".git/code-phase"
        run_folder.mkdir()
        old_stop = run_folder / "stop.prev.md"
        old_stop.write_text("Stopped.\n\nTo go on: /code resume <your feedback>\n")
        os.utime(old_stop, (1.0, 1.0))

        done = self.resume_in_repo(env)

        self.assertNotEqual(done.returncode, 0)
        self.assertIn("this session's last stop is in", done.stderr)

    def test_resume_with_the_recorded_stop_in_this_run_folder_and_no_stop_files_goes_on(self):
        run_folder = self.repo / ".git/code-phase"
        run_folder.mkdir()
        spellings = {"plain": run_folder, "symlinked": self.repo.parent / "link"}
        spellings["symlinked"].symlink_to(self.repo, target_is_directory=True)
        spellings["symlinked"] = spellings["symlinked"] / ".git/code-phase"
        for name, recorded_folder in spellings.items():
            with self.subTest(name):
                record_dir = self.home / ".claude/code-stop-sessions"
                record_dir.mkdir(parents=True, exist_ok=True)
                (record_dir / "test-session.json").write_text(json.dumps(
                    {"runFolder": str(recorded_folder), "repoTop": str(self.repo), "goOn": "", "time": 1.0}))

                done = self.resume_in_repo({**ENV, "HOME": str(self.home)})

                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertNotIn("code_stop_record: ignoring", done.stderr)

    def test_resume_in_a_repo_with_its_own_stop_goes_on_whatever_the_session_recorded(self):
        _, env = self.other_repo_with_recorded_stop()
        run_folder = self.repo / ".git/code-phase"
        run_folder.mkdir()
        (run_folder / "stop.md").write_text("Stopped.\n\nTo go on: /code resume <your feedback>\n")

        done = self.resume_in_repo(env)

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue((run_folder / "stop.prev.md").is_file())

    def test_resume_with_no_session_id_or_no_record_goes_on(self):
        _, env = self.other_repo_with_recorded_stop()
        no_session = {key: value for key, value in env.items() if key != "CLAUDE_CODE_SESSION_ID"}
        no_record = {**env, "CLAUDE_CODE_SESSION_ID": "never-relayed"}
        for name, case_env in {"no session id": no_session, "no record": no_record}.items():
            with self.subTest(name):
                done = self.resume_in_repo(case_env)

                self.assertEqual(done.returncode, 0, done.stderr)

    def test_resume_with_no_record_prints_head_and_says_so(self):
        done = self.phase_start_with("--resume")

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.strip(), git(self.repo, "rev-parse", "HEAD"))
        self.assertIn("no start record", done.stderr)

    def test_resume_with_a_record_head_that_is_not_an_ancestor_prints_head_and_says_so(self):
        self.phase_start()
        self.unrelated_commit()

        done = self.phase_start_with("--resume")

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.strip(), git(self.repo, "rev-parse", "HEAD"))
        self.assertIn("not an ancestor of HEAD", done.stderr)

    def test_no_record_holds_no_file_and_says_so(self):
        (self.repo / "theirs.py").write_text("# another session's edit\n")

        done = self.review_prompt("HEAD")

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn("held files:", done.stdout)
        self.assertIn("no phase start record", done.stderr)


if __name__ == "__main__":
    unittest.main()
