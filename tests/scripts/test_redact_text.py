"""Checks for redact_text.py: the home path scrub and the secret filter.
REDACT_TEXT_MODULE overrides the module path; it defaults to the installed one."""
import importlib.util
import os
import pathlib
import unittest

import toolkit_paths

MODULE = pathlib.Path(os.environ.get("REDACT_TEXT_MODULE") or toolkit_paths.LIB_DIR / "redact_text.py")
module_spec = importlib.util.spec_from_file_location("redact_text", MODULE)
redact_text = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(redact_text)


class RedactTextTest(unittest.TestCase):
    def test_scrub_replaces_any_home_directory_and_keeps_the_rest(self):
        scrubbed = redact_text.scrub("/home/bob/dev/x.py and /Users/amy/y.py and /srv/z.py")
        self.assertEqual(scrubbed, "/home/captured/dev/x.py and /home/captured/y.py and /srv/z.py")

    def test_a_secret_email_or_token_text_is_found_and_a_path_is_not(self):
        for text in ("mail me at a.b@example.com", "the API token is set", "key sk-abcdefghijklmnop1234",
                     "x" * 20 + "9" + "y" * 20):
            self.assertTrue(redact_text.has_secret(text), text)
        self.assertFalse(redact_text.has_secret("see /home/captured/dev/evals/ab-full/kit/repo/backend/src/x.ts:3"))

    def test_a_long_segment_after_a_slash_and_a_long_name_with_no_digit_are_not_secrets(self):
        self.assertFalse(redact_text.has_secret("see /repo/" + "a1b2" * 10 + "/x.py"))
        self.assertFalse(redact_text.has_secret("see /repo/" + "a1b2" * 10 + " done"))
        self.assertFalse(redact_text.has_secret("test_a_store_capture_writes_one_scrubbed_file"))


if __name__ == "__main__":
    unittest.main()
