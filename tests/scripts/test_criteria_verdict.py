import sys
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import criteria_verdict


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

    def test_a_git_grep_line_with_presence_and_ban_wording_is_a_ban(self):
        line = "- [ ] **Prohibition**: no match, the call must not exist - `git grep -n x -- src`"
        self.assertTrue(criteria_verdict.is_search_ban("git grep -n x -- src", line))


if __name__ == "__main__":
    unittest.main()
