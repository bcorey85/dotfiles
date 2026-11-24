"""Tests for lib/iso_time.py: ISO timestamps with a trailing Z read on Python 3.10, and UTC text with
milliseconds is written."""
import datetime
import sys
import unittest

from toolkit_paths import LIB_DIR

sys.path.insert(0, str(LIB_DIR))
import iso_time


class ParseIsoTimestampTest(unittest.TestCase):
    def test_a_trailing_z_reads_as_utc(self):
        moment = iso_time.parse_iso_timestamp("2026-11-22T14:55:42.777Z")

        expected = datetime.datetime(2026, 11, 22, 14, 55, 42, 777000, tzinfo=datetime.timezone.utc)
        self.assertEqual(expected, moment)

    def test_an_offset_is_kept(self):
        moment = iso_time.parse_iso_timestamp("2026-11-22T14:55:42+02:00")

        self.assertEqual(7200, moment.utcoffset().total_seconds())

    def test_text_that_is_no_timestamp_raises_value_error(self):
        with self.assertRaises(ValueError):
            iso_time.parse_iso_timestamp("yesterday")

    def test_a_fraction_of_any_length_reads(self):
        for text, microsecond in (("2026-11-22T14:55:42.77Z", 770000), ("2026-11-22T14:55:42.3135+00:00", 313500),
                                  ("2026-11-22T14:55:42.1234567Z", 123456)):
            with self.subTest(text):
                self.assertEqual(microsecond, iso_time.parse_iso_timestamp(text).microsecond)


class ParseZonedIsoTimestampTest(unittest.TestCase):
    def test_a_zoned_timestamp_reads(self):
        moment = iso_time.parse_zoned_iso_timestamp("2026-11-22T14:55:42Z")

        self.assertEqual(datetime.timezone.utc, moment.tzinfo)

    def test_text_with_no_zone_raises_value_error(self):
        for text in ("2026-11-22", "2026-11-22T14:55:42"):
            with self.subTest(text), self.assertRaises(ValueError):
                iso_time.parse_zoned_iso_timestamp(text)


class UtcMillisecondTextTest(unittest.TestCase):
    def test_an_offset_moment_is_written_in_utc_with_milliseconds(self):
        moment = iso_time.parse_iso_timestamp("2026-11-22T09:00:00-05:00")

        self.assertEqual("2026-11-22T14:00:00.000Z", iso_time.utc_millisecond_text(moment))

    def test_leftover_microseconds_round_down_or_up_as_asked(self):
        moment = iso_time.parse_iso_timestamp("2026-11-22T14:55:42.3135Z")

        self.assertEqual("2026-11-22T14:55:42.313Z", iso_time.utc_millisecond_text(moment))
        self.assertEqual("2026-11-22T14:55:42.314Z", iso_time.utc_millisecond_text(moment, round_up=True))

    def test_a_whole_millisecond_does_not_round_up(self):
        moment = iso_time.parse_iso_timestamp("2026-11-22T14:55:42.313Z")

        self.assertEqual("2026-11-22T14:55:42.313Z", iso_time.utc_millisecond_text(moment, round_up=True))

    def test_rounding_up_carries_into_the_next_second(self):
        moment = iso_time.parse_iso_timestamp("2026-11-22T14:55:42.9995Z")

        self.assertEqual("2026-11-22T14:55:43.000Z", iso_time.utc_millisecond_text(moment, round_up=True))


if __name__ == "__main__":
    unittest.main()
