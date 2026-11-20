"""Tests for lib/gate_env.py: the environment variables a repo's gate commands need, from its plans and the personal
per-repo file."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import toolkit_paths

LIB_DIR = pathlib.Path(os.environ.get("GATE_ENV_SCRIPT") or toolkit_paths.LIB_DIR / "gate_env.py").parent
sys.path.insert(0, str(LIB_DIR))
import gate_env  # noqa: E402


class RepoGateEnvTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = pathlib.Path(directory.name)
        self.gate_env_file = self.root.parent / f"{self.root.name}-gate-env.json"
        self.addCleanup(self.gate_env_file.unlink, missing_ok=True)
        environment = mock.patch.dict(os.environ, {"CLAUDE_GATE_ENV_FILE": str(self.gate_env_file)})
        environment.start()
        self.addCleanup(environment.stop)

    def init_repo_with_origin(self, origin_url):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "remote", "add", "origin", origin_url], check=True)

    def test_the_personal_file_gives_the_assignments_listed_under_the_repo_name(self):
        self.init_repo_with_origin("git@x:org/app.git")
        self.gate_env_file.write_text(json.dumps({"app": ["PLUGINS=1"], "other": ["NOPE=1"]}))

        self.assertEqual(["PLUGINS=1"], gate_env.repo_gate_env(self.root))

    def test_a_plan_assignment_wins_over_the_personal_file_for_the_same_name(self):
        self.init_repo_with_origin("git@x:org/app.git")
        self.gate_env_file.write_text(json.dumps({"app": ["PLUGINS=1", "KEEP=1"]}))
        own_plan = self.write_plan("one", "PLUGINS=0 cargo test")

        self.assertEqual(["KEEP=1", "PLUGINS=0"], sorted(gate_env.repo_gate_env(self.root, own_plan)))

    def test_an_agreed_plan_assignment_wins_over_the_personal_file_when_the_run_has_no_plan(self):
        self.init_repo_with_origin("git@x:org/app.git")
        self.gate_env_file.write_text(json.dumps({"app": ["PLUGINS=1", "KEEP=1"]}))
        self.write_plan("one", "PLUGINS=0 cargo test")

        self.assertEqual(["KEEP=1", "PLUGINS=0"], sorted(gate_env.repo_gate_env(self.root, None)))

    def test_a_repo_with_no_origin_is_named_by_its_folder(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.gate_env_file.write_text(json.dumps({self.root.name: ["PLUGINS=1"]}))

        self.assertEqual(["PLUGINS=1"], gate_env.repo_gate_env(self.root))

    def test_a_folder_that_is_not_a_git_repo_is_named_by_its_folder(self):
        self.gate_env_file.write_text(json.dumps({self.root.name: ["PLUGINS=1"]}))

        self.assertEqual(["PLUGINS=1"], gate_env.repo_gate_env(self.root))

    def test_a_linked_worktree_with_no_origin_is_named_by_the_main_checkout_folder(self):
        main_checkout = self.root / "main-checkout"
        linked = self.root / "linked"
        subprocess.run(["git", "init", "-q", str(main_checkout)], check=True)
        subprocess.run(["git", "-C", str(main_checkout), "-c", "user.name=t", "-c", "user.email=t@t", "commit",
                        "-q", "--allow-empty", "-m", "base"], check=True)
        subprocess.run(["git", "-C", str(main_checkout), "worktree", "add", "-q", str(linked)], check=True)
        self.gate_env_file.write_text(json.dumps({"main-checkout": ["PLUGINS=1"], "linked": ["NOPE=1"]}))

        self.assertEqual(["PLUGINS=1"], gate_env.repo_gate_env(linked))

    def test_a_missing_personal_file_adds_nothing(self):
        self.init_repo_with_origin("git@x:org/app.git")

        self.assertEqual([], gate_env.repo_gate_env(self.root))

    def test_the_personal_file_path_is_the_one_the_variable_names_else_the_home_file(self):
        self.assertEqual(self.gate_env_file, gate_env.personal_gate_env_file())

        with mock.patch.dict(os.environ, {"HOME": "/home/someone"}):
            os.environ.pop("CLAUDE_GATE_ENV_FILE")
            self.assertEqual(pathlib.Path("/home/someone/.claude/gate-env.json"), gate_env.personal_gate_env_file())

    def test_a_malformed_personal_file_raises_naming_the_file_and_the_entry(self):
        self.init_repo_with_origin("git@x:org/app.git")
        bad_files = {
            "not json": "{nope",
            "not a mapping": json.dumps(["PLUGINS=1"]),
            "not a list": json.dumps({"app": "PLUGINS=1"}),
            "not an assignment": json.dumps({"app": ["PLUGINS"]}),
            "a value the loop cannot read back": json.dumps({"app": ["A=$HOME/x"]}),
            "a word with a command separator": json.dumps({"app": ["A=a;b"]}),
            "a quoted word": json.dumps({"app": ["'A=1'"]}),
            "a quoted value with a newline": json.dumps({"app": ['A="a\nb"']}),
        }
        for label, text in bad_files.items():
            with self.subTest(label):
                self.gate_env_file.write_text(text)

                with self.assertRaises(ValueError) as caught:
                    gate_env.repo_gate_env(self.root)

                self.assertIn(str(self.gate_env_file), str(caught.exception))
                if label not in ("not json", "not a mapping"):
                    self.assertIn("'app'", str(caught.exception))

    def write_plan(self, folder, command):
        plan_dir = self.root / "docs/plans" / folder
        plan_dir.mkdir(parents=True)
        (plan_dir / "spec.md").write_text(
            f"## Phase 1: X\n\n#### Automated Verification:\n\n- [ ] **T**: `{command}`\n"
        )
        return f"docs/plans/{folder}/spec.md"

    def test_a_repo_with_no_plans_has_no_gate_env(self):
        self.assertEqual([], gate_env.repo_gate_env(self.root))

    def test_plans_that_agree_on_a_value_give_it(self):
        self.write_plan("one", "A=1 cargo test")
        self.write_plan("two", "A=1 B=2 cargo test")

        self.assertEqual(["A=1", "B=2"], sorted(gate_env.repo_gate_env(self.root)))

    def test_plans_that_disagree_on_a_value_leave_the_name_out(self):
        self.write_plan("one", "A=1 cargo test")
        self.write_plan("two", "A=2 cargo test")
        self.write_plan("three", "B=3 cargo test")

        self.assertEqual(["B=3"], gate_env.repo_gate_env(self.root))

    def test_the_plan_of_the_run_decides_its_own_value_over_the_others(self):
        self.write_plan("one", "A=1 cargo test")
        own_plan = self.write_plan("two", "A=2 cargo test")
        self.write_plan("three", "A=3 cargo test")

        self.assertEqual(["A=2"], gate_env.repo_gate_env(self.root, own_plan))

    def test_the_plan_of_the_run_takes_no_name_that_only_other_plans_set(self):
        self.write_plan("one", "B=9 cargo test")
        own_plan = self.write_plan("two", "A=2 cargo test")

        self.assertEqual(["A=2"], gate_env.repo_gate_env(self.root, own_plan))

    def test_a_plan_with_no_names_gives_none_even_when_other_plans_agree(self):
        self.write_plan("one", "B=9 cargo test")
        own_plan = self.write_plan("two", "cargo test")

        self.assertEqual([], gate_env.repo_gate_env(self.root, own_plan))

    def test_shell_junk_in_other_plans_adds_no_names_and_literal_settings_stay(self):
        self.write_plan("one", "n=$(ledger count) && test 1 = 1")
        self.write_plan("two", "PATH=/x/bin:$PATH cargo test")
        self.write_plan("three", "T=$(find . -name x) cargo test")
        self.write_plan("four", "src=index pass=done")
        self.write_plan("five", "S=...; cargo test")
        self.write_plan("six", "CARGO_BUILD_JOBS=4 cargo test")

        self.assertEqual(["CARGO_BUILD_JOBS=4"], gate_env.repo_gate_env(self.root))

    def test_an_old_plan_with_a_misworded_verification_heading_does_not_stop_the_read(self):
        old_dir = self.root / "docs/plans/old"
        old_dir.mkdir(parents=True)
        old_plan = "## Phase 1: X\n\n#### Verification (automated):\n\n- [ ] `A=1 cargo test`\n"
        (old_dir / "spec.md").write_text(old_plan)
        self.write_plan("current", "B=2 cargo test")

        self.assertEqual(["B=2"], gate_env.repo_gate_env(self.root))

    def test_a_plan_path_that_does_not_exist_is_read_as_a_plan_with_no_names(self):
        self.write_plan("one", "B=9 cargo test")

        self.assertEqual(["B=9"], gate_env.repo_gate_env(self.root, "docs/plans/gone/spec.md"))


class CheckEnvTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = pathlib.Path(directory.name)
        self.main_checkout = self.root / "main"
        self.linked = self.root / "linked"
        subprocess.run(["git", "init", "-q", str(self.main_checkout)], check=True)
        subprocess.run(["git", "-C", str(self.main_checkout), "-c", "user.name=t", "-c", "user.email=t@t", "commit",
                        "-q", "--allow-empty", "-m", "base"], check=True)
        subprocess.run(["git", "-C", str(self.main_checkout), "worktree", "add", "-q", str(self.linked)], check=True)
        self.shims = self.root / "pyenv" / "shims"
        self.shims.mkdir(parents=True)
        self.base_env = {"PATH": "/usr/bin", "PYENV_ROOT": str(self.root / "pyenv")}

    def test_a_worktree_with_the_pin_only_in_the_main_checkout_gets_its_version_and_the_shims_first(self):
        (self.main_checkout / ".python-version").write_text("\n3.12.4\n3.11.9\n")

        result = gate_env.check_env(self.linked, self.base_env)

        self.assertEqual("3.12.4", result["PYENV_VERSION"])
        self.assertEqual(f"{self.shims}{os.pathsep}/usr/bin", result["PATH"])

    def test_a_pyenv_version_already_in_the_env_wins_over_the_main_checkout_pin(self):
        (self.main_checkout / ".python-version").write_text("3.12.4\n")
        caller_env = dict(self.base_env, PYENV_VERSION="3.9.0")

        result = gate_env.check_env(self.linked, caller_env)

        self.assertEqual("3.9.0", result["PYENV_VERSION"])

    def test_a_worktree_with_its_own_pin_gets_the_shims_and_no_version(self):
        (self.main_checkout / ".python-version").write_text("3.12.4\n")
        (self.linked / ".python-version").write_text("3.10.1\n")

        result = gate_env.check_env(self.linked, self.base_env)

        self.assertNotIn("PYENV_VERSION", result)
        self.assertTrue(result["PATH"].startswith(str(self.shims)), result["PATH"])

    def test_a_subfolder_of_a_worktree_with_its_own_pin_gets_no_version(self):
        (self.main_checkout / ".python-version").write_text("3.12.4\n")
        (self.linked / ".python-version").write_text("3.10.1\n")
        subfolder = self.linked / "pkg"
        subfolder.mkdir()

        result = gate_env.check_env(subfolder, self.base_env)

        self.assertNotIn("PYENV_VERSION", result)
        self.assertTrue(result["PATH"].startswith(str(self.shims)), result["PATH"])

    def test_a_subfolder_pin_alone_beats_the_main_checkout_pin(self):
        (self.main_checkout / ".python-version").write_text("3.12.4\n")
        subfolder = self.linked / "pkg"
        subfolder.mkdir()
        (subfolder / ".python-version").write_text("3.10.1\n")

        result = gate_env.check_env(subfolder, self.base_env)

        self.assertNotIn("PYENV_VERSION", result)
        self.assertTrue(result["PATH"].startswith(str(self.shims)), result["PATH"])

    def test_an_empty_main_checkout_pin_sets_no_version_and_still_adds_the_shims(self):
        (self.main_checkout / ".python-version").write_text("\n\n")

        result = gate_env.check_env(self.linked, self.base_env)

        self.assertNotIn("PYENV_VERSION", result)
        self.assertEqual(f"{self.shims}{os.pathsep}/usr/bin", result["PATH"])

    def test_no_pin_anywhere_leaves_the_env_as_it_is(self):
        self.assertEqual(self.base_env, gate_env.check_env(self.linked, self.base_env))

    def test_a_worktree_of_a_bare_repo_takes_no_pin_from_the_git_dir(self):
        bare = self.root / "bare.git"
        subprocess.run(["git", "clone", "-q", "--bare", str(self.main_checkout), str(bare)], check=True)
        (bare / ".python-version").write_text("3.12.4\n")
        bare_linked = self.root / "bare-linked"
        subprocess.run(["git", "-C", str(bare), "worktree", "add", "-q", "--detach", str(bare_linked)], check=True)

        self.assertIsNone(gate_env.main_checkout_pin(bare_linked))

    def test_a_pin_with_no_shims_folder_sets_no_path_entry(self):
        (self.main_checkout / ".python-version").write_text("3.12.4\n")
        self.shims.rmdir()

        result = gate_env.check_env(self.linked, self.base_env)

        self.assertEqual("/usr/bin", result["PATH"])

    def test_a_folder_that_is_not_a_git_repo_with_no_pin_leaves_the_env_as_it_is(self):
        plain = self.root / "plain"
        plain.mkdir()

        self.assertEqual(self.base_env, gate_env.check_env(plain, self.base_env))

    def test_the_given_env_is_not_changed(self):
        (self.main_checkout / ".python-version").write_text("3.12.4\n")
        given = dict(self.base_env)

        gate_env.check_env(self.linked, given)

        self.assertEqual(self.base_env, given)


if __name__ == "__main__":
    unittest.main()
