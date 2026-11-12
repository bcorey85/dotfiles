import sys
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import criteria_verdict

UV_COMMAND = "uv run pytest"
UV_ITEM = "`uv run pytest` passes"
# What mise 2026.11.3 prints from the uv shim when the pinned uv is not installed.
MISE_NOT_INSTALLED = (
    "mise ERROR Tool not installed for shim: uv\n"
    "Missing tool version: aqua:astral-sh/uv@0.1.0\n"
    "Install all missing tools with: mise install\n")
MISE_INSTALL_FAILED = "mise ERROR Failed to install aqua:astral-sh/uv@0.1.0: error sending request for url\n"


class ItemVerdictTest(unittest.TestCase):
    def test_each_kind_of_item_maps_to_one_outcome_exit_style_code_and_hit_count(self):
        cases = [
            ("ban, no hit", "grep foo a", "`grep foo a` finds no match", 1, "", "GREEN", 0, 0),
            ("ban, a hit", "grep foo a", "`grep foo a` finds no match", 0, "a:foo\nb:foo\n", "RED", 1, 2),
            ("ban, search error", "grep foo a", "`grep foo a` finds no match", 2, "", "BROKEN", 2, 0),
            ("negated ban, no hit", "grep foo a", "`! grep foo a`", 1, "", "GREEN", 0, 0),
            ("presence, a hit", "grep foo a", "`grep foo a` finds the handler", 0, "foo\n", "GREEN", 0, None),
            ("presence, no hit", "grep foo a", "`grep foo a` finds the handler", 1, "", "RED", 1, None),
            ("pipe, zero", "grep foo a | wc -l", "`grep foo a | wc -l` prints 0", 0, "0\n", "GREEN", 0, 0),
            ("pipe, a count", "grep foo a | wc -l", "`grep foo a | wc -l` prints 0", 0, "3\n", "RED", 1, 3),
            ("not a search, passes", "test -e a", "`test -e a` exits 0", 0, "", "GREEN", 0, None),
            ("not a search, fails", "test -e a", "`test -e a` exits 0", 1, "", "RED", 1, None),
            ("command not found", "nope", "`nope` exits 0", 127, "", "BROKEN", 127, None),
            ("timeout", "slow", "`slow` exits 0", 124, "", "BROKEN", 124, None),
        ]
        for label, command, line, code, output, outcome, exit_code, hits in cases:
            with self.subTest(label):
                verdict = criteria_verdict.item_verdict(command, line, code, output)
                self.assertEqual((verdict.outcome, verdict.code, verdict.hits), (outcome, exit_code, hits))

    def test_a_ban_without_presence_wording_that_fails_carries_the_ban_note(self):
        verdict = criteria_verdict.item_verdict("grep foo a", "`grep foo a` must not exist", 0, "foo\n")
        self.assertEqual((verdict.outcome, verdict.code), ("RED", 1))
        self.assertNotIn(criteria_verdict.SEARCH_BAN_NOTE, verdict.output)

        verdict = criteria_verdict.item_verdict("grep foo a", "`grep foo a` shows foo", 0, "foo\n")
        self.assertTrue(verdict.output.endswith(criteria_verdict.SEARCH_BAN_NOTE))

    def test_a_filtered_test_run_that_matches_no_test_fails_with_a_note_and_a_flag(self):
        verdict = criteria_verdict.item_verdict("npx vitest run -t totals", "`npx vitest run -t totals` passes", 0,
                                                "No test files found")
        self.assertEqual((verdict.outcome, verdict.code), ("RED", 1))
        self.assertIn(criteria_verdict.NO_TEST_MATCHED_NOTE, verdict.output)
        self.assertIn("matches no test", verdict.flag)

    def test_a_filtered_run_that_prints_no_runner_summary_and_passes_no_test_is_red(self):
        for command in ("echo pytest -k nothing", "! cargo test x"):
            with self.subTest(command=command):
                verdict = criteria_verdict.item_verdict(command, f"`{command}` passes", 0, "")
                self.assertEqual((verdict.outcome, verdict.code), ("RED", 1))
                self.assertIn(criteria_verdict.NO_TEST_MATCHED_NOTE, verdict.output)

    def test_a_presence_search_for_a_filtered_runner_command_line_is_red_with_the_flag(self):
        command = "rg -n 'pytest -k foo' docs"
        output = "docs/a.md:1:pytest -k foo\n"
        verdict = criteria_verdict.item_verdict(command, f"`{command}` finds the line", 0, output)
        self.assertEqual((verdict.outcome, verdict.code), ("RED", 1))
        self.assertIn("matches no test", verdict.flag)

    def test_a_git_grep_line_with_presence_and_ban_wording_is_a_ban(self):
        line = "- [ ] **Prohibition**: no match, the call must not exist - `git grep -n x -- src`"
        self.assertTrue(criteria_verdict.is_search_ban("git grep -n x -- src", line))

    def test_a_search_behind_env_with_assignments_is_a_ban(self):
        command = "env LC_ALL=C rg -n foo src/"
        line = f"- [ ] **B**: no hits — `{command}`"
        self.assertTrue(criteria_verdict.is_search_ban(command, line))

    def test_an_environment_failure_reads_env_and_keeps_the_exit_style_code(self):
        cases = [
            ("mise not installed", MISE_NOT_INSTALLED),
            ("mise install failed", MISE_INSTALL_FAILED),
            ("mise not active", "mise ERROR uv is a mise bin however it is not currently active\n"),
            ("pyenv not installed", "pyenv: version `3.9.1' is not installed (set by /repo/.python-version)\n"),
            ("pyenv shim", "pyenv: uv: command not found\n"),
            ("asdf no version", "No version is set for command uv\nConsider adding one of the following versions\n"),
            ("asdf no preset version", "No preset version installed for command uv\n"),
            ("shell", "zsh: command not found: uv\n"),
            ("sh", "sh: 1: uv: not found\n"),
            ("dash", "/bin/sh: 1: uv: not found\n"),
            ("dry run shell line", "/bin/sh: line 1: uv: command not found\n"),
            ("bash", "bash: uv: command not found\n"),
            ("shell with path", "/bin/bash: uv: command not found\n"),
            ("uv spawn", "error: Failed to spawn: `pytest`\n"),
            ("poetry", "Command not found: pytest\n"),
            ("pipenv", "Error: the command pytest could not be found within PATH or Pipfile's [scripts].\n"),
        ]
        for label, output in cases:
            with self.subTest(label):
                verdict = criteria_verdict.item_verdict(UV_COMMAND, UV_ITEM, 1, output)
                self.assertEqual((verdict.outcome, verdict.code), ("ENV", 1))

    def test_a_line_numbered_command_not_found_stays_red(self):
        cases = [
            ("script with extension", "tests/run.sh: line 40: new_helper: command not found\n"),
            ("script with dot path", "./run.sh: line 3: uv: command not found\n"),
            ("script without extension", "scripts/check: line 3: uv: command not found\n"),
            ("shell command string", "bash: line 1: uv: command not found\n"),
        ]
        for label, output in cases:
            with self.subTest(label):
                verdict = criteria_verdict.item_verdict("bash tests/run.sh", "`bash tests/run.sh` passes", 1, output)
                self.assertEqual(verdict.outcome, "RED")

    def test_an_environment_failure_flag_names_the_matched_line(self):
        verdict = criteria_verdict.item_verdict(UV_COMMAND, UV_ITEM, 1, MISE_NOT_INSTALLED)
        self.assertEqual(verdict.flag, "environment failure: mise ERROR Tool not installed for shim: uv")

    def test_a_failure_without_an_environment_message_stays_red(self):
        verdict = criteria_verdict.item_verdict(UV_COMMAND, UV_ITEM, 1, "1 failed\n")
        self.assertEqual(verdict.outcome, "RED")

    def test_the_phrase_command_not_found_inside_assertion_text_stays_red(self):
        cases = [
            ("no test summary", "AssertionError: 'ok' != 'uv: command not found'\n"),
            ("failed test summary", "FAIL: x\nAssertionError: 'ok' != 'uv: command not found'\n1 failed\n"),
            ("script line with an exception name", "AssertionError: line 3: uv: command not found\n"),
            ("qualified exception name", "mypkg.errors.ConfigError: line 3: uv: command not found\n"),
            ("asdf unknown command", "asdf: unknown command: uv\n"),
            ("real-looking line after a failed summary", "1 failed\nzsh: command not found: uv\n"),
            ("traceback assertion", "Traceback (most recent call last):\n  File \"t.py\", line 1\n"
                                    "AssertionError: uv: command not found\n"),
            ("traceback command not found",
             "Traceback (most recent call last):\n  File \"t.py\", line 1\n"
             "AssertionError: Command not found: uv\n"),
            ("unittest failure", "FAIL: test_x\nbash: uv: command not found\nFAILED (failures=1)\n"),
            ("failing test line and no runner summary", "FAIL: test_x\nbash: uv: command not found\n"),
            ("unittest spawn line", "FAIL: test_x\nerror: Failed to spawn: `pytest`\nFAILED (failures=1)\n"),
            ("unittest quoted spawn text",
             "FAIL: t\nAssertionError: 'Failed to spawn: x' != 'y'\nFAILED (failures=1)\n"),
        ]
        for label, output in cases:
            with self.subTest(label):
                verdict = criteria_verdict.item_verdict("python3 -m pytest tests/test_x.py", "`...` passes", 1, output)
                self.assertEqual(verdict.outcome, "RED")

    def test_a_passing_run_never_reads_env(self):
        verdict = criteria_verdict.item_verdict(UV_COMMAND, UV_ITEM, 0, MISE_NOT_INSTALLED)
        self.assertEqual(verdict.outcome, "GREEN")

    def test_a_command_that_did_not_run_reads_broken_even_when_its_output_says_not_found(self):
        verdict = criteria_verdict.item_verdict(UV_COMMAND, UV_ITEM, 127,
                                                "zsh: command not found: uv\n")
        self.assertEqual(verdict.outcome, "BROKEN")

    def test_a_search_shim_that_cannot_start_reads_env_though_its_exit_1_is_a_no_match(self):
        verdict = criteria_verdict.item_verdict("rg -n foo src", "`rg -n foo src` finds no match", 1,
                                                MISE_NOT_INSTALLED)
        self.assertEqual((verdict.outcome, verdict.code), ("ENV", 0))

    def test_an_escaped_backticked_ban_is_still_judged_as_a_ban_through_judge_item(self):
        plain = criteria_verdict.item_verdict("rg -n 'exists*' src", "`rg -n 'exists*' src` passes", 0, "src/a:1:x")
        escaped = criteria_verdict.item_verdict("rg -n 'exists*' src", "`rg -n 'exists\\*' src` passes", 0, "src/a:1:x")
        self.assertEqual((plain.outcome, plain.code), ("RED", 1))
        self.assertEqual((escaped.outcome, escaped.code), (plain.outcome, plain.code))
        self.assertIn(criteria_verdict.SEARCH_BAN_NOTE, plain.output)
        self.assertIn(criteria_verdict.SEARCH_BAN_NOTE, escaped.output)

    def test_presence_wording_inside_a_backticked_span_does_not_make_a_ban_a_presence_check(self):
        line = "- [ ] `rg -n 'exists\\*' src` and `x contains y` passes"
        self.assertTrue(criteria_verdict.is_search_ban("rg -n 'exists*' src", line))


if __name__ == "__main__":
    unittest.main()
