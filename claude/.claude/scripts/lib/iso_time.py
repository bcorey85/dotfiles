"""Reading and writing ISO 8601 timestamps. Python 3.10's datetime.fromisoformat does not read a trailing Z, and
reads a fraction only of exactly 3 or 6 digits; this module accepts any number of fraction digits."""
import datetime
import re

FRACTION = re.compile(r"\.(\d+)")


def six_digit_fraction(match):
    """The replacement text for a FRACTION match: the digits padded or cut to 6 (extra digits are dropped)."""
    return "." + (match.group(1) + "000000")[:6]


def parse_iso_timestamp(text):
    """The datetime of an ISO timestamp such as 2026-11-22T14:55:42.777Z; a trailing Z reads as UTC.
    Raises ValueError for text that is not an ISO timestamp."""
    zoned = text[:-1] + "+00:00" if text.endswith("Z") else text
    fixed_fraction = FRACTION.sub(six_digit_fraction, zoned, count=1)
    return datetime.datetime.fromisoformat(fixed_fraction)


def parse_zoned_iso_timestamp(text):
    """Like parse_iso_timestamp, but text with no zone, such as 2026-11-22, raises ValueError too."""
    moment = parse_iso_timestamp(text)
    if moment.tzinfo is None:
        raise ValueError(f"no time zone in {text!r}")
    return moment


def utc_millisecond_text(moment, round_up=False):
    """A datetime as UTC text with milliseconds and a Z, such as 2026-11-22T14:55:42.777Z; string order is time order.
    Leftover microseconds round down, or up to the next millisecond when round_up is set."""
    utc = moment.astimezone(datetime.timezone.utc)
    millisecond = utc.replace(microsecond=utc.microsecond // 1000 * 1000)
    if round_up and utc.microsecond % 1000:
        millisecond += datetime.timedelta(milliseconds=1)
    return f"{millisecond:%Y-%m-%dT%H:%M:%S}.{millisecond.microsecond // 1000:03d}Z"
