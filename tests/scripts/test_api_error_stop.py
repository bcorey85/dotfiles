"""lib/api_error_stop.py: what an API-error record means and when a resume prompt can go to its session, and
script_utils.last_api_error, which finds the record."""
import datetime
import json
import os
import pathlib
import sys
import tempfile
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import api_error_stop
import script_utils


def error_record(error, text="API Error", **fields):
    return {"type": "assistant", "uuid": "e-1", "isApiErrorMessage": True, "error": error,
            "message": {"id": "c1e05401-b4da", "role": "assistant", "content": [{"type": "text", "text": text}]},
            **fields}


class ResumeEpochTest(unittest.TestCase):
    def test_a_login_text_under_a_usage_limit_gets_no_resume_time(self):
        for text in ("Please run /login", "401 Unauthorized", "authentication problem"):
            with self.subTest(text):
                record = error_record("rate_limit", text, quotaLimits={"resetsAt": 1000})
                self.assertIsNone(api_error_stop.resume_epoch(record))

    def test_quota_limits_take_precedence_over_rate_limit_info(self):
        record = error_record("rate_limit", quotaLimits={"resetsAt": 1000},
                              apiErrorParams={"rate_limit_info": {"resetsAt": 5000}})

        self.assertEqual(api_error_stop.resume_epoch(record), 1000 + api_error_stop.RESET_MARGIN_SECONDS)

    def test_a_usage_limit_resumes_one_margin_after_its_reset(self):
        record = error_record("rate_limit", quotaLimits={"resetsAt": 1000})

        self.assertEqual(api_error_stop.resume_epoch(record), 1060)

    def test_a_bool_reset_time_is_no_time(self):
        record = error_record("rate_limit", quotaLimits={"resetsAt": True})

        self.assertIsNone(api_error_stop.resume_epoch(record))

    def test_a_server_error_with_no_timestamp_gets_no_resume_time(self):
        self.assertIsNone(api_error_stop.resume_epoch(error_record("server_error")))

    def test_a_server_error_waits_after_its_timestamp(self):
        record = error_record("server_error", timestamp="2026-01-01T00:00:00Z")
        stopped_at = script_utils.epoch_of_timestamp("2026-01-01T00:00:00Z")

        self.assertEqual(api_error_stop.resume_epoch(record), stopped_at + api_error_stop.SERVER_ERROR_WAIT_SECONDS)

    def test_a_timestamp_with_no_zone_reads_as_utc(self):
        record = error_record("server_error", timestamp="2026-01-01T00:00:00")
        utc_epoch = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc).timestamp()

        self.assertEqual(api_error_stop.resume_epoch(record), utc_epoch + api_error_stop.SERVER_ERROR_WAIT_SECONDS)

    def test_a_week_old_server_error_gets_no_resume_time_once_now_is_given(self):
        record = error_record("server_error", timestamp="2026-01-01T00:00:00Z")
        stopped_at = script_utils.epoch_of_timestamp("2026-01-01T00:00:00Z")
        week_later = stopped_at + 7 * 24 * 60 * 60
        recent = stopped_at + api_error_stop.SERVER_ERROR_WAIT_SECONDS + 60

        self.assertIsNone(api_error_stop.resume_epoch(record, week_later))
        self.assertEqual(api_error_stop.resume_epoch(record, recent),
                         stopped_at + api_error_stop.SERVER_ERROR_WAIT_SECONDS)

    def test_the_age_cap_cuts_off_one_second_past_the_cap_for_both_error_kinds(self):
        usage_limit = error_record("rate_limit", quotaLimits={"resetsAt": 1000})
        resume_at = 1000 + api_error_stop.RESET_MARGIN_SECONDS
        stamp = "2026-01-01T00:00:00Z"
        server_error = error_record("server_error", timestamp=stamp)
        server_resume_at = script_utils.epoch_of_timestamp(stamp) + api_error_stop.SERVER_ERROR_WAIT_SECONDS
        cap = api_error_stop.MAX_RESUME_AGE_SECONDS

        for record, at in ((usage_limit, resume_at), (server_error, server_resume_at)):
            with self.subTest(record["error"]):
                self.assertEqual(api_error_stop.resume_epoch(record, at + cap), at)
                self.assertIsNone(api_error_stop.resume_epoch(record, at + cap + 1))

    def test_an_unparseable_or_non_string_timestamp_gets_no_resume_time(self):
        for timestamp in ("garbage", 12345, None):
            with self.subTest(timestamp):
                record = error_record("server_error", timestamp=timestamp)
                self.assertIsNone(api_error_stop.resume_epoch(record))

    def test_a_message_id_holding_401_does_not_read_as_a_login(self):
        record = error_record("rate_limit", quotaLimits={"resetsAt": 1000})
        record["message"]["id"] = "c1e05401-b4da-4ce3-9374-5d62d7baec0d"

        self.assertEqual(api_error_stop.error_reason(record), api_error_stop.API_ERROR)
        self.assertIsNotNone(api_error_stop.resume_epoch(record))

    def test_an_authentication_failed_error_reads_as_a_login_whatever_its_text(self):
        record = error_record("authentication_failed", "Failed to authenticate: OAuth session expired")

        self.assertEqual(api_error_stop.error_reason(record), api_error_stop.LOGIN_EXPIRED)


class EpochOfTimestampTest(unittest.TestCase):
    def test_a_timestamp_with_an_offset_and_one_with_z_read_the_same_moment(self):
        zulu = script_utils.epoch_of_timestamp("2026-11-15T06:22:12.305Z")
        offset = script_utils.epoch_of_timestamp("2026-11-15T07:22:12.305+01:00")
        self.assertEqual(zulu, offset)


class LastApiErrorTest(unittest.TestCase):
    def last_api_error(self, lines):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        transcript = pathlib.Path(folder.name, "s.jsonl")
        transcript.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return script_utils.last_api_error(transcript)

    def test_records_of_other_types_after_the_error_are_skipped(self):
        error = json.dumps(error_record("rate_limit"))
        trailing = [json.dumps({"type": "system", "subtype": "turn_duration"}),
                    json.dumps({"type": "last-prompt"}), json.dumps({"type": "cost-state"})]

        found = self.last_api_error([error, *trailing])

        self.assertEqual(found["uuid"], "e-1")

    def test_a_conversation_record_after_the_error_means_the_session_went_on(self):
        error = json.dumps(error_record("rate_limit"))
        work = json.dumps({"type": "assistant", "message": {"role": "assistant", "content": []}})

        self.assertIsNone(self.last_api_error([error, work, json.dumps({"type": "last-prompt"})]))

    def test_a_torn_last_line_reads_as_no_error(self):
        self.assertIsNone(self.last_api_error([json.dumps(error_record("rate_limit")), "{"]))

    @unittest.skipIf(os.geteuid() == 0, "root ignores chmod 0")
    def test_an_unreadable_transcript_is_reported_only_when_asked(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        transcript = pathlib.Path(folder.name, "s.jsonl")
        transcript.write_text(json.dumps(error_record("rate_limit")) + "\n", encoding="utf-8")
        transcript.chmod(0)
        self.addCleanup(transcript.chmod, 0o644)

        reported = script_utils.last_api_error(transcript, report_unreadable=True)
        default = script_utils.last_api_error(transcript)

        self.assertEqual(reported, script_utils.TRANSCRIPT_UNREADABLE)
        self.assertIsNone(default)


if __name__ == "__main__":
    unittest.main()
