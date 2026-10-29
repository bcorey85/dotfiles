"""Checks for format_changed.py, the Stop and UserPromptSubmit hook that formats the files a turn changed.

Formatters are fake executables on PATH that record their arguments, run inside temp git repos.
Set HOOK_SCRIPTS_DIR to run against another directory of scripts."""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

import toolkit_paths

SCRIPT = pathlib.Path(os.environ.get("HOOK_SCRIPTS_DIR") or toolkit_paths.GATES_DIR) / "format_changed.py"

FAKE_TOOL = """#!/bin/sh
{
  printf 'tool=%s\\n' "$(basename "$0")"
  printf 'cwd=%s\\n' "$PWD"
  for a in "$@"; do printf 'arg=%s\\n' "$a"; done
  printf -- '--\\n'
} >> "$FAKE_LOG"
"""


class Repo:
    def __init__(self, test):
        self.scratch = tempfile.TemporaryDirectory()
        test.addCleanup(self.scratch.cleanup)
        root = pathlib.Path(self.scratch.name)
        self.home = root / "home"
        self.bin = root / "bin"
        self.repo = root / "repo"
        for directory in (self.home, self.bin, self.repo):
            directory.mkdir()
        self.log = root / "tools.log"
        self.environment = {"PATH": f"{self.bin}:/usr/bin:/bin", "HOME": str(self.home), "TMPDIR": str(root),
                            "FAKE_LOG": str(self.log), "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t", "GIT_CONFIG_GLOBAL": "/dev/null",
                            "GIT_CONFIG_SYSTEM": "/dev/null", "PWD": str(self.repo)}
        for key in ("LANG", "LC_ALL"):
            if key in os.environ:
                self.environment[key] = os.environ[key]
        self.git("init", "-q", "-b", "main")
        self.put("seed.txt", "seed\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "seed")

    def git(self, *arguments, cwd=None):
        return subprocess.run(
            ["git", *list(arguments)],
            cwd=str(self.repo if cwd is None else cwd),
            env=self.environment,
            capture_output=True,
        )

    def put(self, relative, content):
        target = self.repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

    def tool(self, name, local=False):
        directory = self.repo / "node_modules" / ".bin" if local else self.bin
        directory.mkdir(parents=True, exist_ok=True)
        (directory / name).write_text(FAKE_TOOL)
        (directory / name).chmod(0o755)

    def hook(self, event, session="s1", cwd=None, raw=None, extra_env=None):
        payload = {"hook_event_name": event, "session_id": session, "cwd": str(self.repo) if cwd is None else cwd}
        environment = dict(self.environment, **(extra_env or {}))
        return subprocess.run(
            [sys.executable, str(SCRIPT)],
            input=(raw if raw is not None else json.dumps(payload)).encode(),
            capture_output=True,
            env=environment,
            cwd=str(self.repo),
        )

    def calls(self):
        if not self.log.exists():
            return []
        calls = []
        for block in self.log.read_text().split("--\n"):
            lines = [line for line in block.split("\n") if line]
            if lines:
                calls.append((lines[0][len("tool="):], [line[len("arg="):] for line in lines[2:]]))
        return calls

    def state_files(self):
        directory = self.home / ".claude" / "state" / "format-changed"
        return sorted(path.name for path in directory.iterdir()) if directory.exists() else []

    def commit_branch_files(self, branch, files):
        """Commit `files` on a new `branch` cut from main, then return to main."""
        self.git("checkout", "-q", "-b", branch)
        for name, content in files.items():
            self.put(name, content)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", branch)
        self.git("checkout", "-q", "main")


class FormatChangedTest(unittest.TestCase):
    def setUp(self):
        self.repo = Repo(self)
        self.repo.tool("npx")

    def turn(self, files, session="s1"):
        self.repo.hook("UserPromptSubmit", session)
        for name, content in files.items():
            self.repo.put(name, content)
        return self.repo.hook("Stop", session)

    def stop_with_marker(self, marker, as_directory):
        """Prompt, dirty a formattable file, leave `marker` in the git dir, then Stop."""
        self.repo.hook("UserPromptSubmit")
        self.repo.put("a.ts", "1")
        target = self.repo.repo / ".git" / marker
        if as_directory:
            target.mkdir()
        else:
            target.write_text("0" * 40 + "\n")
        return self.repo.hook("Stop")

    def test_new_files_are_formatted_with_prettier_when_no_oxfmt(self):
        finished = self.turn({"a.ts": "1", "b.json": "1", "c.txt": "1"})
        self.assertEqual((finished.returncode, finished.stdout, finished.stderr), (0, b"", b""))
        self.assertEqual(self.repo.calls(), [("npx", ["--yes", "prettier", "--write", "a.ts", "b.json"])])

    def test_formatter_runs_in_the_repo_root_even_from_a_subdirectory(self):
        self.repo.put("sub/x.txt", "1")
        self.repo.hook("UserPromptSubmit", cwd=str(self.repo.repo / "sub"))
        self.repo.put("top.ts", "1")
        self.repo.hook("Stop", cwd=str(self.repo.repo / "sub"))
        log = self.repo.log.read_text()
        self.assertIn(f"cwd={self.repo.repo.resolve()}\n", log)
        self.assertEqual(self.repo.calls()[0][1][-1], "top.ts")

    def test_extension_selection(self):
        names = [
            "a.ts",
            "b.tsx",
            "c.js",
            "d.jsx",
            "e.vue",
            "f.json",
            "g.css",
            "h.scss",
            "i.md",
            "j.txt",
            "k.py",
            "l.TS",
            "m",
        ]
        self.turn(dict.fromkeys(names, "1"))
        self.assertEqual(
            self.repo.calls()[0][1][3:], sorted(name for name in names if name not in ("j.txt", "k.py", "l.TS", "m"))
        )

    def test_oxlint_then_oxfmt_when_on_path(self):
        self.repo.tool("oxlint")
        self.repo.tool("oxfmt")
        self.turn({"a.ts": "1", "b.json": "1"})
        self.assertEqual(
            self.repo.calls(), [("npx", ["oxlint", "--fix", "a.ts"]), ("npx", ["oxfmt", "a.ts", "b.json"])]
        )

    def test_local_eslint_is_used_without_oxlint(self):
        self.repo.tool("eslint", local=True)
        self.turn({"a.vue": "1", "b.md": "1"})
        self.assertEqual(self.repo.calls(), [
            ("npx", ["eslint", "--fix", "--no-warn-ignored", "--max-warnings=0", "a.vue"]),
            ("npx", ["--yes", "prettier", "--write", "a.vue", "b.md"])])

    def test_local_oxlint_wins_over_eslint(self):
        self.repo.tool("eslint", local=True)
        self.repo.tool("oxlint", local=True)
        self.repo.tool("oxfmt", local=True)
        self.turn({"a.js": "1"})
        self.assertEqual(self.repo.calls(), [("npx", ["oxlint", "--fix", "a.js"]), ("npx", ["oxfmt", "a.js"])])

    def test_format_only_files_skip_the_linter(self):
        self.repo.tool("oxlint")
        self.turn({"a.json": "1", "b.css": "1", "c.scss": "1", "d.md": "1"})
        self.assertEqual(
            self.repo.calls(), [("npx", ["--yes", "prettier", "--write", "a.json", "b.css", "c.scss", "d.md"])]
        )

    def test_plan_files_are_never_formatted(self):
        self.turn({"docs/plans/login/spec.md": "1", "docs/plans/login/shards.json": "1", "docs/notes.md": "1"})
        self.assertEqual(self.repo.calls(), [("npx", ["--yes", "prettier", "--write", "docs/notes.md"])])

    def test_nothing_formattable_runs_nothing(self):
        self.turn({"a.txt": "1"})
        self.assertEqual(self.repo.calls(), [])

    def test_files_dirty_before_the_prompt_are_left_alone_until_edited_again(self):
        self.repo.put("a.ts", "1")
        self.repo.hook("UserPromptSubmit")
        self.repo.hook("Stop")
        self.assertEqual(self.repo.calls(), [])
        self.repo.put("a.ts", "2")
        self.repo.hook("Stop")
        self.assertEqual(self.repo.calls(), [("npx", ["--yes", "prettier", "--write", "a.ts"])])

    def test_deleted_files_are_not_formatted(self):
        self.repo.put("gone.ts", "1")
        self.repo.git("add", "-A")
        self.repo.git("commit", "-q", "-m", "x")
        self.repo.hook("UserPromptSubmit")
        (self.repo.repo / "gone.ts").unlink()
        self.repo.hook("Stop")
        self.assertEqual(self.repo.calls(), [])

    def test_ignored_files_are_not_formatted(self):
        self.repo.put(".gitignore", "ignored.ts\n")
        self.repo.git("add", "-A")
        self.repo.git("commit", "-q", "-m", "x")
        self.turn({"ignored.ts": "1", "seen.ts": "1"})
        self.assertEqual(self.repo.calls()[0][1][-1], "seen.ts")

    def test_names_with_spaces_and_dashes_are_passed_whole(self):
        self.turn({"src/a b.ts": "1", "-dash.ts": "1"})
        self.assertEqual(self.repo.calls()[0][1][3:], ["-dash.ts", "src/a b.ts"])

    def test_snapshot_file_name_and_content(self):
        self.repo.put("a.ts", "1")
        self.repo.hook("UserPromptSubmit", session="abc")
        names = self.repo.state_files()
        self.assertEqual(len(names), 1)
        self.assertRegex(names[0], r"^abc-\d+$")
        text = (self.repo.home / ".claude" / "state" / "format-changed" / names[0]).read_text()
        self.assertRegex(text, r"^[0-9a-f]{40} a\.ts\n$")

    def test_snapshot_suffix_is_the_posix_cksum_of_the_root(self):
        self.repo.hook("UserPromptSubmit", session="abc")
        root = str(self.repo.repo.resolve())
        expected = subprocess.run(["cksum"], input=root.encode(), capture_output=True).stdout.split()[0].decode()
        self.assertEqual(self.repo.state_files(), ["abc-" + expected])

    def test_empty_dirty_set_writes_an_empty_snapshot(self):
        self.repo.hook("UserPromptSubmit")
        names = self.repo.state_files()
        self.assertEqual((self.repo.home / ".claude" / "state" / "format-changed" / names[0]).read_text(), "")

    def test_stop_without_a_snapshot_does_nothing(self):
        self.repo.put("a.ts", "1")
        self.repo.hook("Stop")
        self.assertEqual(self.repo.calls(), [])

    def test_stop_with_format_hook_off_formats_nothing(self):
        self.repo.hook("UserPromptSubmit")
        self.repo.put("a.ts", "1")
        self.repo.hook("Stop", extra_env={"CLAUDE_FORMAT_HOOK_OFF": "1"})
        self.assertEqual(self.repo.calls(), [])

    def test_sessions_do_not_share_snapshots(self):
        self.repo.hook("UserPromptSubmit", session="one")
        self.repo.put("a.ts", "1")
        self.repo.hook("Stop", session="two")
        self.assertEqual(self.repo.calls(), [])

    def test_second_prompt_replaces_the_snapshot(self):
        self.repo.hook("UserPromptSubmit")
        self.repo.put("a.ts", "1")
        self.repo.hook("UserPromptSubmit")
        self.repo.hook("Stop")
        self.assertEqual(self.repo.calls(), [])

    def test_other_events_do_nothing(self):
        self.repo.hook("UserPromptSubmit")
        self.repo.put("a.ts", "1")
        finished = self.repo.hook("SessionStart")
        self.assertEqual((finished.returncode, finished.stdout, self.repo.calls()), (0, b"", []))

    def test_missing_session_id_does_nothing(self):
        for raw in ('{"hook_event_name":"UserPromptSubmit","cwd":"/"}', '{"hook_event_name":"Stop","session_id":null}',
                    '{"hook_event_name":"Stop","session_id":""}'):
            finished = self.repo.hook("x", raw=raw)
            self.assertEqual(finished.returncode, 0)
        self.assertEqual(self.repo.state_files(), [])

    def test_empty_cwd_falls_back_to_pwd(self):
        self.repo.hook("UserPromptSubmit", cwd="")
        self.repo.put("a.ts", "1")
        self.repo.hook("Stop", cwd="")
        self.assertEqual(len(self.repo.calls()), 1)

    def test_cwd_outside_a_repo_does_nothing(self):
        finished = self.repo.hook("UserPromptSubmit", cwd="/nonexistent/dir")
        self.assertEqual((finished.returncode, self.repo.state_files()), (0, []))

    def test_skip_switches_exit_quietly_and_write_nothing(self):
        for variable in ("CLAUDE_SKIP_HOOKS", "CLAUDE_FORMAT_HOOK_OFF"):
            with self.subTest(variable=variable):
                finished = self.repo.hook("UserPromptSubmit", extra_env={variable: "1"})
                self.assertEqual((finished.returncode, finished.stdout, self.repo.state_files()), (0, b"", []))

    def test_empty_skip_hooks_still_runs(self):
        self.repo.hook("UserPromptSubmit", extra_env={"CLAUDE_SKIP_HOOKS": ""})
        self.assertEqual(len(self.repo.state_files()), 1)

    def test_bad_payloads_exit_zero_and_write_nothing(self):
        for raw in ("", "not json", "[1]", "null", "5", '{"hook_event_name":5,"session_id":"s"}'):
            finished = self.repo.hook("x", raw=raw)
            self.assertEqual((finished.returncode, finished.stdout), (0, b""), raw)
        self.assertEqual(self.repo.state_files(), [])

    def test_old_snapshots_are_deleted_by_whole_days(self):
        directory = self.repo.home / ".claude" / "state" / "format-changed"
        directory.mkdir(parents=True)
        for name, days in (("four", 4), ("three", 3), ("two", 2), ("one", 1)):
            path = directory / name
            path.write_text("x\n")
            old = time.time() - days * 86400 - 60
            os.utime(str(path), (old, old))
        self.repo.hook("UserPromptSubmit")
        remaining = [name for name in self.repo.state_files() if "-" not in name]
        self.assertEqual(remaining, ["one", "two"])

    def test_missing_npx_is_not_fatal(self):
        (self.repo.bin / "npx").unlink()
        git_only = self.repo.bin.parent / "git-only"
        git_only.mkdir()
        (git_only / "git").symlink_to(shutil.which("git"))
        self.repo.environment["PATH"] = f"{self.repo.bin}:{git_only}"
        finished = self.turn({"a.ts": "1"})
        self.assertEqual(finished.returncode, 0)

    def test_repo_without_commits(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        fresh = pathlib.Path(scratch.name)
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=str(fresh), env=self.repo.environment)
        (fresh / "n.ts").write_text("1")
        self.repo.hook("UserPromptSubmit", cwd=str(fresh))
        self.repo.hook("Stop", cwd=str(fresh))
        self.assertEqual(self.repo.calls(), [])

    def test_unfinished_operation_markers_block_formatting(self):
        markers = (("MERGE_HEAD", False), ("CHERRY_PICK_HEAD", False), ("REVERT_HEAD", False),
                   ("rebase-merge", True), ("rebase-apply", True))
        for marker, as_directory in markers:
            with self.subTest(marker=marker):
                self.setUp()
                finished = self.stop_with_marker(marker, as_directory=as_directory)
                self.assertEqual((finished.returncode, finished.stdout, self.repo.calls()), (0, b"", []))

    def test_files_brought_in_by_an_uncommitted_merge_are_not_formatted(self):
        self.repo.commit_branch_files("other", {"theirs.md": "* item\n", "theirs.ts": "1"})
        self.repo.hook("UserPromptSubmit")
        self.repo.git("merge", "--no-ff", "--no-commit", "other")
        self.assertTrue((self.repo.repo / ".git" / "MERGE_HEAD").exists())
        self.repo.hook("Stop")
        self.assertEqual(self.repo.calls(), [])

    def test_uncommitted_merge_in_a_linked_worktree_blocks_formatting(self):
        self.repo.commit_branch_files("other", {"theirs.md": "* item\n", "theirs.ts": "1"})
        worktree = self.repo.repo.parent / "linked"
        self.repo.git("worktree", "add", "-q", "-b", "feature", str(worktree), "main")
        self.repo.hook("UserPromptSubmit", cwd=str(worktree))
        self.repo.git("merge", "--no-ff", "--no-commit", "other", cwd=worktree)
        self.assertTrue((worktree / "theirs.md").exists())
        self.assertFalse((worktree / ".git").is_dir())
        self.repo.hook("Stop", cwd=str(worktree))
        self.assertEqual(self.repo.calls(), [])

    def test_formatting_resumes_once_the_merge_or_squash_is_committed(self):
        for kind in ("merge", "squash"):
            with self.subTest(kind=kind):
                self.setUp()
                self.repo.commit_branch_files("other", {"theirs.ts": "1"})
                flag = "--no-ff" if kind == "merge" else "--squash"
                arguments = ["merge", flag] + (["--no-commit"] if kind == "merge" else []) + ["other"]
                merged = self.repo.git(*arguments)
                self.assertEqual(merged.returncode, 0, merged.stderr)
                committed = self.repo.git("commit", "-q", "-m", kind)
                self.assertEqual(committed.returncode, 0, committed.stderr)
                marker = "MERGE_HEAD" if kind == "merge" else "SQUASH_MSG"
                self.assertFalse((self.repo.repo / ".git" / marker).exists())
                self.turn({"mine.ts": "1"})
                self.assertEqual(self.repo.calls(), [("npx", ["--yes", "prettier", "--write", "mine.ts"])])

    def test_files_brought_in_by_an_uncommitted_squash_merge_are_not_formatted(self):
        self.repo.commit_branch_files("other", {"theirs.md": "* item\n", "theirs.ts": "1"})
        self.repo.hook("UserPromptSubmit")
        squashed = self.repo.git("merge", "--squash", "other")
        self.assertEqual(squashed.returncode, 0, squashed.stderr)
        git_dir = self.repo.repo / ".git"
        self.assertTrue((git_dir / "SQUASH_MSG").exists())
        self.assertFalse((git_dir / "MERGE_HEAD").exists())
        self.repo.hook("Stop")
        self.assertEqual(self.repo.calls(), [])

    def test_files_brought_in_by_an_uncommitted_cherry_pick_are_not_formatted(self):
        self.repo.commit_branch_files("other", {"theirs.md": "* item\n", "theirs.ts": "1"})
        self.repo.hook("UserPromptSubmit")
        picked = self.repo.git("cherry-pick", "-n", "other")
        self.assertEqual(picked.returncode, 0, picked.stderr)
        git_dir = self.repo.repo / ".git"
        self.assertTrue((git_dir / "MERGE_MSG").exists())
        self.assertFalse((git_dir / "CHERRY_PICK_HEAD").exists())
        self.repo.hook("Stop")
        self.assertEqual(self.repo.calls(), [])


if __name__ == "__main__":
    unittest.main()
