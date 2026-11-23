"""Checks for mutation_lock.py at its public boundary: argv in, output and exit code out, with a temp HOME, state
folder and git repo."""
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import shlex
import subprocess
import sys
import tempfile
import time
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import script_utils

SCRIPT = pathlib.Path(os.environ.get("MUTATION_LOCK_PATH") or toolkit_paths.TOOLS_DIR / "mutation_lock.py")
GUARD = toolkit_paths.GATES_DIR / "calibration_guard.py"
STAMP_FORM = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
DEAD_PID = 99999999
MUTATION_TESTER_PROMPTS = (
    toolkit_paths.CLAUDE_DIR / "agents" / "mutation-tester.md",
    toolkit_paths.REPO_ROOT / "opencode" / ".config" / "opencode" / "agents" / "mutation-tester.md",
)

spec = importlib.util.spec_from_file_location("mutation_lock_under_test", str(SCRIPT))
mutation_lock = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mutation_lock)


def sha16(data):
    return hashlib.sha256(data).hexdigest()[:16]


def now_stamp():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class MutationLockTest(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.root = pathlib.Path(temp_dir.name).resolve()
        self.home = self.root / "home"
        self.state = self.root / "state" / "claude-calibration"
        self.home.mkdir()
        self.env = {**os.environ, "HOME": str(self.home), "XDG_STATE_HOME": str(self.root / "state")}
        self.repo = self.root / "repo"
        (self.repo / "src").mkdir(parents=True)
        self.target = self.repo / "src" / "a.py"
        self.original = b"x = 1\ny = 2\n"
        self.target.write_bytes(self.original)
        self.git("init", "-q")
        self.git("add", "src/a.py")
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", "commit", "-q", "-m", "a")
        self.lock_file = self.state / "lock.json"
        self.backup_file = self.state / "backups" / "src" / "a.py"

    def git(self, *args):
        finished = subprocess.run(["git", "-C", str(self.repo), *args], capture_output=True, text=True, check=True)
        return finished.stdout

    def run_script(self, *args, script=SCRIPT):
        return subprocess.run([sys.executable, str(script), *map(str, args)], capture_output=True, text=True,
                              env=self.env, cwd=str(self.root), check=False)

    def lock_args(self, target=None, pid=None):
        return ["lock", target or self.target, "--class", "off-by-one", "--line", "2",
                "--owner-pid", pid or os.getpid()]

    def make_lock(self, **overrides):
        fields = {"ts": now_stamp(), "kind": "mutation-test", "writer": "mutation-tester", "file": "src/a.py",
                  "backup_path": str(self.backup_file), "pre_hash": sha16(self.original),
                  "class": "mutant: x", "line": "1", "worktree": str(self.repo), "owner_pid": os.getpid()}
        fields.update(overrides)
        self.state.mkdir(parents=True, exist_ok=True)
        self.lock_file.write_text(json.dumps(fields, indent=2) + "\n")

    def make_backup(self, data=None):
        self.backup_file.parent.mkdir(parents=True, exist_ok=True)
        self.backup_file.write_bytes(self.original if data is None else data)

    def locked_run(self):
        """A real `lock` call owned by this test process."""
        finished = self.run_script(*self.lock_args())
        self.assertEqual(finished.returncode, 0, finished.stdout + finished.stderr)

    def assert_ends_with(self, finished, prefix, constant=None):
        last = finished.stdout.rstrip("\n").splitlines()[-1]
        self.assertTrue(last.startswith(prefix), finished.stdout)
        if constant is not None:
            self.assertEqual(last, constant)

    def assert_stop(self, finished, constant):
        self.assertEqual(finished.returncode, mutation_lock.EXIT_STOP, finished.stdout + finished.stderr)
        self.assert_ends_with(finished, "STOP:", constant)

    def assert_nothing_written(self):
        self.assertFalse(self.backup_file.exists())
        self.assertFalse((self.state / "backups").exists())

    def test_check_on_a_clean_file_names_the_next_step_and_writes_nothing(self):
        finished = self.run_script("check", self.target)

        self.assertEqual(finished.returncode, 0, finished.stdout + finished.stderr)
        self.assert_ends_with(finished, "NEXT:")
        self.assertNotIn("NOTE:", finished.stdout)
        self.assertFalse(self.lock_file.exists())
        self.assertFalse(self.state.exists())

    def test_check_stops_on_a_target_that_cannot_be_locked(self):
        link = self.repo / "src" / "link.py"
        link.symlink_to(self.target)
        outside = self.root / "elsewhere"
        outside.mkdir()
        (outside / "b.py").write_text("z = 1\n")
        cases = {
            "missing file": (self.repo / "src" / "gone.py", mutation_lock.STOP_NOT_A_FILE),
            "symlink": (link, mutation_lock.STOP_NOT_A_FILE),
            "folder outside any repo": (outside / "b.py", mutation_lock.STOP_NOT_A_REPO),
            "path under .git": (self.repo / ".git" / "config", mutation_lock.STOP_OUTSIDE_TREE),
        }
        for name, (target, constant) in cases.items():
            with self.subTest(name):
                self.assert_stop(self.run_script("check", target), constant)
                self.assertFalse(self.state.exists())

    def test_check_stops_on_a_live_lock_and_leaves_it_alone(self):
        self.make_lock()
        before = self.lock_file.read_bytes()

        finished = self.run_script("check", self.target)

        self.assert_stop(finished, mutation_lock.STOP_LIVE_LOCK)
        self.assertEqual(self.lock_file.read_bytes(), before)

    def test_check_on_a_stale_or_legacy_lock_shows_the_file_and_backup_and_keeps_the_lock(self):
        self.make_lock(owner_pid=DEAD_PID)
        stale_bytes = self.lock_file.read_bytes()
        stale = self.run_script("check", self.target)
        self.lock_file.unlink()

        legacy_file = self.home / ".claude" / "calibration-lock.json"
        legacy_file.parent.mkdir()
        legacy_file.write_bytes(stale_bytes)
        legacy = self.run_script("check", self.target)

        for name, finished in (("stale", stale), ("legacy", legacy)):
            with self.subTest(name):
                self.assert_stop(finished, mutation_lock.STOP_UNRESTORED)
                self.assertIn(str(self.target), finished.stdout)
                self.assertIn(str(self.backup_file), finished.stdout)
        self.assertEqual(legacy_file.read_bytes(), stale_bytes)

    def test_lock_writes_the_fields_the_guard_reads_and_a_byte_identical_backup(self):
        finished = self.run_script(*self.lock_args())

        self.assertEqual(finished.returncode, 0, finished.stdout + finished.stderr)
        self.assert_ends_with(finished, "NEXT:")
        fields = json.loads(self.lock_file.read_text())
        self.assertEqual(set(fields), {"ts", "kind", "writer", "file", "backup_path", "pre_hash", "class", "line",
                                       "worktree", "owner_pid"})
        self.assertRegex(fields["ts"], STAMP_FORM)
        self.assertIsInstance(fields["owner_pid"], int)
        self.assertEqual(fields["pre_hash"], sha16(self.original))
        self.assertEqual(fields["file"], "src/a.py")
        self.assertEqual(fields["worktree"], str(self.repo))
        self.assertEqual(self.backup_file.read_bytes(), self.original)
        guard = self.run_script("--live", script=GUARD)
        self.assertEqual(guard.returncode, 0, guard.stdout + guard.stderr)

    def test_lock_refuses_when_any_lock_exists_and_writes_nothing(self):
        legacy_file = self.home / ".claude" / "calibration-lock.json"
        placements = {
            "live": (self.lock_file, {}),
            "stale": (self.lock_file, {"owner_pid": DEAD_PID}),
            "legacy": (legacy_file, {}),
        }
        for name, (place, overrides) in placements.items():
            with self.subTest(name):
                self.make_lock(**overrides)
                if place != self.lock_file:
                    legacy_file.parent.mkdir(exist_ok=True)
                    legacy_file.write_bytes(self.lock_file.read_bytes())
                    self.lock_file.unlink()
                before = place.read_bytes()

                finished = self.run_script(*self.lock_args())

                self.assertEqual(finished.returncode, mutation_lock.EXIT_STOP, finished.stdout)
                self.assert_ends_with(finished, "STOP:")
                self.assertEqual(place.read_bytes(), before)
                self.assertFalse((self.state / "backups").exists())
                place.unlink()

    def test_restore_after_an_edit_puts_the_bytes_back_and_removes_the_lock(self):
        self.locked_run()
        self.target.write_bytes(b"x = 99\n")

        finished = self.run_script("restore", "--owner-pid", os.getpid())

        self.assertEqual(finished.returncode, 0, finished.stdout + finished.stderr)
        self.assert_ends_with(finished, "DONE:")
        self.assertEqual(self.target.read_bytes(), self.original)
        self.assertFalse(self.lock_file.exists())

    def test_restore_with_no_edit_says_the_file_was_already_identical(self):
        self.locked_run()

        finished = self.run_script("restore", "--owner-pid", os.getpid())

        self.assertEqual(finished.returncode, 0, finished.stdout + finished.stderr)
        self.assert_ends_with(finished, "DONE:")
        self.assertIn("already identical", finished.stdout)
        self.assertFalse(self.lock_file.exists())

    def test_restore_with_a_tampered_backup_exits_3_and_changes_nothing(self):
        self.locked_run()
        self.target.write_bytes(b"edited\n")
        self.backup_file.write_bytes(b"tampered\n")
        lock_before = self.lock_file.read_bytes()

        finished = self.run_script("restore", "--owner-pid", os.getpid())

        self.assertEqual(finished.returncode, mutation_lock.EXIT_RESTORE_MISMATCH, finished.stdout)
        self.assertIn(mutation_lock.MISMATCH_HEADING, finished.stdout)
        self.assert_ends_with(finished, "STOP:", mutation_lock.STOP_RESTORE_MISMATCH)
        self.assertIn(str(self.target), finished.stdout)
        self.assertIn(str(self.backup_file), finished.stdout)
        self.assertEqual(self.lock_file.read_bytes(), lock_before)
        self.assertEqual(self.target.read_bytes(), b"edited\n")

    @unittest.skipIf(os.geteuid() == 0, "root can write to a read-only file")
    def test_restore_into_a_read_only_target_stops_with_the_recovery_line_and_keeps_the_lock(self):
        self.locked_run()
        self.target.write_bytes(b"edited\n")
        self.addCleanup(os.chmod, self.target, 0o600)
        os.chmod(self.target, 0o400)
        lock_before = self.lock_file.read_bytes()

        finished = self.run_script("restore", "--owner-pid", os.getpid())

        self.assert_stop(finished, mutation_lock.STOP_RESTORE_FAILED)
        self.assertIn(f'cp "{self.backup_file}" "{self.target}" && rm "{self.lock_file}"', finished.stdout)
        self.assertEqual(self.lock_file.read_bytes(), lock_before)

    def test_restore_refuses_another_owner_or_writer_and_prints_the_recovery_line(self):
        cases = {"another owner": {"owner_pid": os.getpid() + 1}, "another writer": {"writer": "calibrate"}}
        for name, overrides in cases.items():
            with self.subTest(name):
                self.make_lock(**overrides)
                self.make_backup()
                self.target.write_bytes(b"edited\n")
                before = self.lock_file.read_bytes()

                finished = self.run_script("restore", "--owner-pid", os.getpid())

                self.assert_stop(finished, mutation_lock.STOP_NOT_OURS)
                self.assertIn(f'cp "{self.backup_file}" "{self.target}" && rm "{self.lock_file}"', finished.stdout)
                self.assertEqual(self.target.read_bytes(), b"edited\n")
                self.assertEqual(self.lock_file.read_bytes(), before)

    def test_restore_of_an_old_layout_lock_prints_the_manual_lines_and_keeps_the_lock(self):
        old_backup = self.state / "backups" / "a.py.bak"
        cases = {
            "backup path in the old place": {"backup_path": str(old_backup)},
            "no worktree": {"worktree": ""},
            "absolute file": {"file": str(self.target)},
        }
        for name, overrides in cases.items():
            with self.subTest(name):
                self.make_lock(**overrides)
                self.make_backup()
                before = self.lock_file.read_bytes()

                finished = self.run_script("restore", "--owner-pid", os.getpid())

                self.assert_stop(finished, mutation_lock.STOP_OLD_LAYOUT)
                self.assertIn(f'rm "{self.lock_file}"', finished.stdout)
                self.assertEqual(self.lock_file.read_bytes(), before)

    def test_restore_of_an_old_layout_lock_prints_the_copy_line(self):
        old_backup = self.state / "backups" / "a.py.bak"
        self.make_lock(backup_path=str(old_backup))

        finished = self.run_script("restore", "--owner-pid", os.getpid())

        self.assertIn(f'cp "{old_backup}" "{self.target}"', finished.stdout)

    def test_lock_and_restore_work_under_an_untidy_state_root(self):
        untidy_root = f"{self.root}//state/."
        self.env["XDG_STATE_HOME"] = untidy_root

        locked = self.run_script(*self.lock_args())
        self.assertEqual(locked.returncode, 0, locked.stdout + locked.stderr)
        self.target.write_bytes(b"edited\n")
        restored = self.run_script("restore", "--owner-pid", os.getpid())

        self.assertEqual(restored.returncode, 0, restored.stdout + restored.stderr)
        self.assert_ends_with(restored, "DONE:")
        self.assertEqual(self.target.read_bytes(), self.original)

    def test_help_lists_every_precondition_in_order(self):
        finished = self.run_script("--help")

        self.assertEqual(finished.returncode, 0)
        positions = [finished.stdout.find(text) for text in mutation_lock.PRECONDITIONS]
        self.assertNotIn(-1, positions, finished.stdout)
        self.assertEqual(positions, sorted(positions))

    def test_check_and_lock_note_an_uncommitted_or_untracked_target_and_go_on(self):
        untracked = self.repo / "src" / "new.py"
        untracked.write_text("n = 1\n")
        edited = self.repo / "src" / "a.py"
        edited.write_bytes(self.original + b"z = 3\n")
        cases = {"edited": (edited, "src/a.py"), "untracked": (untracked, "src/new.py")}
        for name, (target, relpath) in cases.items():
            with self.subTest(name):
                porcelain = self.git("status", "--porcelain", "--", relpath).rstrip("\n")
                expected = f"NOTE: {relpath} has uncommitted edits ({porcelain})"
                checked = self.run_script("check", target)
                locked = self.run_script(*self.lock_args(target))

                for verb, finished in (("check", checked), ("lock", locked)):
                    self.assertEqual(finished.returncode, 0, finished.stdout + finished.stderr)
                    notes = [line for line in finished.stdout.splitlines() if line.startswith("NOTE:")]
                    self.assertEqual(len(notes), 1, f"{verb}: {finished.stdout}")
                    self.assertTrue(notes[0].startswith(expected), notes[0])
                self.assertEqual((self.state / "backups" / relpath).read_bytes(), target.read_bytes())
                self.lock_file.unlink()

    def test_lock_stops_when_the_target_is_too_large_to_back_up(self):
        big = self.repo / "src" / "big.bin"
        big.write_bytes(b"")
        os.truncate(big, mutation_lock.file_backup.MAX_FILE_BYTES + 1)

        finished = self.run_script(*self.lock_args(big))

        self.assert_stop(finished, mutation_lock.STOP_BACKUP_FAILED)
        self.assertFalse(self.lock_file.exists())

    def test_restore_with_no_lock_stops(self):
        finished = self.run_script("restore", "--owner-pid", os.getpid())

        self.assert_stop(finished, mutation_lock.STOP_NO_LOCK)

    def test_restore_with_only_a_legacy_lock_stops(self):
        legacy_file = self.home / ".claude" / "calibration-lock.json"
        legacy_file.parent.mkdir()
        self.make_lock()
        legacy_file.write_bytes(self.lock_file.read_bytes())
        self.lock_file.unlink()

        finished = self.run_script("restore", "--owner-pid", os.getpid())

        self.assert_stop(finished, mutation_lock.STOP_LEGACY_LOCK)

    def test_restore_with_a_missing_backup_stops_and_keeps_the_lock(self):
        self.locked_run()
        self.target.write_bytes(b"edited\n")
        self.backup_file.unlink()
        before = self.lock_file.read_bytes()

        finished = self.run_script("restore", "--owner-pid", os.getpid())

        self.assert_stop(finished, mutation_lock.STOP_BACKUP_MISSING)
        self.assertEqual(self.lock_file.read_bytes(), before)
        self.assertEqual(self.target.read_bytes(), b"edited\n")

    @unittest.skipIf(os.geteuid() == 0, "root can write in a read-only folder")
    def test_check_stops_when_the_backups_folder_cannot_be_written(self):
        state_home = self.root / "state"
        state_home.mkdir()
        self.addCleanup(os.chmod, state_home, 0o700)
        os.chmod(state_home, 0o500)

        finished = self.run_script("check", self.target)

        self.assert_stop(finished, mutation_lock.STOP_STATE_UNWRITABLE)
        self.assertFalse(self.lock_file.exists())

    @unittest.skipIf(os.geteuid() == 0, "root can write in a read-only folder")
    def test_lock_stops_when_the_state_folder_cannot_be_written(self):
        state_home = self.root / "state"
        state_home.mkdir()
        self.addCleanup(os.chmod, state_home, 0o700)
        os.chmod(state_home, 0o500)

        finished = self.run_script(*self.lock_args())

        self.assert_stop(finished, mutation_lock.STOP_STATE_UNWRITABLE)
        self.assertFalse(self.lock_file.exists())

    def test_restore_after_the_mutant_deleted_the_target_brings_it_back(self):
        self.locked_run()
        self.target.unlink()

        finished = self.run_script("restore", "--owner-pid", os.getpid())

        self.assertEqual(finished.returncode, 0, finished.stdout + finished.stderr)
        self.assert_ends_with(finished, "DONE:")
        self.assertEqual(self.target.read_bytes(), self.original)
        self.assertFalse(self.lock_file.exists())

    def test_lock_stops_on_a_class_that_is_not_one_line(self):
        for name, seed_class in {"empty": "", "blank": "  ", "newline": "a\nb", "carriage return": "a\rb"}.items():
            with self.subTest(name):
                args = self.lock_args()
                args[args.index("--class") + 1] = seed_class

                finished = self.run_script(*args)

                self.assert_stop(finished, mutation_lock.STOP_BAD_ARGUMENT)
                self.assertFalse(self.lock_file.exists())
                self.assertFalse((self.state / "backups").exists())

    def test_lock_stops_when_another_process_holds_the_lock_write_file(self):
        self.state.mkdir(parents=True)

        with mutation_lock.file_lock.hold_exclusive(self.state / "lock.write", 1):
            finished = self.run_script(*self.lock_args())

        self.assert_stop(finished, mutation_lock.STOP_LOCK_BUSY)
        self.assertFalse(self.lock_file.exists())
        self.assert_nothing_written()

    @unittest.skipIf(os.geteuid() == 0, "root can remove a lock in a read-only folder")
    def test_restore_reports_a_lock_it_cannot_remove(self):
        self.locked_run()
        self.target.write_bytes(b"edited\n")
        self.addCleanup(os.chmod, self.state, 0o700)
        os.chmod(self.state, 0o500)

        finished = self.run_script("restore", "--owner-pid", os.getpid())

        self.assert_stop(finished, mutation_lock.STOP_LOCK_NOT_REMOVED)
        self.assertIn(f'rm "{self.lock_file}"', finished.stdout)
        self.assertEqual(self.target.read_bytes(), self.original)

    def test_both_mutation_tester_prompts_call_only_verbs_and_flags_the_script_takes(self):
        call_pattern = re.compile(r"mutation_lock\.py (\w[\w-]*)([^\n`]*)")
        placeholders = (("<target>", "f.py"), ("<line>", "1"), ('"$PPID"', "1"),
                        ('"<one-line description>"', "x"))
        for prompt_file in MUTATION_TESTER_PROMPTS:
            calls = call_pattern.findall(prompt_file.read_text())
            with self.subTest(str(prompt_file)):
                self.assertEqual({verb for verb, _ in calls}, {"check", "lock", "restore"})
                for verb, rest in calls:
                    for placeholder, value in placeholders:
                        rest = rest.replace(placeholder, value)
                    argv = [verb, *shlex.split(rest)]
                    try:
                        mutation_lock.build_parser().parse_args(argv)
                    except SystemExit:
                        self.fail(f"the script rejects the prompt's call: {argv}")

    def test_both_mutation_tester_prompts_name_no_lock_path_hash_tool_or_count(self):
        banned = ("claude-calibration", "calibration-lock.json", "sha256sum", "jq -n", "all four", "all five")
        for prompt_file in MUTATION_TESTER_PROMPTS:
            text = prompt_file.read_text()
            with self.subTest(str(prompt_file)):
                for word in banned:
                    self.assertNotIn(word, text)
                bullets = [line for line in prompt_section(text, "## Step 0").splitlines() if line.startswith("- ")]
                self.assertEqual(len(bullets), 3, bullets)
                checking = [line for line in bullets if "mutation_lock.py check" in line]
                self.assertEqual(len(checking), 1, bullets)

    def test_mutation_tester_prompts_keep_the_restore_only_rule(self):
        for prompt_file in MUTATION_TESTER_PROMPTS:
            step_four = prompt_section(prompt_file.read_text(), "## Step 4")
            with self.subTest(str(prompt_file)):
                for forbidden in ("Never `git checkout`", "Never `Write`", "never `Edit`"):
                    self.assertIn(forbidden, step_four)
                self.assertIn("RESTORE HASH MISMATCH", step_four)
                self.assertIn("print the exact command it names, if any, for your caller to run", step_four)
                bullets = [line for line in step_four.splitlines() if line.startswith("- ")]
                unremoved = [line for line in bullets if "lock could not be removed" in line]
                other = [line for line in bullets if line.startswith("- Any other `STOP:`")]
                self.assertEqual(len(unremoved), 1, bullets)
                self.assertEqual(len(other), 1, bullets)
                self.assertNotIn("stays mutated", unremoved[0])
                self.assertIn("the target stays mutated: say so loudly at the top of your report", other[0])


def prompt_section(text, heading_start):
    """The lines of the `## ` section whose heading starts with heading_start."""
    lines = text.splitlines()
    starts = script_utils.top_level_sections(lines)
    for position, start in enumerate(starts):
        if not lines[start].startswith(heading_start):
            continue
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        return "\n".join(lines[start:end])
    return ""


if __name__ == "__main__":
    unittest.main()
