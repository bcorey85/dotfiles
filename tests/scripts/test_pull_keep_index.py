"""Tests for tools/pull_keep_index.py: a pull before a push keeps the user's staged files staged."""
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from toolkit_paths import TOOLS_DIR

SCRIPT = pathlib.Path(os.environ.get("PULL_KEEP_INDEX_SCRIPT") or TOOLS_DIR / "pull_keep_index.py")
GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


class PullKeepIndexTest(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.remote = self.tmp / "remote.git"
        self.git(self.tmp, "init", "-q", "--bare", "-b", "master", str(self.remote))
        self.repo = self.clone("a")
        self.write(self.repo, "f", "1\n")
        self.write(self.repo, "g", "1\n")
        self.git(self.repo, "add", "f", "g")
        self.git(self.repo, "commit", "-qm", "one")
        self.git(self.repo, "push", "-q", "-u", "origin", "HEAD:master")

    def git(self, folder, *arguments):
        env = {**os.environ, **GIT_ENV}
        finished = subprocess.run(["git", "-C", str(folder), *arguments], capture_output=True, text=True, env=env)
        self.assertEqual(finished.returncode, 0, finished.stderr)
        return finished.stdout

    def clone(self, name):
        folder = self.tmp / name
        self.git(self.tmp, "clone", "-q", str(self.remote), str(folder))
        return folder

    def write(self, folder, name, text):
        (folder / name).write_text(text)

    def push_from_other_machine(self, name, text):
        other = self.clone("other-" + name)
        self.write(other, name, text)
        self.git(other, "add", name)
        self.git(other, "commit", "-qm", "other " + name)
        self.git(other, "push", "-q")

    def run_script(self):
        env = {**os.environ, **GIT_ENV}
        return subprocess.run([sys.executable, str(SCRIPT), str(self.repo)], capture_output=True, text=True, env=env)

    def status(self):
        return self.git(self.repo, "status", "--porcelain").splitlines()

    def test_staged_and_unstaged_changes_keep_their_state_across_the_pull(self):
        self.push_from_other_machine("h", "2\n")
        self.write(self.repo, "f", "staged\n")
        self.git(self.repo, "add", "f")
        self.write(self.repo, "g", "unstaged\n")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(sorted(self.status()), [" M g", "M  f"])
        self.assertEqual((self.repo / "h").read_text(), "2\n")
        self.assertEqual(self.git(self.repo, "stash", "list"), "")

    def test_a_partly_staged_file_keeps_both_its_staged_and_unstaged_text(self):
        self.push_from_other_machine("h", "2\n")
        self.write(self.repo, "f", "staged\n")
        self.git(self.repo, "add", "f")
        self.write(self.repo, "f", "staged then edited\n")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(self.status(), ["MM f"])
        self.assertEqual(self.git(self.repo, "show", ":f"), "staged\n")
        self.assertEqual((self.repo / "f").read_text(), "staged then edited\n")

    def test_a_clean_tree_just_pulls(self):
        self.push_from_other_machine("h", "2\n")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(self.status(), [])
        self.assertEqual((self.repo / "h").read_text(), "2\n")

    def test_a_failed_pull_puts_the_changes_back_staged(self):
        self.write(self.repo, "f", "staged\n")
        self.git(self.repo, "add", "f")
        shutil.rmtree(self.remote)

        finished = self.run_script()

        self.assertNotEqual(finished.returncode, 0)
        self.assertIn("git pull failed", finished.stderr)
        self.assertIn("the local changes are back in place", finished.stderr)
        self.assertEqual(self.status(), ["M  f"])

    def test_a_staged_change_the_pull_conflicts_with_stops_and_names_the_saved_commit(self):
        self.push_from_other_machine("f", "theirs\n")
        self.write(self.repo, "f", "mine\n")
        self.git(self.repo, "add", "f")

        finished = self.run_script()

        self.assertNotEqual(finished.returncode, 0)
        self.assertIn("stash apply --index", finished.stderr)
        saved = finished.stderr.split("stash apply --index ")[1].split()[0]
        self.assertEqual(self.git(self.repo, "show", saved + ":f"), "mine\n")

    def add_files(self, *names):
        for name in names:
            self.write(self.repo, name, "1\n")
        self.git(self.repo, "add", *names)
        self.git(self.repo, "commit", "-qm", "more files")
        self.git(self.repo, "push", "-q")

    def test_the_re_apply_names_the_saved_commit_to_the_built_page_driver(self):
        # The agent-evals built-page driver rebuilds a page during a stash apply only when BUILT_PAGE_STASH names it.
        recorder = self.tmp / "record_driver.py"
        recorder.write_text("import os, pathlib, sys\n"
                            "pathlib.Path(sys.argv[1]).write_text(os.environ.get('BUILT_PAGE_STASH', ''))\n"
                            "pathlib.Path(sys.argv[3]).write_text(pathlib.Path(sys.argv[4]).read_text())\n")
        record = self.tmp / "record"
        self.git(self.repo, "config", "merge.built-page.driver", f"{sys.executable} {recorder} {record} %O %A %B")
        self.write(self.repo, ".gitattributes", "f merge=built-page\n")
        self.git(self.repo, "add", ".gitattributes")
        self.git(self.repo, "commit", "-qm", "attributes")
        self.git(self.repo, "push", "-q")
        self.push_from_other_machine("f", "theirs\n")
        self.write(self.repo, "f", "mine\n")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        saved = record.read_text()
        self.assertEqual(self.git(self.repo, "show", saved + ":f"), "mine\n")
        self.assertEqual(self.status(), [" M f"])

    def test_a_conflicting_re_apply_keeps_the_staged_and_unstaged_split(self):
        self.add_files("k", "m")
        self.push_from_other_machine("f", "theirs\n")
        self.write(self.repo, "f", "mine\n")
        self.write(self.repo, "g", "staged\n")
        self.git(self.repo, "add", "g")
        self.write(self.repo, "m", "staged\n")
        self.git(self.repo, "add", "m")
        self.write(self.repo, "m", "staged then edited\n")
        self.write(self.repo, "k", "unstaged\n")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 1, finished.stderr)
        self.assertEqual(sorted(self.status()), [" M k", "M  g", "MM m", "UU f"])
        self.assertEqual(self.git(self.repo, "show", ":m"), "staged\n")
        self.assertEqual((self.repo / "m").read_text(), "staged then edited\n")
        self.assertIn("conflict with the pull in: f.", finished.stderr)
        recovery = finished.stderr.split("then run: ")[1].split("\n")[0].split()
        self.write(self.repo, "f", "resolved\n")
        subprocess.run(recovery, check=True, env={**os.environ, **GIT_ENV})
        self.assertEqual(sorted(self.status()), [" M f", " M k", "M  g", "MM m"])

    def test_a_new_branch_with_no_upstream_and_no_remote_branch_exits_0_and_keeps_staged_files(self):
        self.git(self.repo, "checkout", "-q", "-b", "fresh")
        self.write(self.repo, "f", "staged\n")
        self.git(self.repo, "add", "f")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertIn("nothing to pull", finished.stdout)
        self.assertEqual(self.status(), ["M  f"])

    def test_a_remote_branch_whose_name_ends_in_the_local_name_does_not_count_as_the_same_branch(self):
        self.git(self.repo, "push", "-q", "origin", "HEAD:refs/heads/feature/fresh")
        self.git(self.repo, "checkout", "-q", "-b", "fresh")
        self.write(self.repo, "f", "staged\n")
        self.git(self.repo, "add", "f")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertIn("nothing to pull", finished.stdout)
        self.assertEqual(self.status(), ["M  f"])

    def test_a_branch_with_no_upstream_pulls_the_remote_branch_of_the_same_name(self):
        self.git(self.repo, "checkout", "-q", "-b", "shared")
        self.git(self.repo, "push", "-q", "origin", "shared")
        other = self.clone("other-shared")
        self.git(other, "checkout", "-q", "shared")
        self.write(other, "h", "2\n")
        self.git(other, "add", "h")
        self.git(other, "commit", "-qm", "other h")
        self.git(other, "push", "-q", "origin", "shared")
        self.write(self.repo, "f", "staged\n")
        self.git(self.repo, "add", "f")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual((self.repo / "h").read_text(), "2\n")
        self.assertEqual(self.status(), ["M  f"])
        upstream = self.git(self.repo, "rev-parse", "--abbrev-ref", "@{u}").strip()
        self.assertEqual(upstream, "origin/shared")

    def test_a_branch_whose_upstream_was_deleted_on_origin_exits_1_so_a_chained_push_does_not_run(self):
        self.git(self.repo, "checkout", "-q", "-b", "gone")
        self.git(self.repo, "push", "-q", "-u", "origin", "gone")
        self.git(self.remote, "branch", "-q", "-D", "gone")
        self.git(self.repo, "fetch", "-q", "--prune")
        self.write(self.repo, "f", "staged\n")
        self.git(self.repo, "add", "f")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 1, finished.stdout)
        self.assertIn("the upstream refs/heads/gone of gone is gone from origin", finished.stderr)
        self.assertIn("a chained push stops here so it does not recreate it", finished.stderr)
        self.assertIn(f"git -C {self.repo} branch --unset-upstream", finished.stderr)
        self.assertIn(f"git -C {self.repo} push -u origin HEAD", finished.stderr)
        self.assertNotIn("stash apply --index", finished.stderr)
        self.assertEqual(self.status(), ["M  f"])

    def test_an_unpruned_upstream_deleted_on_origin_exits_1_with_the_recovery_after_the_failed_pull(self):
        self.git(self.repo, "checkout", "-q", "-b", "gone")
        self.git(self.repo, "push", "-q", "-u", "origin", "gone")
        self.git(self.remote, "branch", "-q", "-D", "gone")
        self.write(self.repo, "f", "staged\n")
        self.git(self.repo, "add", "f")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 1, finished.stdout)
        self.assertIn("the upstream refs/heads/gone of gone is gone from origin", finished.stderr)
        self.assertIn("the local changes are in place", finished.stderr)
        self.assertIn(f"git -C {self.repo} branch --unset-upstream", finished.stderr)
        self.assertEqual(self.status(), ["M  f"])

    def test_a_branch_whose_upstream_is_gone_from_a_remote_other_than_origin_names_that_remote(self):
        self.git(self.repo, "remote", "add", "upstream", str(self.remote))
        self.git(self.repo, "checkout", "-q", "-b", "gone")
        self.git(self.repo, "push", "-q", "-u", "upstream", "gone")
        self.git(self.remote, "branch", "-q", "-D", "gone")
        self.git(self.repo, "fetch", "-q", "--prune", "upstream")
        self.write(self.repo, "f", "staged\n")
        self.git(self.repo, "add", "f")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 1, finished.stdout)
        self.assertIn("the upstream refs/heads/gone of gone is gone from upstream", finished.stderr)
        self.assertIn(f"git -C {self.repo} push -u upstream HEAD", finished.stderr)
        self.assertNotIn("origin", finished.stderr)
        self.assertEqual(self.status(), ["M  f"])

    def test_a_set_upstream_whose_remote_url_is_a_missing_path_exits_1_with_the_lookup_failure(self):
        self.git(self.repo, "checkout", "-q", "-b", "gone")
        self.git(self.repo, "push", "-q", "-u", "origin", "gone")
        self.git(self.remote, "branch", "-q", "-D", "gone")
        self.git(self.repo, "fetch", "-q", "--prune")
        missing = self.tmp / "no-such-remote.git"
        self.git(self.repo, "remote", "set-url", "origin", str(missing))
        self.write(self.repo, "f", "staged\n")
        self.git(self.repo, "add", "f")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 1, finished.stdout)
        self.assertIn(f"could not look up refs/heads/gone on origin in {self.repo}:", finished.stderr)
        self.assertNotIn("is gone from", finished.stderr)
        self.assertEqual(self.status(), ["M  f"])

    def test_a_failed_pull_whose_remote_also_fails_the_lookup_reports_the_pull_failure(self):
        self.git(self.repo, "checkout", "-q", "-b", "gone")
        self.git(self.repo, "push", "-q", "-u", "origin", "gone")
        self.git(self.remote, "branch", "-q", "-D", "gone")
        self.git(self.repo, "remote", "set-url", "origin", str(self.tmp / "no-such-remote.git"))
        self.write(self.repo, "f", "staged\n")
        self.git(self.repo, "add", "f")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 1, finished.stdout)
        self.assertIn("git pull failed", finished.stderr)
        self.assertIn("the local changes are back in place", finished.stderr)
        self.assertEqual(self.status(), ["M  f"])

    def test_a_failed_lookup_of_the_configured_upstream_exits_1_naming_the_remote_and_ref(self):
        self.git(self.repo, "checkout", "-q", "-b", "lost")
        self.git(self.repo, "push", "-q", "-u", "origin", "lost")
        self.git(self.repo, "config", "branch.lost.remote", "nowhere")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 1, finished.stdout)
        self.assertIn("could not look up refs/heads/lost on nowhere", finished.stderr)
        self.assertNotIn("is gone from", finished.stderr)

    def test_a_single_branch_clone_pulls_the_remote_branch_and_sets_its_upstream(self):
        self.git(self.repo, "push", "-q", "origin", "HEAD:refs/heads/solo")
        single = self.tmp / "single"
        self.git(self.tmp, "clone", "-q", "--single-branch", "-b", "master", str(self.remote), str(single))
        self.git(single, "fetch", "-q", "origin", "solo")
        self.git(single, "checkout", "-q", "-b", "solo", "FETCH_HEAD")
        self.assertEqual(self.git(single, "branch", "-r", "--list", "origin/solo"), "")
        self.repo = single

        finished = self.run_script()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        merge = self.git(single, "config", "--get", "branch.solo.merge").strip()
        self.assertEqual(merge, "refs/heads/solo")
        self.assertEqual(self.git(single, "config", "--get", "branch.solo.remote").strip(), "origin")

        second = self.run_script()

        self.assertEqual(second.returncode, 0, second.stderr)

    def test_a_folder_that_is_not_a_repo_exits_1_naming_the_failed_branch_lookup(self):
        not_a_repo = self.tmp / "plain"
        not_a_repo.mkdir()
        env = {**os.environ, **GIT_ENV, "GIT_CEILING_DIRECTORIES": str(self.tmp)}

        finished = subprocess.run([sys.executable, str(SCRIPT), str(not_a_repo)], capture_output=True, text=True,
                                  env=env)

        self.assertEqual(finished.returncode, 1)
        self.assertIn("git branch --show-current failed", finished.stderr)

    def test_a_branch_with_no_upstream_and_no_origin_exits_1_with_the_git_error(self):
        self.git(self.repo, "checkout", "-q", "-b", "fresh")
        self.git(self.repo, "remote", "remove", "origin")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 1)
        self.assertIn("could not look up refs/heads/fresh on origin", finished.stderr)

    def test_a_branch_rewritten_locally_pulls_nothing_and_says_to_force_push(self):
        old_tip = self.git(self.repo, "rev-parse", "--short", "HEAD").strip()
        self.write(self.repo, "f", "amended\n")
        self.git(self.repo, "commit", "-qa", "--amend", "--no-edit")
        head = self.git(self.repo, "rev-parse", "HEAD")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertIn(f"was rewritten locally (the upstream tip {old_tip} was on it before); nothing pulled.",
                      finished.stdout)
        self.assertIn("--force-with-lease", finished.stdout)
        self.assertEqual(self.git(self.repo, "rev-parse", "HEAD"), head)
        self.assertEqual(self.status(), [])
        for name in ("rebase-merge", "rebase-apply"):
            self.assertFalse((self.repo / ".git" / name).exists(), name)

    def test_a_rewrite_leaves_staged_and_unstaged_changes_untouched(self):
        self.write(self.repo, "f", "amended\n")
        self.git(self.repo, "commit", "-qa", "--amend", "--no-edit")
        self.write(self.repo, "f", "staged\n")
        self.git(self.repo, "add", "f")
        self.write(self.repo, "g", "unstaged\n")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertIn("--force-with-lease", finished.stdout)
        self.assertEqual(sorted(self.status()), [" M g", "M  f"])
        self.assertEqual((self.repo / "f").read_text(), "staged\n")
        self.assertEqual((self.repo / "g").read_text(), "unstaged\n")

    def test_a_rewrite_after_another_machine_pushed_without_a_fetch_still_pulls(self):
        self.commit_local("k", "1\n")
        self.git(self.repo, "push", "-q")
        self.push_from_other_machine("h", "2\n")
        self.write(self.repo, "k", "amended\n")
        self.git(self.repo, "commit", "-qa", "--amend", "--no-edit")

        finished = self.run_script()

        self.assertNotIn("rewritten locally", finished.stdout)
        self.assertEqual((self.repo / "h").read_text(), "2\n", finished.stdout + finished.stderr)
        self.assertEqual(finished.returncode, 1, finished.stdout + finished.stderr)
        self.assertIn("the pull stopped mid-rebase", finished.stderr)

    def test_a_rewrite_with_the_upstream_deleted_on_the_remote_exits_1_naming_the_gone_upstream(self):
        self.git(self.repo, "checkout", "-q", "-b", "topic")
        self.git(self.repo, "push", "-q", "-u", "origin", "topic")
        self.git(self.remote, "branch", "-q", "-D", "topic")
        self.write(self.repo, "f", "amended\n")
        self.git(self.repo, "commit", "-qa", "--amend", "--no-edit")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 1, finished.stdout)
        self.assertNotIn("rewritten locally", finished.stdout)
        self.assertIn("is gone from origin", finished.stderr)

    def test_a_commit_another_machine_pushed_is_still_pulled_after_a_fetch(self):
        self.push_from_other_machine("h", "2\n")
        self.git(self.repo, "fetch", "-q")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertNotIn("rewritten locally", finished.stdout)
        self.assertEqual((self.repo / "h").read_text(), "2\n")

    def commit_local(self, name, text):
        self.write(self.repo, name, text)
        self.git(self.repo, "add", name)
        self.git(self.repo, "commit", "-qm", "local " + name)

    def assert_names_both_ways_out(self, stderr):
        self.assertIn(f"git -C {self.repo} rebase --continue", stderr)
        self.assertIn(f"git -C {self.repo} rebase --abort", stderr)
        self.assertIn("refs/heads/master", stderr)

    def test_a_run_inside_a_stopped_rebase_touches_nothing_and_names_the_way_out(self):
        self.commit_local("h", "local\n")
        env = {**os.environ, **GIT_ENV, "GIT_SEQUENCE_EDITOR": "sed -i 1s/^pick/edit/"}
        subprocess.run(["git", "-C", str(self.repo), "rebase", "-q", "-i", "HEAD~1"], check=True, env=env,
                       capture_output=True)
        self.write(self.repo, "f", "staged\n")
        self.git(self.repo, "add", "f")
        self.write(self.repo, "g", "unstaged\n")
        head = self.git(self.repo, "rev-parse", "HEAD")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 1, finished.stderr)
        self.assertEqual(sorted(self.status()), [" M g", "M  f"])
        self.assertEqual(self.git(self.repo, "rev-parse", "HEAD"), head)
        self.assertIn("a rebase is stopped", finished.stderr)
        self.assertIn("no conflicted paths", finished.stderr)
        self.assert_names_both_ways_out(finished.stderr)

    def push_to_topic_from_other_machine(self, name, text):
        other = self.clone("other-topic-" + name)
        self.git(other, "checkout", "-q", "topic")
        self.write(other, name, text)
        self.git(other, "add", name)
        self.git(other, "commit", "-qm", "other " + name)
        self.git(other, "push", "-q")

    def test_a_replayed_merge_that_had_resolved_conflicts_falls_back_to_a_merge_of_the_remote(self):
        self.git(self.repo, "checkout", "-q", "-b", "topic")
        self.commit_local("f", "topic\n")
        self.git(self.repo, "push", "-q", "-u", "origin", "topic")
        self.push_from_other_machine("f", "master\n")
        self.git(self.repo, "fetch", "-q")
        env = {**os.environ, **GIT_ENV}
        subprocess.run(["git", "-C", str(self.repo), "merge", "-q", "origin/master"], env=env, capture_output=True)
        self.write(self.repo, "f", "resolved\n")
        self.git(self.repo, "commit", "-qam", "merge master, conflict resolved")
        self.push_to_topic_from_other_machine("h", "2\n")
        self.write(self.repo, "g", "staged\n")
        self.git(self.repo, "add", "g")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 0, finished.stdout + finished.stderr)
        self.assertIn("merged the remote instead", finished.stdout)
        self.assertEqual((self.repo / "f").read_text(), "resolved\n")
        self.assertEqual((self.repo / "h").read_text(), "2\n")
        self.assertEqual(self.status(), ["M  g"])
        self.git(self.repo, "merge-base", "--is-ancestor", "origin/topic", "HEAD")

    def test_a_pull_that_stops_mid_rebase_names_the_conflict_and_both_ways_out(self):
        self.push_from_other_machine("f", "theirs\n")
        self.commit_local("f", "local\n")
        self.write(self.repo, "g", "unstaged\n")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 1, finished.stderr)
        self.assertIn("conflicted paths: f", finished.stderr)
        self.assert_names_both_ways_out(finished.stderr)
        self.assertIn("stash apply --index", finished.stderr)
        saved = finished.stderr.split("stash apply --index ")[1].split()[0]
        self.assertEqual(self.git(self.repo, "show", saved + ":g"), "unstaged\n")


if __name__ == "__main__":
    unittest.main()
