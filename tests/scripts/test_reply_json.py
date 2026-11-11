"""Checks for lib/reply_json.py: the list after the last matching key, and the last JSON object with a wanted key,
in a reply that need not be valid JSON."""
import re
import sys
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import reply_json

OPEN_KEY = re.compile(r'"open"\s*:\s*(?=\[)')


class ListAfterLastKeyTests(unittest.TestCase):
    def test_absent_key_is_not_found(self):
        self.assertEqual(reply_json.list_after_last_key('{"other": []}', OPEN_KEY), (False, None, -1))

    def test_last_key_wins_and_reports_its_start(self):
        reply = 'x "open": [1] y "open": ["a", "b"] tail'
        found, value, key_start = reply_json.list_after_last_key(reply, OPEN_KEY)
        self.assertEqual((found, value, key_start), (True, ["a", "b"], reply.rfind('"open"')))

    def test_undecodable_list_is_found_with_no_value(self):
        reply = 'junk "open": [1, oops'
        found, value, key_start = reply_json.list_after_last_key(reply, OPEN_KEY)
        self.assertEqual((found, value, key_start), (True, None, reply.find('"open"')))

    def test_undecodable_last_key_is_final_even_when_an_earlier_key_decodes(self):
        reply = 'x "open": ["a"] y "open": [1, oops'
        found, value, key_start = reply_json.list_after_last_key(reply, OPEN_KEY)
        self.assertEqual((found, value, key_start), (True, None, reply.rfind('"open"')))


class LastJsonObjectTests(unittest.TestCase):
    def test_the_last_object_that_holds_a_wanted_key_is_returned_past_prose_braces(self):
        cases = [
            ("prose braces before the object", 'see {CUBE} then {"command": "make test"}', ("command",),
             {"command": "make test"}),
            ("the last of two objects", '{"open": 1} and {"open": 2}', ("open",), {"open": 2}),
            ("an object without a wanted key", '{"other": 1}', ("command",), None),
            ("no object", "plain text", ("command",), None),
        ]
        for message, reply, keys, expected in cases:
            with self.subTest(message):
                self.assertEqual(expected, reply_json.last_json_object(reply, keys))


if __name__ == "__main__":
    unittest.main()
