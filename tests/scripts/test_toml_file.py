"""Checks for lib/toml_file.py, and that the toolkit's scripts run on Python 3.10, the work machine's default python3.

No 3.10 interpreter is installed here, so a child Python stands in for one: it removes what 3.11 and later added and the
scripts use (tomllib, hashlib.file_digest, datetime.UTC) before it runs any toolkit code."""
import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile
import textwrap
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import toml_file

PYTHON_310_STAND_IN = textwrap.dedent("""\
    import datetime
    import hashlib
    import json
    import sys

    sys.modules["tomllib"] = None
    if hasattr(hashlib, "file_digest"):
        del hashlib.file_digest
    if hasattr(datetime, "UTC"):
        del datetime.UTC
    folders = [str(arg) for arg in json.loads(sys.argv[1])]
    sys.path[:0] = folders
""")

IMPORT_EVERY_SCRIPT = PYTHON_310_STAND_IN + textwrap.dedent("""\
    import runpy

    failures = {}
    for index, script in enumerate(json.loads(sys.argv[2])):
        sys.path.insert(0, script.rsplit("/", 1)[0])
        # coder_packet.py reads its arguments at its top level: --help makes it print its usage and exit.
        sys.argv = [script, "--help"]
        try:
            runpy.run_path(script, run_name=f"py310_import_check_{index}")
        except SystemExit:
            pass
        except Exception as error:
            failures[script] = f"{type(error).__name__}: {error}"
        finally:
            sys.path.pop(0)
    print(json.dumps(failures))
""")

NO_CONFIG_PATHS = PYTHON_310_STAND_IN + textwrap.dedent("""\
    import pathlib

    import check_discovery
    import format_files
    import full_check
    import pytest_config
    import worktree_snapshot

    repo = pathlib.Path(sys.argv[2])
    print(json.dumps({
        "pytest_options": pytest_config.pytest_options(repo),
        "configures_ruff": format_files.repo_configures_ruff(repo),
        "formats_with_ruff": format_files.repo_formats_with_ruff(repo),
        "pyproject_names": sorted(full_check.pyproject_names(repo)),
        "discovered_check": check_discovery.discovered_check_command(repo),
        "makefile_hash": worktree_snapshot.file_hash(repo, "Makefile"),
    }))
""")

PYPROJECT = """[project]
dependencies = ["requests"]

[tool.ruff.format]
quote-style = "single"

[tool.pytest.ini_options]
addopts = "-q"
"""


def script_folders():
    return [toolkit_paths.LIB_DIR, toolkit_paths.CODE_DIR, toolkit_paths.REVIEW_DIR, toolkit_paths.SCRIPTS_DIR]


def toolkit_python_files():
    """Every Python file of the toolkit's scripts and skill scripts, as strings."""
    scripts = sorted(toolkit_paths.SCRIPTS_DIR.glob("*/*.py"))
    scripts += sorted(toolkit_paths.SCRIPTS_DIR.glob("*.py"))
    scripts += sorted((toolkit_paths.CLAUDE_DIR / "skills").glob("*/scripts/*.py"))
    return [str(script) for script in scripts]


def run_stand_in(test, program, argument):
    """Run `program` in the stand-in Python, in an empty scratch folder, so a script that writes at import time writes
    there."""
    scratch = tempfile.TemporaryDirectory()
    test.addCleanup(scratch.cleanup)
    folders = json.dumps([str(folder) for folder in script_folders()])
    completed = subprocess.run([sys.executable, "-c", program, folders, argument], capture_output=True, text=True,
                               stdin=subprocess.DEVNULL, timeout=120, check=False, cwd=scratch.name)
    return completed


class ReadTomlTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.folder = pathlib.Path(scratch.name)

    def test_a_valid_file_reads_as_its_tables(self):
        config = self.folder / "pyproject.toml"
        config.write_text(PYPROJECT)

        self.assertEqual({"addopts": "-q"}, toml_file.read_toml(config)["tool"]["pytest"]["ini_options"])

    def test_a_missing_or_invalid_file_reads_as_empty(self):
        invalid = self.folder / "invalid.toml"
        invalid.write_text("[tool\n")

        self.assertEqual({}, toml_file.read_toml(invalid))
        self.assertEqual({}, toml_file.read_toml(self.folder / "missing.toml"))


class Python310Test(unittest.TestCase):
    maxDiff = None

    def test_every_toolkit_script_imports_without_what_python_3_11_added(self):
        scripts = toolkit_python_files()

        completed = run_stand_in(self, IMPORT_EVERY_SCRIPT, json.dumps(scripts))

        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual({}, json.loads(completed.stdout.splitlines()[-1]))

    def test_the_stand_in_finds_every_entry_script_the_work_machine_crashed_on(self):
        names = {pathlib.Path(script).name for script in toolkit_python_files()}

        self.assertLessEqual({"review_fix.py", "gate_commands.py", "code_review_start.py", "plan_check.py"}, names)

    def test_a_repo_with_toml_config_takes_the_no_config_path_with_a_note(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        repo = pathlib.Path(scratch.name)
        (repo / "pyproject.toml").write_text(PYPROJECT)
        makefile_text = b"test:\n\tpython3 -m unittest\n"
        (repo / "Makefile").write_bytes(makefile_text)
        makefile_hash = hashlib.sha256(makefile_text).hexdigest()

        completed = run_stand_in(self, NO_CONFIG_PATHS, str(repo))

        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual({"pytest_options": [], "configures_ruff": False, "formats_with_ruff": False,
                          "pyproject_names": [], "discovered_check": "make test", "makefile_hash": makefile_hash},
                         json.loads(completed.stdout.splitlines()[-1]))
        self.assertIn("has no tomllib", completed.stderr)


if __name__ == "__main__":
    unittest.main()
