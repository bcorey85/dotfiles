"""transcript_time.py: owner of the conversion of a transcript's ISO 8601 timestamp to epoch seconds. Standard library
only, so a hook that runs on every Write can import it cheaply."""
from datetime import datetime, timezone


def epoch_of_timestamp(timestamp):
    """Epoch seconds of an ISO 8601 timestamp such as `2026-11-15T06:22:12.305Z`. A timestamp with no offset is read
    as UTC. Raises ValueError for any other."""
    # Python 3.10's fromisoformat does not read a trailing Z.
    moment = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.timestamp()
