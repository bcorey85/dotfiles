"""Checks the `if` filters on the git-only PreToolUse(Bash) hooks in settings.json."""
import json
import unittest

import toolkit_paths

SETTINGS = toolkit_paths.CLAUDE_DIR / "settings.json"

WHY_LEADING_STAR = (
    "The leading * matters: a measured headless run showed Bash(git *) skips the hook for "
    "`env git`, `/usr/bin/git`, `time git`, `command git`, `nice git`, `timeout 5 git` and "
    "`eval \"git ...\"`, while Bash(*git*) reached all of them."
)

EXPECTED_FILTERS = {
    "gates/git_discipline_gate.py": ["Bash(*git*)", "Bash(*gh*)"],
    "review/deferred_push_check.py": ["Bash(*git*)", "Bash(*gh*)"],
    "review/review_commit_gate.py": ["Bash(*git*)"],
}


def bash_pretooluse_handlers():
    settings = json.loads(SETTINGS.read_text())
    groups = settings["hooks"]["PreToolUse"]
    handlers = []
    for group in groups:
        if group.get("matcher") != "Bash":
            continue
        handlers.extend(group.get("hooks", []))
    return handlers


class HookIfFiltersTest(unittest.TestCase):
    def test_git_only_hooks_keep_wide_if_filters(self):
        handlers = bash_pretooluse_handlers()
        for script, expected in EXPECTED_FILTERS.items():
            with self.subTest(script=script):
                filters = [handler.get("if") for handler in handlers
                           if handler.get("command", "").endswith(script)]
                self.assertEqual(len(filters), len(expected),
                                 f"{script}: expected {len(expected)} handlers, found {len(filters)}. "
                                 + WHY_LEADING_STAR)
                self.assertEqual(set(filters), set(expected),
                                 f"{script}: `if` values {filters} differ from {expected}. "
                                 + WHY_LEADING_STAR)


if __name__ == "__main__":
    unittest.main()
