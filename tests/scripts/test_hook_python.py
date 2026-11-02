"""Checks for hook-python, the launcher every Python hook in settings.json runs through so that hooks skip a
version manager's python3 shim and never run on a Python older than ruff.toml's target-version.

Each case runs the launcher with HOME in a temp dir and a PATH of planted stand-in interpreters that print their own
name, so the case reads which interpreter the launcher chose.
"""
import json
import os
import pathlib
import re
import subprocess
import tempfile
import tomllib
import unittest

import toolkit_paths

HOOK_PYTHON = pathlib.Path(os.environ.get("HOOK_PYTHON_SCRIPT") or toolkit_paths.TOOLS_DIR / "hook-python")
SETTINGS = toolkit_paths.CLAUDE_DIR / "settings.json"
LAUNCHER_PREFIX = "sh ~/.claude/scripts/tools/hook-python "
PYTHON_SCRIPT = re.compile(r"~/\.claude/\S+\.py\b")

# A stand-in interpreter: prints its label and the arguments it was given.
FAKE_INTERPRETER_SOURCE = """#!/bin/sh
echo "{label} $*"
"""


class HookPythonTest(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.temp_root = pathlib.Path(temp_dir.name).resolve()
        self.home = self.temp_root / "home"
        self.home.mkdir()

    def plant_interpreter(self, folder, label, name="python3"):
        folder.mkdir(parents=True, exist_ok=True)
        interpreter = folder / name
        interpreter.write_text(FAKE_INTERPRETER_SOURCE.format(label=label))
        interpreter.chmod(0o755)
        return interpreter

    def plant_pyenv_version(self, version, label):
        pyenv_root = self.home / ".pyenv"
        self.plant_interpreter(pyenv_root / "versions" / version / "bin", label)
        (pyenv_root / "version").write_text(f"{version}\n")

    def run_launcher(self, path_dirs, **extra_env):
        env = {"HOME": str(self.home), "PATH": ":".join(str(folder) for folder in path_dirs), **extra_env}
        finished = subprocess.run(["/bin/sh", str(HOOK_PYTHON), "gate.py", "hook"], env=env, capture_output=True,
                                  text=True, check=True)
        return finished.stdout.strip()

    def test_pyenv_global_version_runs_without_the_shim(self):
        shims = self.home / ".pyenv" / "shims"
        self.plant_interpreter(shims, "shim")
        self.plant_pyenv_version("3.12.4", "pyenv")

        chosen = self.run_launcher([shims])

        self.assertEqual("pyenv gate.py hook", chosen)

    def test_pyenv_version_variable_beats_the_global_file(self):
        self.plant_pyenv_version("3.12.4", "global")
        self.plant_interpreter(self.home / ".pyenv" / "versions" / "3.13.1" / "bin", "pinned")

        chosen = self.run_launcher([], PYENV_VERSION="3.13.1")

        self.assertEqual("pinned gate.py hook", chosen)

    def test_pyenv_system_version_takes_the_first_python_outside_a_shims_folder(self):
        shims = self.home / ".pyenv" / "shims"
        system_bin = self.temp_root / "usr-bin"
        self.plant_interpreter(shims, "shim")
        self.plant_interpreter(system_bin, "system")
        (self.home / ".pyenv" / "version").write_text("system\n")

        chosen = self.run_launcher([shims, system_bin])

        self.assertEqual("system gate.py hook", chosen)

    def test_pyenv_version_prefix_runs_a_matching_version_folder(self):
        shims = self.home / ".pyenv" / "shims"
        system_bin = self.temp_root / "usr-bin"
        self.plant_interpreter(shims, "shim")
        self.plant_interpreter(system_bin, "system")
        self.plant_interpreter(self.home / ".pyenv" / "versions" / "3.12.4" / "bin", "pyenv")
        (self.home / ".pyenv" / "version").write_text("3.12\n")

        chosen = self.run_launcher([shims, system_bin])

        self.assertEqual("pyenv gate.py hook", chosen)

    def test_pyenv_version_older_than_the_floor_takes_a_versioned_python_on_path(self):
        shims = self.home / ".pyenv" / "shims"
        old_bin = self.temp_root / "old-bin"
        homebrew_bin = self.temp_root / "homebrew-bin"
        self.plant_interpreter(shims, "shim")
        self.plant_interpreter(old_bin, "old")
        self.plant_interpreter(homebrew_bin, "newer", name="python3.12")
        self.plant_interpreter(homebrew_bin, "newest", name="python3.13")
        self.plant_pyenv_version("3.9.12", "pyenv")

        chosen = self.run_launcher([shims, old_bin, homebrew_bin])

        self.assertEqual("newest gate.py hook", chosen)

    def test_pyenv_virtualenv_name_takes_a_versioned_python_on_path(self):
        homebrew_bin = self.temp_root / "homebrew-bin"
        self.plant_interpreter(homebrew_bin, "homebrew", name="python3.12")
        self.plant_interpreter(self.home / ".pyenv" / "versions" / "toolbox" / "bin", "virtualenv")

        chosen = self.run_launcher([homebrew_bin], PYENV_VERSION="toolbox")

        self.assertEqual("homebrew gate.py hook", chosen)

    def test_versioned_python_in_a_shims_folder_is_skipped(self):
        mise_shims = self.temp_root / "mise" / "shims"
        system_bin = self.temp_root / "usr-bin"
        self.plant_interpreter(mise_shims, "shim", name="python3.13")
        self.plant_interpreter(system_bin, "system")

        chosen = self.run_launcher([mise_shims, system_bin])

        self.assertEqual("system gate.py hook", chosen)

    def test_launcher_floor_matches_the_ruff_target_version(self):
        ruff_config = tomllib.loads((toolkit_paths.CLAUDE_DIR.resolve().parents[1] / "ruff.toml").read_text())
        target_minor = ruff_config["target-version"].removeprefix("py3")
        floor_match = re.search(r"^MIN_MINOR=(\d+)$", HOOK_PYTHON.read_text(), re.MULTILINE)

        if floor_match is None:
            self.fail("hook-python has no MIN_MINOR= line")
        self.assertEqual(target_minor, floor_match.group(1))

    def test_with_no_pyenv_a_shims_folder_on_path_is_skipped(self):
        mise_shims = self.temp_root / "mise" / "shims"
        homebrew_bin = self.temp_root / "homebrew-bin"
        self.plant_interpreter(mise_shims, "shim")
        self.plant_interpreter(homebrew_bin, "homebrew")

        chosen = self.run_launcher([mise_shims, homebrew_bin])

        self.assertEqual("homebrew gate.py hook", chosen)

    def test_with_only_shims_on_path_runs_plain_python3(self):
        mise_shims = self.temp_root / "mise" / "shims"
        self.plant_interpreter(mise_shims, "shim")

        chosen = self.run_launcher([mise_shims])

        self.assertEqual("shim gate.py hook", chosen)

    def test_pyenv_version_list_runs_the_first_version(self):
        self.plant_interpreter(self.home / ".pyenv" / "versions" / "3.13.1" / "bin", "first")
        self.plant_interpreter(self.home / ".pyenv" / "versions" / "3.12.4" / "bin", "second")

        chosen = self.run_launcher([], PYENV_VERSION="3.13.1:3.12.4")

        self.assertEqual("first gate.py hook", chosen)


class SettingsHookCommandsTest(unittest.TestCase):
    def test_every_python_hook_runs_through_the_launcher(self):
        settings = json.loads(SETTINGS.read_text())

        hook_commands = [hook.get("command", "") for event_hooks in settings["hooks"].values()
                         for matcher in event_hooks for hook in matcher["hooks"]]
        python_hooks = [command for command in hook_commands if PYTHON_SCRIPT.search(command)]
        bypassing_hooks = [command for command in python_hooks if not command.startswith(LAUNCHER_PREFIX)]

        self.assertGreater(len(python_hooks), 0)
        self.assertEqual([], bypassing_hooks)


if __name__ == "__main__":
    unittest.main()
