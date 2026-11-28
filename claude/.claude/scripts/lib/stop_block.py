"""stop_block.py: the JSON line a Stop hook prints to block, with the blocked reply shown to the user.
Standard library only. Owner of a Stop block's output. Import it; never print a block line another way."""
import json

SYSTEM_MESSAGE_LIMIT = 10_000
REPLY_LABEL = "A Stop hook sent this reply back to the session. Its text:"
CUT_LINE = "[The reply was cut here to fit the hook message limit.]"


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
    also carries the reply in systemMessage."""
    found_reasons = [reason for reason in reasons if reason]
    if not found_reasons:
        return None

    decision = {"decision": "block", "reason": " ".join(found_reasons)}
    if show_reply and reply:
        decision["systemMessage"] = shown_reply(reply)
    return json.dumps(decision)
