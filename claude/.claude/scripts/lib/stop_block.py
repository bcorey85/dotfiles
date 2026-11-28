"""stop_block.py: the JSON line a Stop hook prints to block, with the blocked reply shown to the user.
Standard library only. Owner of a Stop block's output. Import it; never print a block line another way."""
import json

SYSTEM_MESSAGE_LIMIT = 10_000
REPLY_LABEL = "A Stop hook sent this reply back to the session. Its text:"
CUT_LINE = "[The reply was cut here to fit the hook message limit.]"
# systemMessage on a blocked Stop did not reach the user's pane in a live run on 2026-11-27. The session's next
# reply always does, so the reason asks the session to carry the blocked text there.
HIDDEN_REPLY_NOTE = ("The user did not see the reply this hook blocked. Open your next message with the line "
                     "the hook flagged, quoted, then give the whole reply again, corrected.")


def shown_reply(reply):
    """REPLY_LABEL, a blank line, then the reply, cut with CUT_LINE so the whole text fits SYSTEM_MESSAGE_LIMIT."""
    text = f"{REPLY_LABEL}\n\n{reply}"
    if len(text) <= SYSTEM_MESSAGE_LIMIT:
        return text

    ending = f"\n{CUT_LINE}"
    kept_length = SYSTEM_MESSAGE_LIMIT - len(ending)
    return text[:kept_length] + ending


def block_line(reasons, reply, show_reply):
    """The JSON line a Stop hook prints to block, or None when no reason holds. With show_reply and a reply, it
    also carries the reply in systemMessage and ends the reason with HIDDEN_REPLY_NOTE."""
    found_reasons = [reason for reason in reasons if reason]
    if not found_reasons:
        return None

    if not (show_reply and reply):
        return json.dumps({"decision": "block", "reason": " ".join(found_reasons)})

    reason = " ".join([*found_reasons, HIDDEN_REPLY_NOTE])
    return json.dumps({"decision": "block", "reason": reason, "systemMessage": shown_reply(reply)})
