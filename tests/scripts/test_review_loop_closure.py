"""Checks for review_loop_closure.closure_check: a reply with no JSON object gets one retry under its own role, and
the prompt it sends holds the purpose check and asks for the members left alone."""
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

        self.assertEqual(result, {"receipt": "all exits re-read", "open": ["a.py:3 - defect - fix"], "left_alone": []})
        self.assertEqual([role for role, _ in calls], ["class-closure", "class-closure-retry"])
        retry_prompt = calls[1][1]
        self.assertIn("could not be used", retry_prompt)
        self.assertIn("Reply with the JSON object only.", retry_prompt)
        shape = '{"receipt": .., "open": [..], "left_alone": [..]}'
        error = f'the class-closure reply holds no {shape} object: {prose!r}'
        self.assertIn(error[: review_loop_findings.RETRY_ERROR_CHARS], retry_prompt)
        self.assertNotIn(error[: review_loop_findings.RETRY_ERROR_CHARS + 1], retry_prompt)

    def test_the_prompt_checks_each_members_purpose_and_asks_the_reply_for_a_left_alone_list(self):
        _, calls = self.check([JSON_REPLY])
        prompt = calls[0][1]

        self.assertIn("say what it reads the value for, next to what the fixed line reads it for", prompt)
        self.assertIn("list it under left_alone with that purpose", prompt)
        self.assertIn('"left_alone": ["<file:line - what it reads the value for>", ...]', prompt)

    def test_the_members_left_alone_come_back_beside_the_open_list(self):
        reply = '{"receipt": "two readers", "open": [], "left_alone": ["log.py:9 - prints the limit"]}'
        result, calls = self.check([reply])

        self.assertEqual(["log.py:9 - prints the limit"], result["left_alone"])
        self.assertEqual(1, len(calls))

    def test_a_malformed_list_is_retried_and_the_second_reply_is_used(self):
        good = '{"receipt": "two readers", "open": [], "left_alone": ["log.py:9 - prints the limit"]}'
        malformed_replies = [
            ('{"receipt": "r", "open": [], "left_alone": "log.py:9 - prints the limit"}', "left_alone"),
            ('{"receipt": "r", "open": [], "left_alone": ["log.py:9 - prints the limit", " "]}', "left_alone"),
            ('{"receipt": "r", "open": [], "left_alone": ["log.py:9 - prints the limit", 3]}', "left_alone"),
            ('{"receipt": "r", "open": "a.py:3 - defect - fix"}', "open"),
            # A raw quote in the receipt: only closure_from_open_list decodes it, and its list is then rejected.
            ('{"receipt": "the "limit" readers", "open": ["a.py:3 - defect - fix"], '
             '"left_alone": ["log.py:9 - prints the limit", " "]}', "left_alone"),
        ]
        for malformed, rejected_key in malformed_replies:
            with self.subTest(malformed=malformed):
                result, calls = self.check([malformed, good])

                self.assertEqual(["log.py:9 - prints the limit"], result["left_alone"])
                self.assertEqual("two readers", result["receipt"])
                self.assertEqual(["class-closure", "class-closure-retry"], [role for role, _ in calls])
                self.assertIn(f"'{rejected_key}' must be a list of non-blank strings", calls[1][1])

    def test_two_malformed_replies_raise(self):
        malformed = '{"receipt": "r", "open": [], "left_alone": "log.py:9 - prints the limit"}'

        with self.assertRaises(ValueError) as raised:
            self.check([malformed, malformed])
        self.assertIn("'left_alone' must be a list of non-blank strings", str(raised.exception))

    def test_a_reply_without_the_left_alone_key_gives_an_empty_list(self):
        result, _ = self.check([JSON_REPLY])

        self.assertEqual([], result["left_alone"])

    def test_a_raw_quote_receipt_keeps_the_members_left_alone(self):
        reply = ('{"receipt": "the "limit" readers", "open": ["a.py:3 - defect - fix"], '
                 '"left_alone": ["log.py:9 - prints the limit"]}')
        result, calls = self.check([reply])

        self.assertEqual(["log.py:9 - prints the limit"], result["left_alone"])
        self.assertEqual(["a.py:3 - defect - fix"], result["open"])
        self.assertEqual(1, len(calls))

    def test_a_raw_quote_receipt_with_left_alone_before_open_keeps_the_receipt_clean(self):
        reply = ('{"receipt": "the "limit" readers", "left_alone": ["log.py:9 - prints the limit"], '
                 '"open": ["a.py:3 - defect - fix"]}')
        result, _ = self.check([reply])

        self.assertEqual('the "limit" readers', result["receipt"])
        self.assertNotIn("left_alone", result["receipt"])
        self.assertEqual(["log.py:9 - prints the limit"], result["left_alone"])
        self.assertEqual(["a.py:3 - defect - fix"], result["open"])

    def test_a_raw_quote_receipt_between_left_alone_and_open_keeps_the_receipt(self):
        reply = ('{"left_alone": ["log.py:9 - prints the limit"], "receipt": "the "limit" readers", '
                 '"open": ["a.py:3 - defect - fix"]}')
        result, _ = self.check([reply])

        self.assertEqual('the "limit" readers', result["receipt"])
        self.assertEqual(["log.py:9 - prints the limit"], result["left_alone"])
        self.assertEqual(["a.py:3 - defect - fix"], result["open"])

    def test_a_raw_quote_receipt_without_left_alone_gives_an_empty_list(self):
        reply = '{"receipt": "the "limit" readers", "open": ["a.py:3 - defect - fix"]}'
        result, _ = self.check([reply])

        self.assertEqual([], result["left_alone"])

    def test_a_raw_quote_reply_with_a_malformed_left_alone_list_retries(self):
        malformed = ('{"receipt": "the "limit" readers", "open": ["a.py:3 - defect - fix"], '
                     '"left_alone": ["log.py:9 - prints the limit" "x"]}')
        result, calls = self.check([malformed, JSON_REPLY])

        self.assertEqual(2, len(calls))
        self.assertEqual("all exits re-read", result["receipt"])

    def test_a_raw_quote_reply_with_open_before_receipt_keeps_both_lists_without_a_retry(self):
        reply = ('{"open": ["a.py:3 - defect - fix"], "receipt": "the "limit" readers", '
                 '"left_alone": ["log.py:9 - prints the limit"]}')
        result, calls = self.check([reply])

        self.assertEqual(1, len(calls))
        self.assertEqual("", result["receipt"])
        self.assertEqual(["a.py:3 - defect - fix"], result["open"])
        self.assertEqual(["log.py:9 - prints the limit"], result["left_alone"])

    def test_a_truncated_left_alone_list_retries_in_place_of_dropping_the_members(self):
        truncated = ('{"receipt": "the "limit" readers", "open": ["a.py:3 - defect - fix"], '
                     '"left_alone": ["log.py:9 - prints the lim')
        result, calls = self.check([truncated, JSON_REPLY])

        self.assertEqual(2, len(calls))
        self.assertEqual(["a.py:3 - defect - fix"], result["open"])

    def test_two_prose_replies_raise(self):
        with self.assertRaises(ValueError):
            self.check(["prose", "more prose"])

    def test_a_json_first_reply_makes_one_call(self):
        _, calls = self.check([JSON_REPLY])

        self.assertEqual([role for role, _ in calls], ["class-closure"])


if __name__ == "__main__":
    unittest.main()
