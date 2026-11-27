"""The announced step of a final message, for the Stop hook in staged_claim_gate.py: a turn that ends by saying the
session will do, or is doing, a step it has not started.

A sentence announces a step when it holds a first-person future or in-progress form of work: `I'll`, `I will`,
`I'm` or `I am` then (`now`) `going to|about to|on it|starting|doing|writing|running|working|fixing|looking|checking|
building|moving|reading|editing|adding|testing|picking`, `Next I'll`, `starting (it|that|this|on it|work) now`,
`on it now` or `working on it`. The last three are progress forms with no subject; they are no announcement when
the current turn of the transcript launched background work (a background Bash call (`run_in_background`) or an
Agent call not set to the foreground, after the last turn start). A first-person sentence passes on the same
condition when its announced action is one of the report words (`bring back`, `report`, `rank`, `summarize`,
`collect`, `compile`, `relay`, `combine`, with suffixes): the word comes within one word of the announcement, and no
other step is joined to it by `and`. Every other first-person sentence is an announcement either way.

Fenced blocks and blockquote lines are drafts for the user and are dropped first (`message_text.without_draft_blocks`).

A sentence is no announcement when it also:
- names a condition: `if`, `once`, `when`, `after`, `until`, `unless`, `as soon as`;
- names the user (`you`, `your`), or opens on a request with no first-person subject before `and I'll` or
  `and I will` ("Turn the gate off and I'll write the check"): the user acts first;
- says work runs or is waited on: `running`, `background`, `waiting`, `wait for`, `wait on`, `in progress`,
  `notif` (a notification), `queued`, `still runs`;
- asks a question (ends on `?`);
- negates each of its first-person announcements in an allowed form, and holds no progress form: at most one start
  word (`start`, `begin`, `do`, `launch`, `open`, `run`, `touch`, `take`, `send`, `make`) then `no`, `nothing` or
  `none` ("I'm starting no lane", "I'll start nothing"), and no idiom word (`but`, `except`, `besides`, `beyond`,
  `apart`, `aside`, `other`, `more`, `fewer`, `less`, `doubt`, `longer`, `long`, `short`, `save`, `than`, `yet`,
  `later`, `till`, `first`, `for now`, `for the moment`, `at the moment`, `for the time being`, `right now`,
  `soon`, `shortly`, `eventually`, `afterwards`) comes anywhere after the announcement; or
  `not` then a start word or `act` ("I will not act on it", with the same idiom rule).
  Every other negation ("I'll not postpone the rerun") blocks. The text after each negated announcement holds no
  `and`, `but`, `then`, `or`, `so`, `while`, `before`, `instead`, `,`, `;`, `:`, an em or en dash or `--`. A negated
  sentence opens no Then or Next chain;
- gates the step on a date or clock: `on|by` a weekday, `on|by` a month and day (`Nov 29`, `November 29th`),
  `at 4:30`, `at 4:30pm`, `at 4pm`, `at :47`, `tomorrow`, `tonight`, `the next time`;
- waits on later events: `later` then a word ending in s, not an excluded one ("later merges"; `this`, `its`, `is`,
  `was`, `as`, `perhaps`, `always`, `anyways`, `sometimes`, `besides`, `versus`, `afterwards`,
  `towards`, `yes`, `thus`, `plus`, `does`, `has`, `us`, `whereas`, `his`, `hers`, `ours`,
  `theirs`, `nowadays`, `upstairs`, `downstairs` and `alas` are out, and so is any word ending in `ss`);
- waits on another party's notice: `act on (its|their|the)` then up to two words and `notice`, `result` or `report`.

A sentence that opens on `then` or `next` (after leading space or a list marker; `Next steps` is a header, not a
chain) passes when the sentence before it names a condition, another actor, running work, a date or clock, later
events or another party's notice, and a chained sentence that passes keeps the chain open. After an ungated
sentence it is judged like any other.
Own-step ordering ("at the end", "before starting", "in my final report") gates nothing.

A span in backticks or double quotes on one line whose whole text is one announcement is dropped first: a sentence
cited as an example is no announcement.
"""
import os
import re
import sys

