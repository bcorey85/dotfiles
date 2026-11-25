"""Runs herdr-lane-sweep against real git repos with a bare origin, the real lanes.py and a stub herdr-lane-resume.

The stub sits beside a copy of the script, so the script finds it in its own folder. It records each lane it is asked
to close.
"""
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

import toolkit_paths
from stubs import copy_script_lib_modules, copy_toolkit_tools_lib, write_stub

BIN_DIR = pathlib.Path(__file__).resolve().parents[2] / "scripts" / ".local" / "bin"
HERDR_LANE_SWEEP = pathlib.Path(os.environ.get("HERDR_LANE_SWEEP", BIN_DIR / "herdr-lane-sweep"))
LANES_CLI = pathlib.Path(os.environ.get("HERDR_LANES_CLI", toolkit_paths.TOOLS_DIR / "lanes.py"))

# The stub fails for the lane named in FAILING_LANE, as the real command does for a working agent.
CLOSE_STUB = """echo "$*" >> "$EVENTS"
if [ "$2" = "$FAILING_LANE" ]; then echo "claude agent in $2 is working" >&2; exit 1; fi
exit 0"""


def git(folder, *args):
    command = ["git", "-C", str(folder), "-c", "user.name=t", "-c", "user.email=t@t", *args]
    finished = subprocess.run(command, capture_output=True, text=True)
    if finished.returncode != 0:
        raise AssertionError(f"{command} failed: {finished.stderr}")
    return finished.stdout.strip()


class HerdrLaneSweepTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = pathlib.Path(os.path.realpath(scratch.name))

        self.origin = self.root / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "master", str(self.origin)], check=True)
        self.main_checkout = self.root / "repo"
        self.main_checkout.mkdir()
        git(self.main_checkout, "init", "-q", "-b", "master")
        git(self.main_checkout, "commit", "-q", "--allow-empty", "-m", "base")
        git(self.main_checkout, "remote", "add", "origin", str(self.origin))
        git(self.main_checkout, "push", "-q", "-u", "origin", "master")
        git(self.main_checkout, "remote", "set-head", "origin", "master")

        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        self.script = self.bin_dir / "herdr-lane-sweep"
        shutil.copy(HERDR_LANE_SWEEP, self.script)
        self.script.chmod(0o755)
        copy_toolkit_tools_lib(self.root)
        copy_script_lib_modules(self.root, "lane_list.py", "first_output_line.py", "quiet_git.py")
        write_stub(self.bin_dir / "herdr-lane-resume", CLOSE_STUB)

        self.events = self.root / "events"
        self.state_home = self.root / "state"

    def env(self, failing_lane=""):
        env = dict(os.environ)
        env.update({
            "HOME": str(self.root),
            "XDG_STATE_HOME": str(self.state_home),
            "HERDR_LANES_CLI": str(LANES_CLI),
            "EVENTS": str(self.events),
            "FAILING_LANE": failing_lane,
        })
        return env

    def add_lane(self, name, start_ref="master", record_base=True):
        """A lane on a new branch `<name>` in a worktree beside the main checkout; its entry records `start_ref`'s
        commit as the base commit unless `record_base` is False."""
        worktree = self.root / name
        git(self.main_checkout, "worktree", "add", "-q", "-b", name, str(worktree), start_ref)
        command = ["python3", str(LANES_CLI), "add", "--name", name, "--worktree", str(worktree),
                   "--main-checkout", str(self.main_checkout), "--branch", name]
        if record_base:
            command += ["--base-commit", git(self.main_checkout, "rev-parse", start_ref)]
        added = subprocess.run(command, input="brief", capture_output=True, text=True, env=self.env())
        self.assertEqual(added.returncode, 0, added.stderr)
        return worktree

    def set_base_commit(self, name, value):
        lane_file = self.state_home / "herdr-lanes" / f"{name}.json"
        entry = json.loads(lane_file.read_text())
        entry["base_commit"] = value
        lane_file.write_text(json.dumps(entry))

    def commit_in(self, worktree):
        git(worktree, "commit", "-q", "--allow-empty", "-m", "work")

    def merge_and_push(self, name, target="master"):
        git(self.main_checkout, "merge", "-q", "--no-ff", "-m", f"merge {name}", name)
        git(self.main_checkout, "push", "-q", "origin", target)

    def sweep(self, failing_lane="", cwd=None):
        return subprocess.run([str(self.script)], capture_output=True, text=True, env=self.env(failing_lane),
                              cwd=cwd)

    def sweep_logging_fetches(self):
        """Run the sweep with a git wrapper that logs each fetch; returns the run and the logged fetch lines."""
        fetch_log = self.root / "fetch-log"
        real_git = shutil.which("git")
        write_stub(self.bin_dir / "git",
                   f'case " $* " in *" fetch "*) echo "$*" >> {fetch_log};; esac\nexec {real_git} "$@"')
        env = self.env()
        env["PATH"] = f"{self.bin_dir}:{env['PATH']}"
        finished = subprocess.run([str(self.script)], capture_output=True, text=True, env=env)
        fetches = fetch_log.read_text().splitlines() if fetch_log.exists() else []
        return finished, fetches

    def closed_calls(self):
        if not self.events.exists():
            return []
        return self.events.read_text().splitlines()

    def test_a_merged_clean_lane_with_a_commit_past_its_base_is_closed(self):
        worktree = self.add_lane("lane-a")
        self.commit_in(worktree)
        self.merge_and_push("lane-a")

        finished = self.sweep()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(finished.stdout.splitlines(), ["closed lane-a"])
        self.assertEqual(self.closed_calls(), ["--close lane-a"])

    def test_a_lane_decided_closable_after_the_deadline_passed_is_kept_as_sweep_deadline(self):
        for name in ("lane-a", "lane-b"):
            worktree = self.add_lane(name)
            shutil.rmtree(worktree)
        # The first close outlasts the deadline; lane-b needs no git call, so only the check before its close stops it.
        write_stub(self.bin_dir / "herdr-lane-resume", 'echo "$*" >> "$EVENTS"\nsleep 2\nexit 0')
        env = self.env()
        env["HERDR_LANE_SWEEP_DEADLINE_SECONDS"] = "1"

        finished = subprocess.run([str(self.script)], capture_output=True, text=True, env=env, timeout=20)

        self.assertEqual(finished.stdout.splitlines(), ["closed lane-a", "kept lane-b: sweep deadline"])
        self.assertEqual(self.closed_calls(), ["--close lane-a"])

    def test_a_merged_lane_is_kept_when_the_caller_runs_inside_its_worktree(self):
        worktree = self.add_lane("lane-a")
        self.commit_in(worktree)
        self.merge_and_push("lane-a")
        inner = worktree / "sub"
        inner.mkdir()
        link = self.root / "link-to-sub"
        link.symlink_to(inner)

        from_root = self.sweep(cwd=worktree)
        from_link = self.sweep(cwd=link)

        self.assertEqual(from_root.stdout.splitlines(), ["kept lane-a: caller runs inside it"], from_root.stderr)
        self.assertEqual(from_link.stdout.splitlines(), ["kept lane-a: caller runs inside it"], from_link.stderr)
        self.assertEqual(self.closed_calls(), [])

    def test_a_lane_with_no_commit_past_its_base_is_kept(self):
        self.add_lane("lane-a")
        base = git(self.main_checkout, "rev-parse", "master")

        finished = self.sweep()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(finished.stdout.splitlines(), [f"kept lane-a: no commit since base {base[:12]}"])
        self.assertEqual(self.closed_calls(), [])

    def test_an_entry_with_no_base_commit_is_kept_even_when_merged(self):
        worktree = self.add_lane("lane-a", record_base=False)
        self.commit_in(worktree)
        self.merge_and_push("lane-a")

        finished = self.sweep()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(finished.stdout.splitlines(), ["kept lane-a: no base commit recorded"])
        self.assertEqual(self.closed_calls(), [])

    def test_a_base_commit_that_is_not_in_the_branch_history_keeps_the_lane(self):
        worktree = self.add_lane("lane-a")
        self.commit_in(worktree)
        self.merge_and_push("lane-a")
        empty_tree = git(self.main_checkout, "hash-object", "-t", "tree", "/dev/null")
        orphan_commit = git(self.main_checkout, "commit-tree", empty_tree, "-m", "unrelated")
        self.set_base_commit("lane-a", orphan_commit)

        finished = self.sweep()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        expected_line = f"kept lane-a: base {orphan_commit[:12]} is not in the history of lane-a"
        self.assertEqual(finished.stdout.splitlines(), [expected_line])
        self.assertEqual(self.closed_calls(), [])

    def test_a_base_commit_id_absent_from_the_repo_keeps_the_lane_with_the_reason(self):
        worktree = self.add_lane("lane-a")
        self.commit_in(worktree)
        self.merge_and_push("lane-a")
        self.set_base_commit("lane-a", "1" * 40)

        finished = self.sweep()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertRegex(finished.stdout, r"^kept lane-a: cannot compare")
        self.assertEqual(self.closed_calls(), [])

    def test_a_lane_with_no_work_that_fast_forwarded_onto_origin_master_is_closed(self):
        worktree = self.add_lane("lane-a")
        self.commit_in(self.main_checkout)
        git(self.main_checkout, "push", "-q", "origin", "master")
        git(worktree, "merge", "-q", "--ff-only", "master")

        finished = self.sweep()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(finished.stdout.splitlines(), ["closed lane-a"])

    def test_a_lane_with_unmerged_commits_is_kept(self):
        worktree = self.add_lane("lane-a")
        self.commit_in(worktree)

        finished = self.sweep()

        self.assertEqual(finished.stdout.splitlines(), ["kept lane-a: unmerged commits"])
        self.assertEqual(self.closed_calls(), [])

    def test_a_caller_whose_directory_was_removed_still_has_every_lane_decided(self):
        worktree = self.add_lane("lane-a")
        self.commit_in(worktree)
        self.merge_and_push("lane-a")
        gone = self.root / "gone"
        gone.mkdir()

        finished = subprocess.run(
            ["bash", "-c", 'cd "$1" && rmdir "$1" && exec "$2"', "bash", str(gone), str(self.script)],
            capture_output=True, text=True, env=self.env())

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(finished.stdout.splitlines(), ["closed lane-a"])

    def test_a_main_checkout_on_a_detached_head_still_compares_with_the_origin_default_branch(self):
        worktree = self.add_lane("lane-a")
        self.commit_in(worktree)
        self.merge_and_push("lane-a")
        git(self.main_checkout, "checkout", "-q", "--detach")

        finished, fetches = self.sweep_logging_fetches()

        self.assertEqual(finished.stdout.splitlines(), ["closed lane-a"], finished.stderr)
        self.assertEqual(len(fetches), 1, fetches)
        self.assertIn("origin master", fetches[0])

    def test_a_worktree_whose_git_status_fails_is_kept_with_the_reason(self):
        worktree = self.add_lane("lane-a")
        self.commit_in(worktree)
        self.merge_and_push("lane-a")
        # A stub git is needed: a broken .git file would fail the earlier head check, not the status call.
        real_git = shutil.which("git")
        write_stub(self.bin_dir / "git",
                   f'case " $* " in *" status "*) echo "fatal: broken index" >&2; exit 128;; esac\n'
                   f'exec {real_git} "$@"')
        env = self.env()
        env["PATH"] = f"{self.bin_dir}:{env['PATH']}"

        finished = subprocess.run([str(self.script)], capture_output=True, text=True, env=env)

        self.assertEqual(finished.stdout.splitlines(), ["kept lane-a: git status failed: fatal: broken index"],
                         finished.stderr)
        self.assertEqual(self.closed_calls(), [])

    def test_a_dirty_lane_is_kept_even_when_merged(self):
        worktree = self.add_lane("lane-a")
        self.commit_in(worktree)
        self.merge_and_push("lane-a")
        (worktree / "scratch.txt").write_text("not committed")

        finished = self.sweep()

        self.assertEqual(finished.stdout.splitlines(), ["kept lane-a: uncommitted changes"])
        self.assertEqual(self.closed_calls(), [])

    def test_a_lane_whose_worktree_folder_is_gone_is_closed(self):
        worktree = self.add_lane("lane-a")
        shutil.rmtree(worktree)

        finished = self.sweep()

        self.assertEqual(finished.stdout.splitlines(), ["closed lane-a"])
        self.assertEqual(self.closed_calls(), ["--close lane-a"])

    def test_a_lane_merged_into_the_main_checkouts_current_branch_but_not_the_default_branch_is_closed(self):
        git(self.main_checkout, "checkout", "-q", "-b", "bench-base")
        git(self.main_checkout, "commit", "-q", "--allow-empty", "-m", "bench")
        git(self.main_checkout, "push", "-q", "origin", "bench-base")
        worktree = self.add_lane("lane-a", start_ref="bench-base")
        self.commit_in(worktree)
        self.merge_and_push("lane-a", target="bench-base")

        finished = self.sweep()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(finished.stdout.splitlines(), ["closed lane-a"])
        self.assertEqual(self.closed_calls(), ["--close lane-a"])

    def test_a_main_checkout_that_is_gone_keeps_the_lane(self):
        worktree = self.add_lane("lane-a")
        self.commit_in(worktree)
        shutil.rmtree(self.main_checkout)

        finished = self.sweep()

        expected = f"kept lane-a: main checkout {self.main_checkout} is gone"
        self.assertEqual(finished.stdout.splitlines(), [expected])
        self.assertEqual(self.closed_calls(), [])

    def test_a_branch_ref_missing_in_the_main_checkout_keeps_the_lane(self):
        worktree = self.add_lane("lane-a")
        self.commit_in(worktree)
        git(self.main_checkout, "update-ref", "-d", "refs/heads/lane-a")

        finished = self.sweep()

        expected = f"kept lane-a: branch lane-a is missing in {self.main_checkout}"
        self.assertEqual(finished.stdout.splitlines(), [expected])
        self.assertEqual(self.closed_calls(), [])

    def test_a_worktree_that_moved_to_another_branch_keeps_the_lane(self):
        worktree = self.add_lane("lane-a")
        self.commit_in(worktree)
        self.merge_and_push("lane-a")
        git(worktree, "switch", "-q", "-c", "next")

        finished = self.sweep()

        self.assertEqual(finished.stdout.splitlines(), ["kept lane-a: worktree is not on lane-a"])
        self.assertEqual(self.closed_calls(), [])

    def test_a_current_branch_that_origin_lacks_is_not_compared_with(self):
        git(self.main_checkout, "checkout", "-q", "-b", "local-only")
        worktree = self.add_lane("lane-a")
        self.commit_in(worktree)
        git(self.main_checkout, "checkout", "-q", "master")
        self.merge_and_push("lane-a")
        git(self.main_checkout, "checkout", "-q", "local-only")

        finished, fetches = self.sweep_logging_fetches()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(finished.stdout.splitlines(), ["closed lane-a"])
        self.assertEqual(len(fetches), 1, fetches)
        self.assertTrue(fetches[0].endswith("fetch --quiet origin master"), fetches)

    def test_no_origin_default_branch_and_a_local_only_current_branch_keeps_the_lane_with_the_reason(self):
        worktree = self.add_lane("lane-a")
        self.commit_in(worktree)
        git(self.main_checkout, "remote", "set-head", "origin", "-d")
        git(self.main_checkout, "checkout", "-q", "-b", "local-only")

        finished = self.sweep()

        self.assertRegex(finished.stdout, r"^kept lane-a: no origin default branch")
        self.assertEqual(self.closed_calls(), [])

    def test_origin_is_fetched_once_per_checkout_however_many_lanes_it_has(self):
        for name in ("lane-a", "lane-b"):
            worktree = self.add_lane(name)
            self.commit_in(worktree)
            self.merge_and_push(name)

        finished, fetches = self.sweep_logging_fetches()

        self.assertEqual(finished.stdout.splitlines(), ["closed lane-a", "closed lane-b"])
        self.assertEqual(len(fetches), 1, fetches)

    def test_a_fetch_that_outlasts_the_deadline_keeps_every_lane_as_sweep_deadline(self):
        for name in ("lane-a", "lane-b"):
            worktree = self.add_lane(name)
            self.commit_in(worktree)
            self.merge_and_push(name)
        real_git = shutil.which("git")
        write_stub(self.bin_dir / "git", f'case " $* " in *" fetch "*) exec sleep 30;; esac\nexec {real_git} "$@"')
        env = self.env()
        env["PATH"] = f"{self.bin_dir}:{env['PATH']}"
        env["HERDR_LANE_SWEEP_DEADLINE_SECONDS"] = "1"

        finished = subprocess.run([str(self.script)], capture_output=True, text=True, env=env, timeout=20)

        self.assertEqual(finished.stdout.splitlines(),
                         ["kept lane-a: sweep deadline", "kept lane-b: sweep deadline"])
        self.assertEqual(self.closed_calls(), [])

    def test_a_failed_fetch_is_reported_for_every_lane_of_that_checkout(self):
        for name in ("lane-a", "lane-b"):
            worktree = self.add_lane(name)
            self.commit_in(worktree)
            self.merge_and_push(name)
        git(self.main_checkout, "remote", "set-url", "origin", str(self.root / "no-such-origin.git"))

        finished = self.sweep()

        lines = finished.stdout.splitlines()
        self.assertEqual(len(lines), 2, finished.stdout)
        for line in lines:
            self.assertRegex(line, r"^kept lane-.: fetch of origin/master failed")
        self.assertEqual(self.closed_calls(), [])

    def test_an_unreachable_origin_with_a_local_only_current_branch_reports_the_failed_fetch(self):
        worktree = self.add_lane("lane-a")
        self.commit_in(worktree)
        self.merge_and_push("lane-a")
        git(self.main_checkout, "remote", "set-head", "origin", "-d")
        git(self.main_checkout, "checkout", "-q", "-b", "local-only")
        git(self.main_checkout, "remote", "set-url", "origin", str(self.root / "no-such-origin.git"))

        finished = self.sweep()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertRegex(finished.stdout, r"^kept lane-a: fetch of origin/local-only failed")
        self.assertEqual(self.closed_calls(), [])

    def test_a_close_that_fails_after_removing_the_entry_reports_the_lane_closed_with_the_prune_reason(self):
        worktree = self.add_lane("lane-a")
        self.commit_in(worktree)
        self.merge_and_push("lane-a")
        write_stub(self.bin_dir / "herdr-lane-resume",
                   f'python3 {LANES_CLI} remove "$2" >/dev/null\necho "prune stuck" >&2\nexit 1')

        finished = self.sweep()

        self.assertEqual(finished.stdout.splitlines(), ["closed lane-a (prune: prune stuck)"])

    def test_a_close_that_fails_keeps_that_lane_with_its_reason_and_the_other_lanes_still_run(self):
        working = self.add_lane("lane-a")
        self.commit_in(working)
        done = self.add_lane("lane-b")
        self.commit_in(done)
        self.merge_and_push("lane-a")
        self.merge_and_push("lane-b")

        finished = self.sweep(failing_lane="lane-a")

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(finished.stdout.splitlines(),
                         ["kept lane-a: claude agent in lane-a is working", "closed lane-b"])
        self.assertEqual(self.closed_calls(), ["--close lane-a", "--close lane-b"])

    def test_the_next_sweep_retries_a_lane_whose_close_was_refused(self):
        worktree = self.add_lane("lane-a")
        self.commit_in(worktree)
        self.merge_and_push("lane-a")
        interrupted = self.sweep(failing_lane="lane-a")
        self.assertEqual(interrupted.stdout.splitlines(), ["kept lane-a: claude agent in lane-a is working"])

        finished = self.sweep()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(finished.stdout.splitlines(), ["closed lane-a"])

    def test_a_close_that_fails_and_breaks_the_lane_list_keeps_the_lane_with_its_reason(self):
        worktree = self.add_lane("lane-a")
        self.commit_in(worktree)
        self.merge_and_push("lane-a")
        lane_file = self.state_home / "herdr-lanes" / "lane-a.json"
        write_stub(self.bin_dir / "herdr-lane-resume", f'echo "{{" > {lane_file}\necho "close broke" >&2\nexit 1')

        finished = self.sweep()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(finished.stdout.splitlines(), ["kept lane-a: close broke"])

    def test_a_current_branch_named_like_the_tail_of_another_origin_branch_is_not_fetched(self):
        worktree = self.add_lane("lane-a")
        self.commit_in(worktree)
        self.merge_and_push("lane-a")
        git(self.main_checkout, "push", "-q", "origin", "master:refs/heads/feature/lane")
        git(self.main_checkout, "checkout", "-q", "-b", "lane")

        finished, fetches = self.sweep_logging_fetches()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(finished.stdout.splitlines(), ["closed lane-a"])
        self.assertEqual(len(fetches), 1, fetches)
        self.assertTrue(fetches[0].endswith("fetch --quiet origin master"), fetches)

    def test_a_close_that_fails_with_no_output_is_kept_with_its_exit_code(self):
        worktree = self.add_lane("lane-a")
        self.commit_in(worktree)
        self.merge_and_push("lane-a")
        write_stub(self.bin_dir / "herdr-lane-resume", "exit 4")

        finished = self.sweep()

        self.assertEqual(finished.stdout.splitlines(), ["kept lane-a: herdr-lane-resume exited 4"])

    def test_a_close_that_fails_with_several_stderr_lines_joins_them(self):
        worktree = self.add_lane("lane-a")
        self.commit_in(worktree)
        self.merge_and_push("lane-a")
        write_stub(self.bin_dir / "herdr-lane-resume", 'echo "first problem" >&2\necho "  second problem" >&2\nexit 1')

        finished = self.sweep()

        self.assertEqual(finished.stdout.splitlines(), ["kept lane-a: first problem; second problem"])

    def test_an_unreadable_lane_list_exits_1(self):
        env = self.env()
        env["HERDR_LANES_CLI"] = str(self.bin_dir / "no-such-lanes.py")

        finished = subprocess.run([str(self.script)], capture_output=True, text=True, env=env)

        self.assertEqual(finished.returncode, 1)
        self.assertIn("herdr-lane-sweep:", finished.stderr)

    def test_an_unknown_argument_exits_1_with_a_message(self):
        finished = subprocess.run([str(self.script), "--bogus"], capture_output=True, text=True, env=self.env())

        self.assertEqual(finished.returncode, 1)
        self.assertIn("unknown argument: --bogus", finished.stderr)

    def test_help_prints_the_header(self):
        finished = subprocess.run([str(self.script), "--help"], capture_output=True, text=True, env=self.env())

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertIn("Usage: herdr-lane-sweep", finished.stdout)
        self.assertIn("kept <name>: <reason>", finished.stdout)


if __name__ == "__main__":
    unittest.main()
