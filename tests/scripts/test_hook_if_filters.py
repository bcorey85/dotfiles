"""Checks the `if` filters on the PreToolUse(Bash) hooks in settings.json that run behind one."""
import json
import re
import unittest

import toolkit_paths

SETTINGS = toolkit_paths.CLAUDE_DIR / "settings.json"

WHY_LEADING_STAR = (
    "The leading * matters: a measured headless run showed an anchored filter such as Bash(git *) "
    "skips the hook for `env git`, `/usr/bin/git`, `time git`, `command git`, `nice git`, "
    "`timeout 5 git` and `eval \"git ...\"`, while Bash(*git*) reached all of them."
)

EXPECTED_FILTERS = {
    "gates/git_discipline_gate.py": ["Bash(*git*)", "Bash(*gh*)"],
    "review/deferred_push_check.py": ["Bash(*git*)", "Bash(*gh*)"],
    "review/review_commit_gate.py": ["Bash(*git*)", "Bash(*review-gate-mark*)"],
    "review/review_loop_gate.py": ["Bash(*log-review-metrics*)"],
    "gates/rg_path_gate.py": ["Bash(*rg*)"],
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


ALWAYS_FIRING = {
    "bash-safety-gate.sh",
    "gates/inline_interpreter_hint.py",
    "gates/shell_write_gate.py",
    "gates/quality_check_cap.py",
    "code/coder_gate.py",
    "gates/wait_loop_gate.py",
}

# command -> scripts behind an `if` filter that fire for it (the always-firing ones are added in the test).
FILTERED_FIRES_BY_COMMAND = {
    "git commit -m x": {
        "gates/git_discipline_gate.py",
        "review/review_commit_gate.py",
        "review/deferred_push_check.py",
    },
    # A git alias: neither git gate fires today. This flips when the two git gates lose their `if` filters.
    "g commit -m x": set(),
    "env git push": {
        "gates/git_discipline_gate.py",
        "review/review_commit_gate.py",
        "review/deferred_push_check.py",
    },
    "gh pr create": {
        "gates/git_discipline_gate.py",
        "review/deferred_push_check.py",
    },
    "review-gate-mark clean": {"review/review_commit_gate.py"},
    "rg foo": {"gates/rg_path_gate.py"},
    "ls -la": set(),
}


def script_of(handler):
    """The script path under scripts/ that a handler command runs."""
    for token in handler["command"].split():
        if token.endswith((".py", ".sh")):
            return token.split("scripts/", 1)[1]
    raise ValueError(f"no script in {handler['command']!r}")


def filter_matches(if_filter, command):
    """Claude Code's `Bash(<glob>)` filter: `*` matches any text over the whole command string."""
    if if_filter is None:
        return True
    glob = if_filter[len("Bash("):-1]
    pattern = ".*".join(re.escape(part) for part in glob.split("*"))
    return re.fullmatch(pattern, command, re.DOTALL) is not None


def scripts_that_fire(command):
    return {script_of(handler) for handler in bash_pretooluse_handlers()
            if filter_matches(handler.get("if"), command)}


class HookIfFiltersTest(unittest.TestCase):
    def test_scripts_that_fire_per_command(self):
        for command, filtered in FILTERED_FIRES_BY_COMMAND.items():
            with self.subTest(command=command):
                self.assertEqual(scripts_that_fire(command), ALWAYS_FIRING | filtered)

    def test_bash_hooks_behind_an_if_filter_keep_wide_filters(self):
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