sys.path[:0] = [os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib")]
import user_prompts
from message_text import without_draft_blocks, without_quoted_spans

_ANNOUNCED_ACTION = (r"(?:now\s+)?(?:going\s+to|about\s+to|on\s+it|starting|doing|writing|running|working|fixing|"
                     r"looking|checking|building|moving|reading|editing|adding|testing|picking)")
FIRST_PERSON_ANNOUNCEMENT = re.compile(
    r"\b(?:I(?:'|\N{RIGHT SINGLE QUOTATION MARK})ll|I\s+will|I(?:'|\N{RIGHT SINGLE QUOTATION MARK})m\s+"
    + _ANNOUNCED_ACTION + r"|I\s+am\s+" + _ANNOUNCED_ACTION + r")\b",
    re.IGNORECASE)
# A progress line with no first-person subject: it passes when the turn launched background work.
PROGRESS_ANNOUNCEMENT = re.compile(
    r"\b(?:starting\s+(?:it|that|this|on\s+it|work)\s+now|on\s+it\s+now|working\s+on\s+it)\b", re.IGNORECASE)
ANNOUNCEMENT = re.compile(FIRST_PERSON_ANNOUNCEMENT.pattern + "|" + PROGRESS_ANNOUNCEMENT.pattern, re.IGNORECASE)
# Report words. A first-person sentence whose announced action is one passes when the turn launched background work.
REPORT_STEP = re.compile(
    r"\b(?:bring(?:ing)?\s+back|report(?:s|ed|ing)?|rank(?:s|ed|ing)?|summari[sz](?:e[sd]?|ing)|"
    r"collect(?:s|ed|ing)?|compil(?:e[sd]?|ing)|relay(?:s|ed|ing)?|combin(?:e[sd]?|ing))\b", re.IGNORECASE)
# The report word is the announced action itself: it comes right after the first-person announcement, with at most
# one word between.
REPORT_ACTION = re.compile(r"\A\s*(?:\w+\s+)?" + REPORT_STEP.pattern, re.IGNORECASE)
_OBJECT_WORD = r"(?:the|a|an|their|its|them|these|those|this|that|it)"
# `and <verb> <object>` where the verb is no report word and no object word: a second step after the report.
SECOND_STEP = re.compile(r"\band\s+(?!" + _OBJECT_WORD + r"\b)(?!" + REPORT_STEP.pattern + r")\w+\s+" + _OBJECT_WORD
                         + r"\b", re.IGNORECASE)
# A word or mark that joins a second clause. A negated announcement passes only when none follows it.
CLAUSE_JOIN = re.compile(r"\b(?:and|but|then|or|so|while|before|instead)\b|[,;:\N{EM DASH}\N{EN DASH}]|--",
                         re.IGNORECASE)
CONDITION = re.compile(r"\b(?:if|once|when|after|until|unless|as\s+soon\s+as)\b", re.IGNORECASE)
OTHER_ACTOR = re.compile(r"\b(?:you|your|yours)\b", re.IGNORECASE)
WORK_RUNS = re.compile(r"\b(?:running|background|waiting|wait\s+(?:for|on)|in\s+progress|notif\w*|queued|"
                       r"still\s+runs?)\b", re.IGNORECASE)
_WEEKDAY = r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
_MONTH = (r"(?:january|february|march|april|may|june|july|august|september|october|november|december|"
          r"jan|feb|mar|apr|jun|jul|aug|sept?|oct|nov|dec)")
# A date or clock the step waits on. The month form has no period after an abbreviation: SENTENCE_END splits there.
TIME_GATE = re.compile(
    r"\b(?:(?:on|by)\s+" + _WEEKDAY + r"|(?:on|by)\s+" + _MONTH + r"\s+\d{1,2}(?:st|nd|rd|th)?|"
    r"at\s+\d{1,2}(?::\d{2})?\s*[ap]\.?m|at\s+\d{1,2}:\d{2}|at\s+:\d{2}|tomorrow|tonight|the\s+next\s+time)\b",
    re.IGNORECASE)
# `later <word ending in s>`: the step waits on events to come. Words that end in s but are no plural noun are out.
LATER_EVENT = re.compile(
    r"\blater\s+(?!(?:this|its|is|was|as|perhaps|always|anyways|sometimes|besides|versus|"
    r"afterwards|towards|yes|thus|plus|does|has|us|whereas|his|hers|ours|theirs|nowadays|upstairs|"
    r"downstairs|alas)\b)\w+(?<!s)s\b",
    re.IGNORECASE)
# The step acts on another party's notice.
OTHER_PARTY_RESULT = re.compile(r"\bact\s+on\s+(?:its|their|the)\s+(?:\w+\s+){0,2}(?:notice|result|report)s?\b",
                                re.IGNORECASE)
# The text right after a first-person announcement negates it, in one of two allowed forms; every other negation
# blocks. (1) At most one start word, then `no`, `nothing` or `none` ("I'm starting no lane", "I'll start
# nothing"). (2) `not` then a start word or `act` ("I will not act on it"). In both forms, an idiom word anywhere
# after the announcement blocks ("I'll do nothing but rerun it", "I'll not start it save for the docs").
_START_WORD = r"(?:start|begin|do|launch|open|run|touch|take|send|make)"
_NEGATION_IDIOM = (r"(?:but|except|besides|beyond|apart|aside|other|more|fewer|less|doubt|longer|long|short|save|"
                   r"than|yet|later|till|first|for\s+now|for\s+the\s+moment|at\s+the\s+moment|"
                   r"for\s+the\s+time\s+being|right\s+now|soon|shortly|eventually|afterwards)")
NEGATION_IDIOM_ANYWHERE = re.compile(r"\b" + _NEGATION_IDIOM + r"\b", re.IGNORECASE)
ANNOUNCEMENT_NEGATION = re.compile(
    r"\A\s*(?:(?:" + _START_WORD + r"\s+)?(?:no|nothing|none)(?![-\w])"
    r"|not\s+(?:" + _START_WORD + r"|act)\b)", re.IGNORECASE)
# A list marker: `1.`, `2)`, `-`, `*`, `+`.
_LIST_MARKER = r"(?:\d+[.)]|[-*+])"
# A sentence that opens on Then or Next: it follows the sentence before it. `Next steps:` is a header, not a chain.
CHAINED_STEP = re.compile(r"\A\s*(?:" + _LIST_MARKER + r"\s*)*(?:then|next)\b(?!\s+steps\b)", re.IGNORECASE)
# A sentence that is only a list marker: SENTENCE_END splits `1.` off its item, and leaves any marker that stands
# alone on its line as a sentence of its own.
LIST_MARKER_ONLY = re.compile(r"\A\s*" + _LIST_MARKER + r"\s*\Z")
# `<request> and I'll ...` with no `I` or `we` before `and`: the step waits on the request.
REQUEST_THEN_STEP = re.compile(r"\band\s+I(?:'|\N{RIGHT SINGLE QUOTATION MARK})ll\b|\band\s+I\s+will\b",
                               re.IGNORECASE)
FIRST_PERSON = re.compile(r"\b(?:I|we)\b", re.IGNORECASE)
SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")

REASON = ("Your message says you will do, or are doing, a step, but the turn is ending with nothing started. "
          "Start that step now with a tool call, or say plainly that it has not started and who acts next.")


def announces_report(sentence, announcement):
    """Whether the announced action of a first-person sentence is a report word, with no second step joined by
    `and`."""
    after_announcement = sentence[announcement.end():]
    if not REPORT_ACTION.match(after_announcement):
        return False
    return not SECOND_STEP.search(after_announcement)


def negated(sentence):
    """Whether every announcement in a sentence is first-person and negated (`ANNOUNCEMENT_NEGATION`): it says no
    step starts."""
    if PROGRESS_ANNOUNCEMENT.search(sentence):
        return False
    announcements = list(FIRST_PERSON_ANNOUNCEMENT.finditer(sentence))
    if not announcements:
        return False
    for announcement in announcements:
        after_announcement = sentence[announcement.end():]
        if not ANNOUNCEMENT_NEGATION.match(after_announcement):
            return False
        if CLAUSE_JOIN.search(after_announcement):
            return False
        if NEGATION_IDIOM_ANYWHERE.search(after_announcement):
            return False
    return True


def gated(sentence):
    """Whether a sentence names a condition, another actor, running work, a date or clock, later events or another
    party's notice: the step it holds waits on something."""
    gates = (CONDITION, OTHER_ACTOR, WORK_RUNS, TIME_GATE, LATER_EVENT, OTHER_PARTY_RESULT)
    return any(gate.search(sentence) for gate in gates)


def announced_step(message, transcript_path=None):
    """The first sentence of a final message that announces a step that neither `gated` nor `negated` passes and
    that is not chained to a gated sentence, or None. A Then or Next sentence passes after a gated one. A
    progress-only sentence, or a first-person one whose announced action is a report word (`announces_report`),
    passes when the current turn of the transcript launched background work."""
    unquoted_message = without_quoted_spans(ANNOUNCEMENT, without_draft_blocks(message))
    background_launched = None
    previous_gated = False
    for sentence in SENTENCE_END.split(unquoted_message):
        if LIST_MARKER_ONLY.match(sentence):
            continue
        if CHAINED_STEP.match(sentence) and previous_gated:
            continue
        sentence_gated = gated(sentence)
        previous_gated = sentence_gated
        if not ANNOUNCEMENT.search(sentence):
            continue
        if sentence.rstrip().endswith("?"):
            continue
        if sentence_gated or negated(sentence):
            continue
        request = REQUEST_THEN_STEP.search(sentence)
        if request and not FIRST_PERSON.search(sentence[:request.start()]):
            continue
        announcement = FIRST_PERSON_ANNOUNCEMENT.search(sentence)
        if announcement and not announces_report(sentence, announcement):
            return sentence.strip()
        if background_launched is None:
            background_launched = user_prompts.turn_launched_background(transcript_path)
        if background_launched:
            continue
        return sentence.strip()
    return None
