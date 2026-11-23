"""ruling_relay.py: a user ruling on user-only asks that the user gave to another session, which relays it with
`--by user --relayed-by <session name>` on `review_fix.py asks-done` and `phase_asks.py rule`. The call is verified
here, in process, against the relaying session's transcript (see human_turn_lookup): a relay with no real user turn
of that session typed after the asks were filed is refused. Only the turn's time is stored, never its words."""
import pathlib
import sys
from typing import NamedTuple

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / folder) for folder in (".", "../lib")]
import handback_store
import human_turn_lookup
import plan_format
import script_utils
from ask_outcome_words import RELAY_USAGE, RELAYED_BY_FLAG, RETIRED_QUOTE_FLAG, USER_ONLY_KEY
from human_turn_lookup import HumanTurnRefusedError
from review_fix_names import FILED_AT_KEY

REFUSAL_PREFIX = "relayed ruling refused: "


class RelayRefusedError(HumanTurnRefusedError):
    """The relay call is refused for its options or its asks, before or besides the turn lookup."""


def relay_refusal_line(error):
    """The user-facing line of a refused relay."""
    return f"{REFUSAL_PREFIX}{error}"


class RelayRequest(NamedTuple):
    """The relay words of a call: the relaying session's name."""
    relayed_by: str


class RelayedRuling(NamedTuple):
    """A verified relay: the request and the latest user turn of the relaying session."""
    request: RelayRequest
    turn: human_turn_lookup.HumanTurn


def pop_relay_options(words):
    """(the words without the relay option, RelayRequest or None). Raises RelayRefusedError for a `--relayed-by`
    with no value, or for the retired `--quote`: no ruling stores the user's words."""
    if RETIRED_QUOTE_FLAG in words:
        raise RelayRefusedError(f"{RETIRED_QUOTE_FLAG} is retired: never pass the user's words. Relay with "
                                f"`{RELAY_USAGE}` and the outcome words alone")
    rest, relayed_by = script_utils.pop_option(words, RELAYED_BY_FLAG)
    if relayed_by is None:
        return rest, None
    if not relayed_by:
        raise RelayRefusedError(f"a relayed ruling names the relaying session: {RELAY_USAGE}")
    return rest, RelayRequest(relayed_by)


def refuse_relay_without_user(request, ruler):
    """Raises RelayRefusedError for relay options on a call whose ruler is not the user."""
    if request is not None and ruler != plan_format.USER_RULING:
        raise RelayRefusedError(f"{RELAYED_BY_FLAG} relays the user's ruling, so it needs "
                                f"`--by {plan_format.USER_RULING}`")


def refuse_relay_without_user_only(asks):
    """Raises RelayRefusedError when no ask in `asks` is user_only: there is no user ruling to relay."""
    if not any(item.get(USER_ONLY_KEY) for item in asks):
        raise RelayRefusedError("no ask of this batch is user_only, so there is no user ruling to relay: drop "
                                f"{RELAYED_BY_FLAG}")


def latest_filed_at(asks):
    """The latest filed time among the user-only asks in `asks`. Raises RelayRefusedError when none is user-only,
    or one has no filed time: the turn must come after every ask it rules."""
    refuse_relay_without_user_only(asks)
    filed_times = []
    for number, item in enumerate(asks, 1):
        if not item.get(USER_ONLY_KEY):
            continue
        filed_at = item.get(FILED_AT_KEY)
        if not isinstance(filed_at, (int, float)):
            raise RelayRefusedError(f"user_only ask {number} has no filed time, so no user turn can be shown to "
                                    "come after it. Rule it with --by user from the user's own session, with no "
                                    "relay options")
        filed_times.append(filed_at)
    return max(filed_times)


def verify_relay(request, filed_at):
    """The RelayedRuling of `request`: the latest real user turn of the live session it names, typed after
    `filed_at` (epoch seconds). Raises HumanTurnRefusedError naming the lookup that failed."""
    turn = human_turn_lookup.verified_human_turn(request.relayed_by, filed_at)
    return RelayedRuling(request, turn)


def record_relay(session_id, repo, relayed, asks):
    """Stores the relayed ruling for the user-only asks in `asks` (see handback_store.record_relayed_ruling). Does
    nothing without a session id, as the other ask rows, and nothing when no user-only ask is in `asks`: a row
    that rules nothing is not a ruling."""
    if not session_id:
        return None
    finding_ids = [item.get("finding_id") for item in asks if item.get(USER_ONLY_KEY)]
    if not finding_ids:
        return None
    return handback_store.record_relayed_ruling(session_id, repo, plan_format.USER_RULING, relayed.request.relayed_by,
                                                relayed.turn.timestamp, finding_ids)
