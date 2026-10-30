"""Checks for review_loop_closure.closure_check: a reply with no JSON object gets one retry under its own role."""
import pathlib
import sys
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
import review_loop_closure
import review_loop_findings

JSON_REPLY = 'Done.\n{"receipt": "all exits re-read", "open": ["a.py:3 - defect - fix"]}'


class ClosureCheckRetryTest(unittest.TestCase):
    def check(self, replies):
        calls = []

        def fake_claude_call(role, prompt, repo, out, **options):
            calls.append((role, prompt))
            return replies[len(calls) - 1]

        result = review_loop_closure.closure_check(
            pathlib.Path("/repo"), pathlib.Path("/out"), ["finding one"], fake_claude_call
        )
        return result, calls

    def test_a_prose_reply_is_retried_once_and_the_second_reply_is_parsed(self):
        prose = "I will answer in prose. " + "x" * 500
        result, calls = self.check([prose, JSON_REPLY])

        self.assertEqual(result, {"receipt": "all exits re-read", "open": ["a.py:3 - defect - fix"]})
        self.assertEqual([role for role, _ in calls], ["class-closure", "class-closure-retry"])
        retry_prompt = calls[1][1]
        self.assertIn("could not be parsed", retry_prompt)
        self.assertIn("Reply with the JSON object only.", retry_prompt)
        error = f'the class-closure reply holds no {{"receipt": .., "open": [..]}} object: {prose!r}'
        self.assertIn(error[: review_loop_findings.RETRY_ERROR_CHARS], retry_prompt)
        self.assertNotIn(error[: review_loop_findings.RETRY_ERROR_CHARS + 1], retry_prompt)

    def test_two_prose_replies_raise(self):
        with self.assertRaises(ValueError):
            self.check(["prose", "more prose"])

    def test_a_json_first_reply_makes_one_call(self):
        _, calls = self.check([JSON_REPLY])

        self.assertEqual([role for role, _ in calls], ["class-closure"])


if __name__ == "__main__":
    unittest.main()
