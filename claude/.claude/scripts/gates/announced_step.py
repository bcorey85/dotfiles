"""The announced step of a final message, for the Stop hook in staged_claim_gate.py: a turn that ends by saying the
session will do, or is doing, a step it has not started.

A sentence announces a step when it holds a first-person future or in-progress form of work: `I'll`, `I will`,
`I'm going to`, `I am going to`, `I'm about to`, `I'm (now) starting|doing|writing|running|working|fixing|looking|
checking|building|moving|reading|editing|adding|testing|picking`, `I'm on it`, `Next I'll`, `starting (it|that|this|on
it|work) now`, `on it now` or `working on it`.

A sentence is no announcement when it also:
- names a condition: `if`, `once`, `when`, `after`, `until`, `unless`, `as soon as`;
- names the user (`you`, `your`), or opens on a request with no first-person subject before `and I'll` or
  `and I will` ("Turn the gate off and I'll write the check"): the user acts first;
- says work runs or is waited on: `running`, `background`, `waiting`, `wait for`, `wait on`, `in progress`,
  `notif` (a notification), `queued`, `still runs`;
- asks a question (ends on `?`).

A span in backticks or double quotes on one line whose whole text is one announcement is dropped first: a sentence
cited as an example is no announcement.
"""
import re

from message_text import without_quoted_spans

ANNOUNCEMENT = re.compile(
    r"\b(?:I(?:'|\N{RIGHT SINGLE QUOTATION MARK})ll|I\s+will|I(?:'|\N{RIGHT SINGLE QUOTATION MARK})m\s+(?:now\s+)?"
    r"(?:going\s+to|about\s+to|on\s+it|starting|doing|writing|running|working|fixing|looking|checking|building|"
    r"moving|reading|editing|adding|testing|picking)|I\s+am\s+(?:now\s+)?(?:going\s+to|about\s+to|starting|working)"
    r"|starting\s+(?:it|that|this|on\s+it|work)\s+now|on\s+it\s+now|working\s+on\s+it)\b",
    re.IGNORECASE)
CONDITION = re.compile(r"\b(?:if|once|when|after|until|unless|as\s+soon\s+as)\b", re.IGNORECASE)
OTHER_ACTOR = re.compile(r"\b(?:you|your|yours)\b", re.IGNORECASE)
WORK_RUNS = re.compile(r"\b(?:running|background|waiting|wait\s+(?:for|on)|in\s+progress|notif\w*|queued|"
                       r"still\s+runs?)\b", re.IGNORECASE)
# `<request> and I'll ...` with no `I` or `we` before `and`: the step waits on the request.
REQUEST_THEN_STEP = re.compile(r"\band\s+I(?:'|\N{RIGHT SINGLE QUOTATION MARK})ll\b|\band\s+I\s+will\b",
                               re.IGNORECASE)
FIRST_PERSON = re.compile(r"\b(?:I|we)\b", re.IGNORECASE)
SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")

REASON = ("Your message says you will do, or are doing, a step, but the turn is ending with nothing started. "
          "Start that step now with a tool call, or say plainly that it has not started and who acts next.")


def announced_step(message):
    """The first sentence of a final message that announces a step with no condition, no other actor and no running
    work, or None."""
    unquoted_message = without_quoted_spans(ANNOUNCEMENT, message)
    for sentence in SENTENCE_END.split(unquoted_message):
        if not ANNOUNCEMENT.search(sentence):
            continue
        if sentence.rstrip().endswith("?"):
            continue
        if CONDITION.search(sentence) or OTHER_ACTOR.search(sentence) or WORK_RUNS.search(sentence):
            continue
        request = REQUEST_THEN_STEP.search(sentence)
        if request and not FIRST_PERSON.search(sentence[:request.start()]):
            continue
        return sentence.strip()
    return None
