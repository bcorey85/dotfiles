"""Checks for code_context.py, the warning a /code start gets when the main context is over its limit, and for the
UserPromptSubmit hook (format_changed.py) that prints it."""
import contextlib
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths

sys.path[:0] = [str(toolkit_paths.LIB_DIR)]
import code_context  # noqa: E402

HOOK = toolkit_paths.GATES_DIR / "format_changed.py"


def reply(input_tokens=0, cache_write=0, cache_read=0, sidechain=False):
    usage = {"input_tokens": input_tokens, "cache_creation_input_tokens": cache_write,
             "cache_read_input_tokens": cache_read, "output_tokens": 500}
    return {"type": "assistant", "isSidechain": sidechain, "message": {"role": "assistant", "usage": usage}}


def prompt_record(text):
    return {"type": "user", "message": {"role": "user", "content": text}}


class TranscriptCase(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.scratch = pathlib.Path(scratch.name)
        self.transcript = self.scratch / "session.jsonl"

    def write_transcript(self, *records):
        self.transcript.write_text("".join(json.dumps(record) + "\n" for record in records))


def synthetic_reply():
    usage = {"input_tokens": 0, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0, "output_tokens": 0}
    return {"type": "assistant", "isSidechain": False,
            "message": {"role": "assistant", "model": "<synthetic>", "usage": usage}}


class CodeContextTest(TranscriptCase):
    def test_a_synthetic_notice_after_a_large_reply_does_not_hide_its_size(self):
        self.write_transcript(reply(cache_read=180_000), synthetic_reply())

        self.assertEqual(180_000, code_context.context_tokens(str(self.transcript)))
        self.assertIsNotNone(code_context.code_start_warning("/code", str(self.transcript)))

    def test_a_compact_boundary_hides_the_replies_before_it(self):
        boundary = {"type": "system", "subtype": "compact_boundary"}
        self.write_transcript(reply(cache_read=180_000), boundary)

        self.assertIsNone(code_context.context_tokens(str(self.transcript)))
        self.assertIsNone(code_context.code_start_warning("/code", str(self.transcript)))

    def test_a_reply_after_a_compact_boundary_sets_the_size(self):
        boundary = {"type": "system", "subtype": "compact_boundary"}
        self.write_transcript(reply(cache_read=50_000), boundary, reply(cache_read=150_000))

        self.assertEqual(150_000, code_context.context_tokens(str(self.transcript)))
        self.assertIsNotNone(code_context.code_start_warning("/code", str(self.transcript)))

    def test_a_code_start_over_the_limit_warns_with_the_context_size(self):
        self.write_transcript(prompt_record("hi"), reply(input_tokens=3, cache_write=2_000, cache_read=140_000))

        warning = code_context.code_start_warning("/code docs/plans/x.md", str(self.transcript))

        message = json.loads(warning)["systemMessage"]
        self.assertIn("142k tokens", message)
        self.assertIn("Run /clear, then /code again.", message)

    def test_the_newest_main_reply_sets_the_size_and_subagent_replies_are_skipped(self):
        self.write_transcript(reply(cache_read=150_000), reply(cache_read=40_000),
                              reply(cache_read=300_000, sidechain=True), prompt_record("next"))

        self.assertEqual(40_000, code_context.context_tokens(str(self.transcript)))
        self.assertIsNone(code_context.code_start_warning("/code", str(self.transcript)))

    def test_a_context_at_the_limit_does_not_warn(self):
        self.write_transcript(reply(cache_read=code_context.CONTEXT_LIMIT))

        self.assertIsNone(code_context.code_start_warning("/code", str(self.transcript)))

    def test_only_a_typed_code_run_start_is_checked(self):
        self.write_transcript(reply(cache_read=500_000))
        cases = [("/code", True), ("  /code docs/plans/x.md 2", True), ("/code +fast fix it", True),
                 ("/code resume go on", False), ("/code-review", False), ("/codex", False), ("run /code", False),
                 ("hello", False)]
        for prompt, warns in cases:
            with self.subTest(prompt=prompt):
                warning = code_context.code_start_warning(prompt, str(self.transcript))
                self.assertEqual(warns, warning is not None)

    def test_a_new_session_or_an_unreadable_transcript_does_not_warn(self):
        self.write_transcript(prompt_record("/code"))
        self.assertIsNone(code_context.code_start_warning("/code", str(self.transcript)))
        self.assertIsNone(code_context.code_start_warning("/code", str(self.scratch / "missing.jsonl")))
        self.assertIsNone(code_context.code_start_warning("/code", ""))

    def test_a_missing_transcript_is_silent_and_another_read_error_names_the_gate_on_stderr(self):
        missing_errors = io.StringIO()
        with contextlib.redirect_stderr(missing_errors):
            missing_tokens = code_context.context_tokens(str(self.scratch / "missing.jsonl"))
        directory_errors = io.StringIO()
        with contextlib.redirect_stderr(directory_errors):
            directory_tokens = code_context.context_tokens(str(self.scratch))

        self.assertIsNone(missing_tokens)
        self.assertEqual("", missing_errors.getvalue())
        self.assertIsNone(directory_tokens)
        self.assertIn("format_changed/code_context", directory_errors.getvalue())


class HookTest(TranscriptCase):
    def run_hook(self, prompt, event="UserPromptSubmit"):
        payload = {"hook_event_name": event, "session_id": "s1", "cwd": str(self.scratch), "prompt": prompt,
                   "transcript_path": str(self.transcript)}
        environment = {"PATH": os.environ["PATH"], "HOME": str(self.scratch)}
        return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload).encode(), capture_output=True,
                              env=environment, cwd=str(self.scratch))

    def test_the_prompt_hook_prints_the_warning_on_a_large_code_start_and_nothing_otherwise(self):
        self.write_transcript(reply(cache_read=180_000))

        warned = self.run_hook("/code docs/plans/x.md")
        quiet = self.run_hook("/review")
        stop = self.run_hook("/code", event="Stop")

        self.assertEqual(0, warned.returncode)
        self.assertIn("180k tokens", json.loads(warned.stdout)["systemMessage"])
        self.assertEqual(b"", quiet.stdout)
        self.assertEqual(b"", stop.stdout)


if __name__ == "__main__":
    unittest.main()
