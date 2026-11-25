"""Tests for tools/pull_keep_index.py: a pull before a push keeps the user's staged files staged."""
import json
import os
import pathlib
import shlex
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
import unittest.mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from toolkit_paths import LIB_DIR, TOOLS_DIR

SCRIPT = pathlib.Path(os.environ.get("PULL_KEEP_INDEX_SCRIPT") or TOOLS_DIR / "pull_keep_index.py")
GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
REF = "refs/pull-keep-index/20260101T000000Z-abc12345"


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
        # An empty session registry and a session id of its own keep every test on the solo route.
        config_dir = self.tmp / "claude-config"
        (config_dir / "sessions").mkdir(parents=True)
        environment = {"CLAUDE_CONFIG_DIR": str(config_dir), "CLAUDE_CODE_SESSION_ID": "self-id"}
        patcher = unittest.mock.patch.dict(os.environ, environment)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.config_dir = config_dir

    def register_other(self, cwd, session_id="other"):
        """Write a live registry row for a session working in `cwd`; its pid is a `sleep` child that cleanup kills."""
        sleeper = subprocess.Popen(["sleep", "600"])
        self.addCleanup(sleeper.wait)
        self.addCleanup(sleeper.kill)
        row = {"pid": sleeper.pid, "sessionId": session_id, "name": "lane-other", "cwd": str(cwd)}
        (self.config_dir / "sessions" / f"{sleeper.pid}.json").write_text(json.dumps(row))

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
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text(text)

    def push_from_other_machine(self, name, text):
        self.push_files_from_other_machine({name: text})

    def push_files_from_other_machine(self, files):
        label = "-".join(name.replace("/", "_") for name in files)
        other = self.clone("other-" + label)
        for name, text in files.items():
            self.write(other, name, text)
        self.git(other, "add", *files)
        self.git(other, "commit", "-qm", "other " + label)
        self.git(other, "push", "-q")

    def run_script(self, *arguments):
        env = {**os.environ, **GIT_ENV}
        return subprocess.run([sys.executable, str(SCRIPT), *arguments, str(self.repo)], capture_output=True,
                              text=True, env=env)

    def saved_commit(self, stderr):
        return stderr.split("The local changes are saved in ")[1].split()[0]

    def mark_built_pages(self, *names):
        driver = self.tmp / "rebuild_driver.py"
        driver.write_text("import pathlib, sys\npathlib.Path(sys.argv[1]).write_text('rebuilt\\n')\n")
        self.git(self.repo, "config", "merge.built-page.driver", f"{sys.executable} {driver} %A")
        self.write(self.repo, ".gitattributes", "".join(f"{name} merge=built-page\n" for name in names))
        self.git(self.repo, "add", ".gitattributes")
        self.git(self.repo, "commit", "-qm", "attributes")
        self.git(self.repo, "push", "-q")

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

    def kept_refs(self):
        listed = self.git(self.repo, "for-each-ref", "--format=%(refname) %(objectname)", "refs/pull-keep-index/")
        return [line.split() for line in listed.splitlines()]

    def make_saved_commit(self, name, text, staged=False):
        self.write(self.repo, name, text)
        if staged:
            self.git(self.repo, "add", name)
        saved = self.git(self.repo, "stash", "create").strip()
        self.git(self.repo, "reset", "-q", "--hard")
        return saved

    def test_help_prints_the_usage_and_exits_0(self):
        env = {**os.environ, **GIT_ENV}

        for flag in ("--help", "-h"):
            finished = subprocess.run([sys.executable, str(SCRIPT), flag], capture_output=True, text=True, env=env)

            self.assertEqual(finished.returncode, 0, finished.stderr)
            self.assertIn("Usage: pull_keep_index.py <repo>", finished.stdout, flag)
            self.assertIn("--put-back", finished.stdout, flag)
            self.assertIn("refs/pull-keep-index/", finished.stdout, flag)

    def test_a_ref_that_cannot_be_made_exits_1_naming_the_saved_commit_before_anything_is_set_aside(self):
        # A file where the ref's folder belongs makes `update-ref` fail.
        (self.repo / ".git" / "refs" / "pull-keep-index").write_text("in the way\n")
        self.write(self.repo, "g", "unstaged\n")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 1, finished.stderr)
        self.assertIn("could not keep a ref", finished.stderr)
        self.assertIn("Nothing was set aside.", finished.stderr)
        self.assertRegex(finished.stderr, r"saved changes [0-9a-f]{40}")
        self.assertEqual(self.status(), [" M g"])

    def test_put_back_of_a_hash_with_two_refs_deletes_only_the_first_by_name(self):
        saved = self.make_saved_commit("g", "unstaged\n")
        first = "refs/pull-keep-index/20260101T000000Z-a"
        second = "refs/pull-keep-index/20260102T000000Z-b"
        self.git(self.repo, "update-ref", second, saved)
        self.git(self.repo, "update-ref", first, saved)

        finished = self.run_script("--put-back", saved)

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual([name for name, _hash in self.kept_refs()], [second])
        self.assertIn(f"older saved changes kept under: {second}", finished.stderr)

    def test_a_ref_that_is_not_a_saved_commit_exits_1_and_makes_no_ref(self):
        head = self.git(self.repo, "rev-parse", "HEAD").strip()
        ref = "refs/pull-keep-index/20260101T000000Z-plain"
        self.git(self.repo, "update-ref", ref, head)

        finished = self.run_script("--put-back", ref)

        self.assertEqual(finished.returncode, 1, finished.stderr)
        self.assertIn(f"pull_keep_index: {ref} is not a saved-changes commit", finished.stderr)
        self.assertEqual(self.kept_refs(), [[ref, head]])

    def test_a_failed_put_back_leaves_a_ref_at_the_saved_commit_and_names_it(self):
        # The hook recreates g after set_aside's reset, so the pull refuses and the apply stops on the file.
        hook = self.repo / ".git" / "hooks" / "reference-transaction"
        hook.write_text("#!/bin/sh\n[ \"$1\" = committed ] || exit 0\n"
                        "while read old new ref; do\n"
                        "  case \"$ref\" in refs/heads/*) echo other > g ;; esac\n"
                        "done\n")
        hook.chmod(0o755)
        self.push_from_other_machine("h", "2\n")
        self.write(self.repo, "g", "unstaged\n")

        finished = self.run_script()

        self.assertNotEqual(finished.returncode, 0)
        kept = self.kept_refs()
        self.assertEqual(len(kept), 1, finished.stderr)
        ref, saved = kept[0]
        self.assertEqual(self.git(self.repo, "show", f"{saved}:g"), "unstaged\n")
        self.assertIn(ref, finished.stderr)
        self.assertIn("would be overwritten", finished.stderr)

    def test_a_clean_run_leaves_no_ref(self):
        self.push_from_other_machine("h", "2\n")
        self.write(self.repo, "f", "staged\n")
        self.git(self.repo, "add", "f")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(self.kept_refs(), [])

    def test_put_back_of_a_ref_deletes_it_and_hands_the_driver_the_hash(self):
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
        saved = self.make_saved_commit("f", "mine\n")
        ref = "refs/pull-keep-index/20260101T000000Z-older"
        self.git(self.repo, "update-ref", "refs/pull-keep-index/20260101T000000Z-mine", saved)
        self.git(self.repo, "update-ref", ref, self.git(self.repo, "rev-parse", "HEAD").strip())
        self.push_from_other_machine("f", "theirs\n")
        self.git(self.repo, "pull", "-q", "--rebase")

        finished = self.run_script("--put-back", "refs/pull-keep-index/20260101T000000Z-mine")

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(record.read_text(), saved)
        self.assertEqual(len(record.read_text()), 40)
        self.assertEqual([name for name, _hash in self.kept_refs()], [ref])
        self.assertIn(f"older saved changes kept under: {ref}", finished.stderr)

    def test_put_back_of_a_hash_deletes_the_ref_that_points_at_it(self):
        saved = self.make_saved_commit("g", "unstaged\n")
        self.git(self.repo, "update-ref", "refs/pull-keep-index/20260101T000000Z-x", saved)

        finished = self.run_script("--put-back", saved)

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(self.kept_refs(), [])
        self.assertEqual(self.status(), [" M g"])

    def test_put_back_of_a_hash_with_no_ref_succeeds_and_leaves_no_ref(self):
        saved = self.make_saved_commit("g", "unstaged\n")

        finished = self.run_script("--put-back", saved)

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(self.kept_refs(), [])

    def test_a_failed_put_back_of_a_hash_with_no_ref_leaves_a_new_ref_and_names_it(self):
        saved = self.make_saved_commit("f", "mine\n", staged=True)
        self.push_from_other_machine("f", "theirs\n")
        self.git(self.repo, "pull", "-q", "--rebase")

        finished = self.run_script("--put-back", saved)

        self.assertEqual(finished.returncode, 1, finished.stderr)
        kept = self.kept_refs()
        self.assertEqual(len(kept), 1, finished.stderr)
        self.assertEqual(kept[0][1], saved)
        self.assertIn(kept[0][0], finished.stderr)

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
        self.assertIn("--put-back ", finished.stderr)
        saved = finished.stderr.split("--put-back ")[1].split()[0]
        self.assertEqual(self.git(self.repo, "show", saved + ":f"), "mine\n")
        own_lines = [line for line in finished.stderr.splitlines() if line.startswith("pull_keep_index:")]
        self.assertTrue(own_lines)
        for line in own_lines:
            self.assertNotIn("stash", line.lower())

    def test_put_back_verb_restores_saved_changes_with_the_split(self):
        self.write(self.repo, "f", "staged\n")
        self.git(self.repo, "add", "f")
        self.write(self.repo, "g", "unstaged\n")
        saved = self.git(self.repo, "stash", "create").strip()
        self.git(self.repo, "reset", "-q", "--hard")

        finished = self.run_script("--put-back", saved)

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(sorted(self.status()), [" M g", "M  f"])

    def test_a_put_back_call_with_no_repo_prints_the_usage(self):
        env = {**os.environ, **GIT_ENV}

        for extra in ([], ["abc"]):
            finished = subprocess.run([sys.executable, str(SCRIPT), "--put-back", *extra], capture_output=True,
                                      text=True, env=env)

            self.assertNotEqual(finished.returncode, 0, extra)
            self.assertIn("Usage: pull_keep_index.py <repo>", finished.stderr, extra)

    def assert_rolled_back(self, stderr, stage, conflicted, saved_file, saved_text):
        """The stop of a part that would not apply: names the file and the ref, says the changes were not put back,
        leaves no tracked change, and keeps the ref at the saved commit."""
        self.assertIn(f"the {stage} local changes conflict with it in {conflicted} and were not put back", stderr)
        kept = self.kept_refs()
        self.assertEqual(len(kept), 1, stderr)
        ref, saved = kept[0]
        self.assertIn(f"(ref {ref})", stderr)
        self.assertIn(f"BUILT_PAGE_STASH={saved} git -C {self.repo} stash apply {saved}", stderr)
        self.assertEqual(self.git(self.repo, "show", f"{saved}:{saved_file}"), saved_text)
        self.assertEqual(self.git(self.repo, "status", "--porcelain", "--untracked-files=no"), "")

    def test_a_staged_clash_on_a_built_page_and_an_ordinary_file_rolls_back_and_names_the_ref(self):
        self.add_files("k")
        self.mark_built_pages("f")
        self.push_from_other_machine("f", "theirs\n")
        self.push_from_other_machine("k", "theirs\n")
        self.write(self.repo, "f", "mine\n")
        self.git(self.repo, "add", "f")
        self.write(self.repo, "k", "staged\n")
        self.git(self.repo, "add", "k")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 1, finished.stderr)
        self.assert_rolled_back(finished.stderr, "staged", "k", "k", "staged\n")
        self.assertEqual((self.repo / "f").read_text(), "theirs\n")
        self.assertEqual((self.repo / "k").read_text(), "theirs\n")

    def test_a_built_page_clash_beside_an_ordinary_file_the_pull_changed_in_other_hunks_is_rebuilt(self):
        self.add_files("k")
        long_text = "".join(f"{i}\n" for i in range(30))
        self.write(self.repo, "k", long_text)
        self.git(self.repo, "add", "k")
        self.git(self.repo, "commit", "-qm", "long k")
        self.git(self.repo, "push", "-q")
        self.mark_built_pages("f")
        self.push_from_other_machine("f", "theirs\n")
        other = self.tmp / "other-f"
        self.write(other, "k", long_text.replace("0\n", "T\n", 1))
        self.git(other, "commit", "-qam", "other k")
        self.git(other, "push", "-q")
        self.write(self.repo, "f", "mine\n")
        self.write(self.repo, "k", long_text.replace("29\n", "M\n"))
        self.git(self.repo, "add", "f", "k")
        self.write(self.repo, "g", "unstaged\n")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(sorted(self.status()), [" M g", "M  f", "M  k"])
        self.assertEqual(self.git(self.repo, "show", ":f"), "rebuilt\n")
        self.assertEqual(self.git(self.repo, "show", ":k"), long_text.replace("0\n", "T\n", 1).replace("29\n", "M\n"))

    def test_put_back_of_a_built_page_clash_beside_a_mergeable_file_rebuilds_the_page(self):
        self.add_files("k")
        long_text = "".join(f"{i}\n" for i in range(30))
        self.write(self.repo, "k", long_text)
        self.git(self.repo, "add", "k")
        self.git(self.repo, "commit", "-qm", "long k")
        self.git(self.repo, "push", "-q")
        self.mark_built_pages("f")
        self.write(self.repo, "f", "mine\n")
        self.write(self.repo, "k", long_text.replace("29\n", "M\n"))
        self.git(self.repo, "add", "f", "k")
        self.write(self.repo, "g", "unstaged\n")
        saved = self.git(self.repo, "stash", "create").strip()
        self.git(self.repo, "reset", "-q", "--hard")
        self.push_from_other_machine("f", "theirs\n")
        other = self.tmp / "other-f"
        self.write(other, "k", long_text.replace("0\n", "T\n", 1))
        self.git(other, "commit", "-qam", "other k")
        self.git(other, "push", "-q")
        self.git(self.repo, "pull", "-q")

        finished = self.run_script("--put-back", saved)

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(sorted(self.status()), [" M g", "M  f", "M  k"])
        self.assertEqual(self.git(self.repo, "show", ":f"), "rebuilt\n")

    def test_help_prints_the_usage_and_exits_0_from_any_folder(self):
        env = {**os.environ, **GIT_ENV}
        for flag in ("--help", "-h"):
            finished = subprocess.run([sys.executable, str(SCRIPT), flag], capture_output=True, text=True, env=env,
                                      cwd=self.tmp)

            self.assertEqual(finished.returncode, 0, finished.stderr)
            self.assertIn("Usage: pull_keep_index.py <repo>", finished.stdout)

    def test_a_built_page_clash_with_an_unstaged_conflict_rolls_back_and_names_the_ref(self):
        self.mark_built_pages("f")
        self.push_from_other_machine("f", "theirs\n")
        self.push_from_other_machine("g", "theirs\n")
        self.write(self.repo, "f", "mine\n")
        self.git(self.repo, "add", "f")
        self.write(self.repo, "g", "unstaged\n")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 1, finished.stderr)
        self.assert_rolled_back(finished.stderr, "unstaged", "g", "g", "unstaged\n")
        self.assertEqual(self.status(), [])
        self.assertEqual((self.repo / "g").read_text(), "theirs\n")

    def test_a_built_page_the_driver_gives_up_on_exits_1_naming_the_page_the_add_command_and_the_ref(self):
        self.mark_built_pages("f")
        failing = self.tmp / "failing_driver.py"
        failing.write_text("import sys\nsys.stderr.write('no way')\nsys.exit(1)\n")
        self.git(self.repo, "config", "merge.built-page.driver", f"{sys.executable} {failing} %A")
        self.push_from_other_machine("f", "theirs\n")
        self.write(self.repo, "f", "mine\n")
        self.git(self.repo, "add", "f")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 1, finished.stderr)
        self.assertIn("the built-page driver could not rebuild f: no way", finished.stderr)
        self.assertIn(f"git -C {self.repo} --literal-pathspecs add -- f", finished.stderr)
        kept = self.kept_refs()
        self.assertEqual(len(kept), 1, finished.stderr)
        self.assertIn(f"(ref {kept[0][0]})", finished.stderr)
        self.assertEqual(self.status(), [])
        self.assertEqual((self.repo / "f").read_text(), "theirs\n")

    def test_only_a_staged_built_page_is_rebuilt_with_no_conflict_message(self):
        # Steps 1 and 3 have nothing to apply once the page is left out; both are skipped.
        self.mark_built_pages("f")
        self.push_from_other_machine("f", "theirs\n")
        self.write(self.repo, "f", "mine\n")
        self.git(self.repo, "add", "f")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertNotIn("were not put back", finished.stderr)
        self.assertEqual(self.status(), ["M  f"])
        self.assertEqual(self.git(self.repo, "show", ":f"), "rebuilt\n")
        self.assertEqual(self.kept_refs(), [])

    def set_up_the_incident(self):
        """Origin changes the built page `docs/p.md` and the file `a`; here `p.md`, `a` (other lines) and `b` are
        staged, `b` is edited again unstaged on another line, and `c` is edited unstaged."""
        lines = "".join(f"{number}\n" for number in range(1, 8))
        for name in ("docs/p.md", "a", "b", "c"):
            self.write(self.repo, name, lines)
        self.git(self.repo, "add", "docs/p.md", "a", "b", "c")
        self.git(self.repo, "commit", "-qm", "incident files")
        self.git(self.repo, "push", "-q")
        self.mark_built_pages("docs/p.md")
        self.push_files_from_other_machine({"docs/p.md": "theirs\n", "a": lines.replace("1\n", "one\n", 1)})
        self.write(self.repo, "docs/p.md", "mine\n")
        self.write(self.repo, "a", lines.replace("7\n", "seven\n"))
        self.write(self.repo, "b", lines.replace("1\n", "staged b\n", 1))
        self.git(self.repo, "add", "docs/p.md", "a", "b")
        self.write(self.repo, "b", lines.replace("1\n", "staged b\n", 1).replace("7\n", "unstaged b\n"))
        self.write(self.repo, "c", "unstaged c\n")
        return lines

    def assert_the_incident_is_back(self, lines):
        self.assertEqual(sorted(self.status()), [" M c", "M  a", "M  docs/p.md", "MM b"])
        both_sides = lines.replace("1\n", "one\n", 1).replace("7\n", "seven\n")
        self.assertEqual(self.git(self.repo, "show", ":a"), both_sides)
        self.assertEqual(self.git(self.repo, "show", ":b"), lines.replace("1\n", "staged b\n", 1))
        self.assertEqual((self.repo / "b").read_text(),
                         lines.replace("1\n", "staged b\n", 1).replace("7\n", "unstaged b\n"))
        self.assertEqual(self.git(self.repo, "show", ":docs/p.md"), "rebuilt\n")
        self.assertEqual((self.repo / "docs/p.md").read_text(), "rebuilt\n")
        self.assertEqual((self.repo / "c").read_text(), "unstaged c\n")
        self.assertEqual(self.kept_refs(), [])

    def test_the_incident_state_ends_with_every_local_change_back_staged_files_staged_and_the_page_rebuilt(self):
        lines = self.set_up_the_incident()

        finished = self.run_script()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assert_the_incident_is_back(lines)

    def run_script_in_subfolder(self, *arguments):
        env = {**os.environ, **GIT_ENV}
        return subprocess.run([sys.executable, str(SCRIPT), *arguments, str(self.repo / "docs")],
                              capture_output=True, text=True, env=env)

    def use_a_recording_driver(self):
        """Configure a built-page driver that records what it was given and rebuilds the page; return the record."""
        record = self.tmp / "driver_args.json"
        driver = self.tmp / "recording_driver.py"
        driver.write_text(
            "import json, os, pathlib, sys\n"
            "base, ours, theirs, page, marker_size = sys.argv[1:6]\n"
            "read = lambda name: pathlib.Path(name).read_text()\n"
            "pathlib.Path(sys.argv[6]).write_text(json.dumps({'base': read(base), 'ours': read(ours),\n"
            "    'theirs': read(theirs), 'page': page, 'marker_size': marker_size,\n"
            "    'stash': os.environ['BUILT_PAGE_STASH'], 'cwd': os.getcwd()}))\n"
            "pathlib.Path(ours).write_text('rebuilt\\n')\n")
        self.git(self.repo, "config", "merge.built-page.driver",
                 f"{sys.executable} {driver} %O %A %B %P %L {record}")
        return record

    def test_the_incident_state_is_put_back_in_full_when_the_argument_is_a_subfolder(self):
        lines = self.set_up_the_incident()

        finished = self.run_script_in_subfolder()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assert_the_incident_is_back(lines)

    def test_the_page_driver_gets_base_ours_theirs_and_the_saved_commit_in_the_top_folder(self):
        lines = self.set_up_the_incident()
        record = self.use_a_recording_driver()
        head_before_pull = self.git(self.repo, "rev-parse", "HEAD").strip()

        finished = self.run_script()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        seen = json.loads(record.read_text())
        self.assertEqual(seen["base"], lines)
        self.assertEqual(seen["ours"], "theirs\n")
        self.assertEqual(seen["theirs"], "mine\n")
        self.assertEqual(seen["page"], "docs/p.md")
        self.assertEqual(os.path.realpath(seen["cwd"]), os.path.realpath(self.repo))
        saved = seen["stash"]
        self.assertEqual(self.git(self.repo, "rev-parse", saved + "^1").strip(), head_before_pull)
        self.assertEqual(self.git(self.repo, "show", saved + ":docs/p.md"), "mine\n")
        self.assertEqual(self.git(self.repo, "show", saved + ":c"), "unstaged c\n")

    def test_the_page_driver_gets_gits_default_conflict_marker_size_for_percent_l(self):
        self.set_up_the_incident()
        record = self.use_a_recording_driver()

        finished = self.run_script()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(json.loads(record.read_text())["marker_size"], "7")

    def test_a_page_missing_from_the_base_reaches_the_driver_as_an_empty_base(self):
        self.mark_built_pages("docs/n.md")
        self.push_files_from_other_machine({"docs/n.md": "theirs\n"})
        self.write(self.repo, "docs/n.md", "mine\n")
        self.git(self.repo, "add", "docs/n.md")
        record = self.use_a_recording_driver()

        finished = self.run_script()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        seen = json.loads(record.read_text())
        self.assertEqual(seen["base"], "")
        self.assertEqual(seen["ours"], "theirs\n")
        self.assertEqual(seen["theirs"], "mine\n")
        self.assertEqual(self.status(), ["M  docs/n.md"])
        self.assertEqual(self.git(self.repo, "show", ":docs/n.md"), "rebuilt\n")

    def test_put_back_run_from_a_subfolder_puts_the_incident_state_back_in_full(self):
        lines = self.set_up_the_incident()
        saved = self.git(self.repo, "stash", "create").strip()
        self.git(self.repo, "reset", "-q", "--hard")
        self.git(self.repo, "update-ref", REF, saved)
        self.git(self.repo, "pull", "-q", "--rebase")

        finished = self.run_script_in_subfolder("--put-back", REF)

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assert_the_incident_is_back(lines)

    def test_put_back_of_the_incident_state_does_the_same_on_a_clean_tree(self):
        lines = self.set_up_the_incident()
        saved = self.git(self.repo, "stash", "create").strip()
        self.git(self.repo, "reset", "-q", "--hard")
        self.git(self.repo, "update-ref", REF, saved)
        self.git(self.repo, "pull", "-q", "--rebase")

        finished = self.run_script("--put-back", REF)

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assert_the_incident_is_back(lines)

    def test_a_built_page_named_with_glob_characters_is_rebuilt_and_a_lookalike_file_keeps_its_staged_text(self):
        self.add_files("p[1]", "p1")
        self.mark_built_pages("p\\[1]")
        self.push_from_other_machine("p[1]", "theirs\n")
        self.write(self.repo, "p[1]", "mine\n")
        self.git(self.repo, "add", "p[1]")
        self.write(self.repo, "p1", "staged\n")
        self.git(self.repo, "add", "p1")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(self.git(self.repo, "show", ":p[1]"), "rebuilt\n")
        self.assertEqual(self.git(self.repo, "show", ":p1"), "staged\n")

    def test_a_recovery_command_for_a_repo_path_with_a_space_parses_back_to_that_path(self):
        spaced = self.tmp / "my repo"
        shutil.move(str(self.repo), str(spaced))
        self.repo = spaced
        self.push_from_other_machine("f", "theirs\n")
        self.write(self.repo, "f", "mine\n")
        self.git(self.repo, "add", "f")

        finished = self.run_script()

        self.assertNotEqual(finished.returncode, 0)
        command = finished.stderr.split("on a clean tree, run: ")[1].split("\n")[0]
        self.assertEqual(shlex.split(command)[-1], str(spaced))

    def test_a_staged_clash_only_on_built_pages_is_rebuilt_and_the_split_kept(self):
        self.add_files("k")
        self.mark_built_pages("f")
        self.push_from_other_machine("f", "theirs\n")
        self.write(self.repo, "f", "mine\n")
        self.git(self.repo, "add", "f")
        self.write(self.repo, "k", "staged\n")
        self.git(self.repo, "add", "k")
        self.write(self.repo, "g", "unstaged\n")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(sorted(self.status()), [" M g", "M  f", "M  k"])
        self.assertEqual(self.git(self.repo, "show", ":f"), "rebuilt\n")
        self.assertEqual((self.repo / "f").read_text(), "rebuilt\n")
        self.assertEqual(self.git(self.repo, "show", ":k"), "staged\n")
        self.assertEqual(self.kept_refs(), [])

    def test_built_page_attributes_with_no_driver_configured_stop_with_the_put_back_command(self):
        # Git text-merges a page whose attribute names an unconfigured driver; never stage that text as rebuilt.
        self.mark_built_pages("f")
        self.git(self.repo, "config", "--unset", "merge.built-page.driver")
        self.push_from_other_machine("f", "theirs\n")
        self.write(self.repo, "f", "mine\n")
        self.git(self.repo, "add", "f")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 1, finished.stderr)
        self.assertIn("--put-back ", finished.stderr)
        self.assertNotIn("--literal-pathspecs add", finished.stderr)
        self.assertEqual(self.status(), [])
        self.assertEqual((self.repo / "f").read_text(), "theirs\n")

    def test_a_put_back_of_a_commit_that_is_not_saved_changes_exits_with_the_usage(self):
        head = self.git(self.repo, "rev-parse", "HEAD").strip()

        finished = self.run_script("--put-back", head)

        self.assertEqual(finished.returncode, 1, finished.stderr)
        self.assertIn(f"pull_keep_index: {head} is not a saved-changes commit", finished.stderr)
        self.assertIn("Usage: pull_keep_index.py <repo>", finished.stderr)

    def test_a_put_back_into_a_repo_with_tracked_changes_exits_with_the_usage(self):
        self.write(self.repo, "f", "staged\n")
        self.git(self.repo, "add", "f")
        saved = self.git(self.repo, "stash", "create").strip()
        self.git(self.repo, "reset", "-q", "--hard")
        self.write(self.repo, "g", "dirty\n")

        finished = self.run_script("--put-back", saved)

        self.assertEqual(finished.returncode, 1, finished.stderr)
        self.assertIn("Usage: pull_keep_index.py <repo>", finished.stderr)
        self.assertEqual(self.status(), [" M g"])
        self.assertIn(f"saved in {saved} (ref refs/pull-keep-index/", finished.stderr)
        self.assertEqual([saved_hash for _name, saved_hash in self.kept_refs()], [saved])

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

    def test_a_conflicting_re_apply_with_nothing_staged_leaves_the_other_files_unstaged(self):
        self.add_files("k", "m")
        self.push_from_other_machine("f", "theirs\n")
        self.write(self.repo, "f", "mine\n")
        self.write(self.repo, "k", "unstaged\n")
        self.write(self.repo, "m", "unstaged\n")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 1, finished.stderr)
        self.assertEqual(sorted(self.status()), [" M k", " M m", "UU f"])
        self.assertIn("conflict with the pull in: f.", finished.stderr)

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

    def test_a_folder_that_is_not_a_repo_exits_1_saying_it_is_not_a_git_repository(self):
        not_a_repo = self.tmp / "plain"
        not_a_repo.mkdir()
        env = {**os.environ, **GIT_ENV, "GIT_CEILING_DIRECTORIES": str(self.tmp)}

        finished = subprocess.run([sys.executable, str(SCRIPT), str(not_a_repo)], capture_output=True, text=True,
                                  env=env)

        self.assertEqual(finished.returncode, 1)
        self.assertIn(f"{not_a_repo} is not a git repository", finished.stderr)

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

    def test_a_pushed_branch_with_the_integration_branch_merged_in_pulls_nothing_and_keeps_its_hashes(self):
        self.git(self.repo, "checkout", "-q", "-b", "feature")
        self.commit_local("k", "1\n")
        self.git(self.repo, "push", "-q", "-u", "origin", "feature")
        self.push_from_other_machine("h", "2\n")
        self.git(self.repo, "fetch", "-q")
        self.git(self.repo, "merge", "-q", "--no-edit", "origin/master")
        self.write(self.repo, "f", "staged\n")
        self.git(self.repo, "add", "f")
        head = self.git(self.repo, "rev-parse", "HEAD")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertIn("already holds the upstream tip", finished.stdout)
        self.assertNotIn("force-with-lease", finished.stdout)
        self.assertEqual(self.git(self.repo, "rev-parse", "HEAD"), head)
        self.assertEqual(self.status(), ["M  f"])

    def test_a_run_that_pulls_nothing_still_moves_the_remote_tracking_ref_to_the_fetched_tip(self):
        stale_tip = self.git(self.repo, "rev-parse", "origin/master").strip()
        self.push_from_other_machine("h", "2\n")
        self.git(self.repo, "fetch", "-q", "origin", "master:refs/heads/held")
        self.git(self.repo, "merge", "-q", "--ff-only", "held")
        self.git(self.repo, "update-ref", "refs/remotes/origin/master", stale_tip)

        finished = self.run_script()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertIn("already holds the upstream tip", finished.stdout)
        self.assertEqual(self.git(self.repo, "rev-parse", "@{u}").strip(), self.head())

    def test_a_fully_synced_branch_pulls_nothing_and_keeps_a_staged_file_staged(self):
        self.git(self.repo, "checkout", "-q", "-b", "feature")
        self.git(self.repo, "push", "-q", "-u", "origin", "feature")
        self.write(self.repo, "f", "staged\n")
        self.git(self.repo, "add", "f")
        head = self.git(self.repo, "rev-parse", "HEAD")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertIn("already holds the upstream tip", finished.stdout)
        self.assertEqual(self.git(self.repo, "rev-parse", "HEAD"), head)
        self.assertEqual(self.status(), ["M  f"])

    def test_a_branch_behind_its_upstream_still_pulls_and_keeps_a_staged_file_staged(self):
        self.git(self.repo, "checkout", "-q", "-b", "feature")
        self.git(self.repo, "push", "-q", "-u", "origin", "feature")
        other = self.clone("other-feature")
        self.git(other, "checkout", "-q", "feature")
        self.write(other, "h", "2\n")
        self.git(other, "add", "h")
        self.git(other, "commit", "-qm", "other h")
        self.git(other, "push", "-q", "origin", "feature")
        self.write(self.repo, "f", "staged\n")
        self.git(self.repo, "add", "f")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertNotIn("already holds", finished.stdout)
        self.assertEqual((self.repo / "h").read_text(), "2\n")
        self.assertEqual(self.status(), ["M  f"])

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
        self.assertIn("--put-back ", finished.stderr)
        saved = finished.stderr.split("--put-back ")[1].split()[0]
        self.assertEqual(self.git(self.repo, "show", saved + ":g"), "unstaged\n")

    def share_the_checkout_with_a_dirty_file(self):
        """Commit `bin/x`, give it an unstaged line `local-edit`, and register another session in the repo."""
        self.add_files("bin/x")
        self.write(self.repo, "bin/x", "1\nlocal-edit\n")
        self.register_other(self.repo)

    def head(self):
        return self.git(self.repo, "rev-parse", "HEAD").strip()

    def test_a_shared_pull_keeps_the_other_sessions_edit_in_the_tree_for_the_whole_pull(self):
        self.share_the_checkout_with_a_dirty_file()
        self.push_from_other_machine("h", "2\n")
        log = self.tmp / "hook.log"
        hook = self.repo / ".git" / "hooks" / "reference-transaction"
        hook.write_text("#!/bin/sh\n[ \"$1\" = committed ] || exit 0\n"
                        "while read old new ref; do\n"
                        "  case \"$ref\" in refs/heads/*)\n"
                        f"    if grep -q local-edit bin/x; then echo kept=1 >> {shlex.quote(str(log))};\n"
                        f"    else echo kept=0 >> {shlex.quote(str(log))}; fi\n"
                        "    echo writer >> bin/x ;;\n"
                        "  esac\n"
                        "done\n")
        hook.chmod(0o755)

        finished = self.run_script()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        lines = log.read_text().splitlines()
        self.assertTrue(lines)
        self.assertEqual(set(lines), {"kept=1"})
        self.assertEqual((self.repo / "bin" / "x").read_text(), "1\nlocal-edit\nwriter\n")
        self.assertEqual(self.kept_refs(), [])
        self.assertEqual(self.git(self.repo, "for-each-ref", "refs/pull-keep-index-fetch"), "")
        self.assertEqual(self.head(), self.git(self.remote, "rev-parse", "master").strip())

    def test_a_shared_pull_fetches_the_upstream_once(self):
        self.share_the_checkout_with_a_dirty_file()
        self.push_from_other_machine("h", "2\n")
        trace = self.tmp / "git-trace.log"
        env = {**os.environ, **GIT_ENV, "GIT_TRACE": str(trace)}

        finished = subprocess.run([sys.executable, str(SCRIPT), str(self.repo)], capture_output=True, text=True,
                                  env=env)

        self.assertEqual(finished.returncode, 0, finished.stderr)
        fetches = [line for line in trace.read_text().splitlines() if "built-in: git fetch" in line]
        self.assertEqual(len(fetches), 1, fetches)
        self.assertEqual(self.head(), self.git(self.remote, "rev-parse", "master").strip())

    def test_a_shared_pull_that_would_overwrite_a_dirty_file_refuses_and_sets_nothing_aside(self):
        self.share_the_checkout_with_a_dirty_file()
        self.push_from_other_machine("bin/x", "theirs\n")
        head = self.head()

        finished = self.run_script()

        self.assertEqual(finished.returncode, 1, finished.stderr)
        self.assertIn("bin/x", finished.stderr)
        self.assertIn("Nothing was set aside", finished.stderr)
        self.assertEqual(self.head(), head)
        self.assertEqual((self.repo / "bin" / "x").read_text(), "1\nlocal-edit\n")
        self.assertEqual(self.kept_refs(), [])

    def test_a_shared_dirty_diverged_branch_is_refused_naming_the_dirty_files(self):
        self.share_the_checkout_with_a_dirty_file()
        self.commit_local("k", "1\n")
        self.push_from_other_machine("h", "2\n")
        head = self.head()

        finished = self.run_script()

        self.assertEqual(finished.returncode, 1, finished.stderr)
        self.assertIn("Dirty files: bin/x", finished.stderr)
        self.assertIn("nothing pulled or set aside", finished.stderr)
        self.assertEqual(self.head(), head)
        self.assertEqual((self.repo / "bin" / "x").read_text(), "1\nlocal-edit\n")
        self.assertEqual(self.kept_refs(), [])

    def share_the_checkout_with_a_dirty_built_page(self, *dirty_sources):
        """Mark `QUEUE.md` a built page, give it and each of `dirty_sources` an unstaged edit, register another
        session, and diverge the branch from a remote that also changed the page."""
        self.mark_built_pages("QUEUE.md")
        self.add_files("QUEUE.md", *dirty_sources)
        self.write(self.repo, "QUEUE.md", "1\npeer-build\n")
        for name in dirty_sources:
            self.write(self.repo, name, "1\nlocal-edit\n")
        self.register_other(self.repo)
        self.commit_local("k", "1\n")
        self.push_files_from_other_machine({"QUEUE.md": "remote-build\n", "h": "2\n"})

    def test_a_peer_dirty_built_page_alone_is_pulled_and_rebuilt(self):
        self.share_the_checkout_with_a_dirty_built_page()
        remote_tip = self.git(self.remote, "rev-parse", "master").strip()

        finished = self.run_script()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.git(self.repo, "merge-base", "--is-ancestor", remote_tip, "HEAD")
        self.assertEqual((self.repo / "k").read_text(), "1\n")
        self.assertEqual((self.repo / "QUEUE.md").read_text(), "rebuilt\n")
        self.assertEqual(self.kept_refs(), [])

    def test_a_peer_dirty_source_file_beside_a_built_page_is_still_refused(self):
        self.share_the_checkout_with_a_dirty_built_page("bin/x")
        head = self.head()

        finished = self.run_script()

        self.assertEqual(finished.returncode, 1, finished.stderr)
        self.assertIn("Dirty files: QUEUE.md bin/x", finished.stderr)
        self.assertEqual(self.head(), head)
        self.assertEqual((self.repo / "bin" / "x").read_text(), "1\nlocal-edit\n")
        self.assertEqual((self.repo / "QUEUE.md").read_text(), "1\npeer-build\n")
        self.assertEqual(self.kept_refs(), [])

    def test_a_peer_dirty_built_page_with_no_driver_configured_is_still_refused(self):
        self.share_the_checkout_with_a_dirty_built_page()
        self.git(self.repo, "config", "--unset", "merge.built-page.driver")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 1, finished.stderr)
        self.assertIn("Dirty files: QUEUE.md", finished.stderr)
        self.assertEqual((self.repo / "QUEUE.md").read_text(), "1\npeer-build\n")

    def test_a_missing_session_id_reads_the_callers_own_row_as_another_session(self):
        self.add_files("bin/x")
        self.write(self.repo, "bin/x", "1\nlocal-edit\n")
        self.register_other(self.repo, session_id="self-id")
        self.commit_local("k", "1\n")
        self.push_from_other_machine("h", "2\n")
        del os.environ["CLAUDE_CODE_SESSION_ID"]

        finished = self.run_script()

        self.assertEqual(finished.returncode, 1, finished.stderr)
        self.assertIn("also works in", finished.stderr)

    def test_a_shared_clean_tree_with_another_session_keeps_the_solo_rebase(self):
        self.register_other(self.repo)
        self.commit_local("k", "1\n")
        self.push_from_other_machine("h", "2\n")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual((self.repo / "h").read_text(), "2\n")
        self.assertEqual(self.git(self.repo, "log", "-1", "--format=%s").strip(), "local k")
        self.assertEqual(self.git(self.repo, "log", "-1", "--format=%s", "HEAD~1").strip(), "other h")

    def test_a_row_with_the_callers_own_session_id_keeps_the_run_solo(self):
        self.add_files("bin/x")
        self.write(self.repo, "bin/x", "1\nlocal-edit\n")
        self.register_other(self.repo, session_id="self-id")
        self.commit_local("k", "1\n")
        self.push_from_other_machine("h", "2\n")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(self.git(self.repo, "log", "-1", "--format=%s", "HEAD~1").strip(), "other h")
        self.assertEqual((self.repo / "bin" / "x").read_text(), "1\nlocal-edit\n")

    def test_a_shared_pull_with_nothing_new_says_already_holds_and_still_sets_the_upstream(self):
        self.add_files("bin/x")
        self.git(self.repo, "checkout", "-q", "-b", "shared")
        self.git(self.repo, "push", "-q", "origin", "shared")
        self.write(self.repo, "bin/x", "1\nlocal-edit\n")
        self.register_other(self.repo)

        finished = self.run_script()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertIn("already holds", finished.stdout)
        self.assertEqual((self.repo / "bin" / "x").read_text(), "1\nlocal-edit\n")
        self.assertEqual(self.git(self.repo, "config", "--get", "branch.shared.merge").strip(), "refs/heads/shared")

    def test_a_shared_pull_on_a_detached_head_exits_1_and_sets_nothing_aside(self):
        self.share_the_checkout_with_a_dirty_file()
        self.git(self.repo, "checkout", "-q", "--detach")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 1, finished.stderr)
        self.assertIn("detached HEAD", finished.stderr)
        self.assertEqual(self.kept_refs(), [])

    def test_a_shared_pull_whose_fetch_fails_exits_1_naming_the_fetch(self):
        self.share_the_checkout_with_a_dirty_file()
        self.git(self.repo, "remote", "set-url", "origin", str(self.tmp / "missing.git"))

        finished = self.run_script()

        self.assertEqual(finished.returncode, 1, finished.stderr)
        self.assertIn("git fetch origin", finished.stderr)
        self.assertEqual((self.repo / "bin" / "x").read_text(), "1\nlocal-edit\n")

    def test_a_shared_pull_from_a_remote_that_cannot_name_a_fetch_ref_exits_1(self):
        self.share_the_checkout_with_a_dirty_file()
        self.git(self.repo, "config", "branch.master.remote", str(self.remote))

        finished = self.run_script()

        self.assertEqual(finished.returncode, 1, finished.stderr)
        self.assertIn("cannot name a fetch ref", finished.stderr)

    def test_a_shared_pull_whose_merge_fails_exits_1_with_git_stderr_and_sets_nothing_aside(self):
        self.share_the_checkout_with_a_dirty_file()
        self.push_from_other_machine("h", "2\n")
        hook = self.repo / ".git" / "hooks" / "reference-transaction"
        hook.write_text("#!/bin/sh\n[ \"$1\" = prepared ] || exit 0\n"
                        "while read old new ref; do\n"
                        "  case \"$ref\" in refs/heads/*) echo hook-refused >&2; exit 1 ;; esac\n"
                        "done\n")
        hook.chmod(0o755)
        head = self.head()

        finished = self.run_script()

        self.assertEqual(finished.returncode, 1, finished.stderr)
        self.assertIn("git merge --ff-only failed", finished.stderr)
        self.assertIn("hook-refused", finished.stderr)
        self.assertIn("Nothing was set aside", finished.stderr)
        self.assertEqual(self.head(), head)
        self.assertEqual(self.kept_refs(), [])

    def test_a_targeted_first_pull_on_the_shared_route_sets_the_upstream(self):
        self.add_files("bin/x")
        self.git(self.repo, "checkout", "-q", "-b", "shared")
        self.git(self.repo, "push", "-q", "origin", "shared")
        other = self.clone("other-shared")
        self.git(other, "checkout", "-q", "shared")
        self.write(other, "h", "2\n")
        self.git(other, "add", "h")
        self.git(other, "commit", "-qm", "other h")
        self.git(other, "push", "-q", "origin", "shared")
        self.write(self.repo, "bin/x", "1\nlocal-edit\n")
        self.register_other(self.repo)

        finished = self.run_script()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual((self.repo / "h").read_text(), "2\n")
        self.assertEqual(self.git(self.repo, "config", "--get", "branch.shared.remote").strip(), "origin")
        self.assertEqual(self.git(self.repo, "config", "--get", "branch.shared.merge").strip(), "refs/heads/shared")
        self.assertEqual((self.repo / "bin" / "x").read_text(), "1\nlocal-edit\n")

    def test_a_single_branch_clone_without_a_resolving_upstream_fast_forwards_on_the_shared_route(self):
        self.add_files("bin/x")
        self.git(self.repo, "push", "-q", "origin", "HEAD:refs/heads/solo")
        single = self.tmp / "single"
        self.git(self.tmp, "clone", "-q", "--single-branch", "-b", "master", str(self.remote), str(single))
        self.git(single, "fetch", "-q", "origin", "solo")
        self.git(single, "checkout", "-q", "-b", "solo", "FETCH_HEAD")
        self.git(single, "config", "branch.solo.remote", "origin")
        self.git(single, "config", "branch.solo.merge", "refs/heads/solo")
        other = self.clone("other-solo")
        self.git(other, "fetch", "-q", "origin", "solo")
        self.git(other, "checkout", "-q", "-b", "solo", "FETCH_HEAD")
        self.write(other, "h", "2\n")
        self.git(other, "add", "h")
        self.git(other, "commit", "-qm", "other h")
        self.git(other, "push", "-q", "origin", "solo")
        self.write(single, "bin/x", "1\nlocal-edit\n")
        self.repo = single
        self.register_other(single)
        self.assertEqual(self.git(single, "branch", "-r", "--list", "origin/solo"), "")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual((single / "h").read_text(), "2\n")
        self.assertEqual((single / "bin" / "x").read_text(), "1\nlocal-edit\n")
        self.assertEqual(self.kept_refs(), [])

    def hold_the_lock(self):
        """Start a child that holds the repo's lock until cleanup kills it; return the lock path."""
        common_dir = pathlib.Path(self.git(self.repo, "rev-parse", "--path-format=absolute",
                                           "--git-common-dir").strip())
        lock = common_dir / "pull-keep-index.lock"
        holder_code = textwrap.dedent(f"""
            import sys, time
            sys.path.insert(0, {str(LIB_DIR)!r})
            import file_lock
            with file_lock.hold_exclusive({str(lock)!r}, 5):
                print("held", flush=True)
                time.sleep(600)
        """)
        holder = subprocess.Popen([sys.executable, "-c", holder_code], stdout=subprocess.PIPE, text=True)
        self.addCleanup(holder.wait)
        self.addCleanup(holder.kill)
        self.assertEqual(holder.stdout.readline().strip(), "held")
        return lock

    def test_a_run_and_a_put_back_wait_for_the_lock_then_exit_1_naming_it(self):
        lock = self.hold_the_lock()
        saved = self.make_saved_commit("g", "unstaged\n")
        self.push_from_other_machine("h", "2\n")
        self.write(self.repo, "f", "staged\n")
        os.environ["PULL_KEEP_INDEX_LOCK_SECONDS"] = "1"

        for arguments in ((), ("--put-back", saved)):
            finished = self.run_script(*arguments)

            self.assertEqual(finished.returncode, 1, finished.stderr)
            self.assertIn(f"another run holds {lock}", finished.stderr)
            self.assertEqual(self.status(), [" M f"], arguments)
            self.assertFalse((self.repo / "h").exists(), arguments)

    def test_a_lock_wait_that_is_not_a_positive_integer_exits_1_naming_the_variable(self):
        for value in ("x", "0", "-3", "1.5"):
            os.environ["PULL_KEEP_INDEX_LOCK_SECONDS"] = value

            finished = self.run_script()

            self.assertEqual(finished.returncode, 1, value)
            self.assertIn("PULL_KEEP_INDEX_LOCK_SECONDS", finished.stderr, value)


