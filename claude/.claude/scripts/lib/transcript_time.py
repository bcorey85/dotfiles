"""transcript_time.py: owner of the conversion of a transcript's ISO 8601 timestamp to epoch seconds. Standard library
and `iso_time` only, so a hook that runs on every Write can import it cheaply."""
from datetime import timezone

import iso_time


def epoch_of_timestamp(timestamp):
    """Epoch seconds of an ISO 8601 timestamp such as `2026-11-15T06:22:12.305Z`. A timestamp with no offset is read
    as UTC. Raises ValueError (iso_time.IsoTimestampError) for any other."""
    moment = iso_time.parse_iso_timestamp(timestamp)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.timestamp()
