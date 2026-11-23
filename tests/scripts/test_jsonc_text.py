"""Checks for jsonc_text.py, the reader of JSON that holds comments and trailing commas."""
import json
import sys
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import jsonc_text

# The shape of a real .oxlintrc.json: line comments between keys and after a value.
COMMENTED_OXLINT_CONFIG = """{
  "$schema": "./node_modules/oxlint/configuration_schema.json",
  // Generated code is linted where it is generated.
  "ignorePatterns": ["dist/", "src/gen/**"], // keep in step with .gitignore
  "rules": {
    /* off until the
       migration lands */
    "no-console": "off",
  },
}
"""


class ParseJsoncTest(unittest.TestCase):
    def test_plain_json_reads_as_json(self):
        self.assertEqual(jsonc_text.parse_jsonc('{"a": [1, 2]}'), {"a": [1, 2]})

    def test_line_comments_block_comments_and_trailing_commas_are_cut(self):
        settings = jsonc_text.parse_jsonc(COMMENTED_OXLINT_CONFIG)

        self.assertEqual(settings["ignorePatterns"], ["dist/", "src/gen/**"])
        self.assertEqual(settings["rules"], {"no-console": "off"})

    def test_comment_marks_and_commas_inside_a_string_stay(self):
        text = '{"url": "https://example.test/a", "glob": "a/*.ts,]", "quote": "say \\"// no\\" /* x */"}'

        self.assertEqual(jsonc_text.parse_jsonc(text), json.loads(text))

    def test_text_that_is_not_json_raises_the_json_error(self):
        with self.assertRaises(json.JSONDecodeError):
            jsonc_text.parse_jsonc('{"a": // nothing\n}')


if __name__ == "__main__":
    unittest.main()
