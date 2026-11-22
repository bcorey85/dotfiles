"""age_text.py: a span of seconds as a short age for a person to read. Standard library only."""

SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3600
SECONDS_PER_DAY = 86400


def age_text(seconds):
    """`seconds` as the largest whole unit: `7d`, `3h`, `12m`, else `under 1m`. A negative span reads as zero."""
    seconds = max(seconds, 0)
    if seconds >= SECONDS_PER_DAY:
        return f"{int(seconds // SECONDS_PER_DAY)}d"
    if seconds >= SECONDS_PER_HOUR:
        return f"{int(seconds // SECONDS_PER_HOUR)}h"
    if seconds >= SECONDS_PER_MINUTE:
        return f"{int(seconds // SECONDS_PER_MINUTE)}m"
    return "under 1m"