class PrintedCommandQuotingTest(unittest.TestCase):
    """Every command the script prints for the user must survive a repo path or remote with a space."""

    @classmethod
    def setUpClass(cls):
        cls.script_dir = str(SCRIPT.parent)
        sys.path[:0] = [cls.script_dir]
        import pull_keep_index
        cls.module = pull_keep_index

    @classmethod
    def tearDownClass(cls):
        sys.path.remove(cls.script_dir)

    def test_upstream_gone_quotes_repo_and_remote(self):
        with self.assertRaises(SystemExit) as stopped:
            self.module.exit_upstream_gone("/a b", "main", "refs/heads/main", "my remote")
        message = str(stopped.exception)
        self.assertIn("git -C '/a b' branch --unset-upstream", message)
        self.assertIn("git -C '/a b' push -u 'my remote' HEAD", message)

    def test_merge_abort_quotes_repo(self):
        found = subprocess.CompletedProcess([], 0)
        with unittest.mock.patch.object(self.module, "run_in_repo", return_value=found):
            text = self.module.merge_abort_text("/a b")
        self.assertIn("git -C '/a b' merge --abort", text)

    def test_stopped_rebase_quotes_repo(self):
        with (
            tempfile.TemporaryDirectory() as state_dir,
            unittest.mock.patch.object(self.module, "listed_paths", return_value=[]),
        ):
            text = self.module.stopped_rebase_text("/a b", state_dir)
        self.assertIn("git -C '/a b' rebase --continue", text)
        self.assertIn("git -C '/a b' rebase --abort", text)

    def test_set_upstream_failure_quotes_every_word(self):
        failed = subprocess.CompletedProcess([], 1, stdout=b"", stderr=b"no")
        with (
            unittest.mock.patch.object(self.module, "run_in_repo", return_value=failed),
            self.assertRaises(SystemExit) as stopped,
        ):
            self.module.set_upstream("/a b", "my remote", "main")
        self.assertIn("git -C '/a b' config branch.main.remote 'my remote'", str(stopped.exception))

    def test_failed_staging_of_rebuilt_pages_names_the_add_command_and_the_saved_commit(self):
        repo = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        env = {**os.environ, **GIT_ENV}
        (repo / "f").write_text("1\n")
        for arguments in (("init", "-q"), ("add", "f"), ("commit", "-qm", "one")):
            subprocess.run(["git", "-C", str(repo), *arguments], check=True, capture_output=True, env=env)
        (repo / "f").write_text("changed\n")
        subprocess.run(["git", "-C", str(repo), "add", "f"], check=True, capture_output=True, env=env)
        saved = subprocess.run(["git", "-C", str(repo), "stash", "create"], check=True, capture_output=True,
                               text=True, env=env).stdout.strip()
        subprocess.run(["git", "-C", str(repo), "reset", "--hard", "--quiet"], check=True, capture_output=True,
                       env=env)
        driver = repo / "driver.py"
        driver.write_text("import pathlib, sys\npathlib.Path(sys.argv[1]).write_text('rebuilt\\n')\n")
        subprocess.run(["git", "-C", str(repo), "config", "merge.built-page.driver", f"{sys.executable} {driver} %A"],
                       check=True, capture_output=True, env=env)
        real_run_in_repo = self.module.run_in_repo

        def fail_the_add(repo_path, *arguments, **options):
            if arguments[:2] == ("--literal-pathspecs", "add"):
                return subprocess.CompletedProcess([], 1, stdout=b"", stderr=b"index is locked")
            return real_run_in_repo(repo_path, *arguments, **options)

        with (
            unittest.mock.patch.object(self.module, "run_in_repo", side_effect=fail_the_add),
            self.assertRaises(SystemExit) as stopped,
        ):
            template = f"{sys.executable} {driver} %A"
            self.module.put_back_by_hand(str(repo), self.module.Saved(saved, REF), ["f"], template)

        message = str(stopped.exception)
        self.assertIn("could not stage the rebuilt pages: index is locked", message)
        self.assertIn(f"git -C {repo} --literal-pathspecs add -- f", message)
        self.assertNotIn("--put-back", message)
        self.assertIn(f"The local changes are saved in {saved} (ref {REF}).", message)


if __name__ == "__main__":
    unittest.main()
