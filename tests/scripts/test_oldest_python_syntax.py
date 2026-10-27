"""Checks that every toolkit Python file parses at the oldest Python ruff.toml targets. Hooks run as bare python3, and
a hook that hits a SyntaxError fails open: the harness prints the error and lets the call through."""
import ast
import json
import re
import tomllib
import unittest

import toolkit_paths

TOOLKIT_ROOT = toolkit_paths.CLAUDE_DIR.resolve().parents[1]
RUFF_CONFIG = TOOLKIT_ROOT / "ruff.toml"
SETTINGS = toolkit_paths.CLAUDE_DIR / "settings.json"
PYTHON_HOOK = re.compile(r"python3 ~/\.claude/(\S+)")


def oldest_python_version():
    """The (major, minor) of ruff.toml's target-version, such as (3, 12) for py312."""
    ruff_config = tomllib.loads(RUFF_CONFIG.read_text())
    target_digits = ruff_config["target-version"].removeprefix("py")

    return int(target_digits[0]), int(target_digits[1:])


def linted_python_files():
    """Every file ruff.toml's include patterns match, less its extend-exclude folders."""
    ruff_config = tomllib.loads(RUFF_CONFIG.read_text())
    excluded_dirs = [TOOLKIT_ROOT / excluded for excluded in ruff_config["extend-exclude"]]

    linted_files = set()
    for pattern in ruff_config["include"]:
        linted_files.update(path for path in TOOLKIT_ROOT.glob(pattern) if path.is_file())

    return {path for path in linted_files if not any(path.is_relative_to(excluded) for excluded in excluded_dirs)}


def python_hook_scripts():
    """The script file of every settings.json hook that runs as `python3 ~/.claude/<script>`."""
    settings = json.loads(SETTINGS.read_text())

    hook_scripts = set()
    for event_hooks in settings["hooks"].values():
        for matcher in event_hooks:
            for hook in matcher["hooks"]:
                hook_match = PYTHON_HOOK.search(hook.get("command", ""))
                if hook_match:
                    hook_scripts.add(toolkit_paths.CLAUDE_DIR.resolve() / hook_match.group(1))

    return hook_scripts


class OldestPythonSyntaxTest(unittest.TestCase):
    def test_every_linted_file_parses_at_the_ruff_target_version(self):
        oldest_version = oldest_python_version()

        syntax_errors = []
        for path in sorted(linted_python_files()):
            try:
                ast.parse(path.read_text(), filename=str(path), feature_version=oldest_version)
            except SyntaxError as error:
                syntax_errors.append(f"{path.relative_to(TOOLKIT_ROOT)}:{error.lineno}: {error.msg}")

        self.assertEqual([], syntax_errors)

    def test_a_three_fourteen_only_except_clause_fails_the_parse(self):
        unparenthesized_except = "try:\n    pass\nexcept ValueError, TypeError:\n    pass\n"

        with self.assertRaises(SyntaxError):
            ast.parse(unparenthesized_except, feature_version=(3, 12))

    def test_every_python_hook_in_settings_is_a_file_the_parse_check_covers(self):
        linted_files = linted_python_files()

        uncovered_hooks = sorted(str(script) for script in python_hook_scripts() if script not in linted_files)

        self.assertEqual([], uncovered_hooks)

    def test_settings_name_python_hooks_for_the_coverage_check_to_read(self):
        self.assertGreater(len(python_hook_scripts()), 0)


if __name__ == "__main__":
    unittest.main()
