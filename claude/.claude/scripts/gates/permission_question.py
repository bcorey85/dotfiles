"""The closing permission question of a final message, for the Stop hook in staged_claim_gate.py.

A message ends on a permission question when its last 400 characters (counted after quoted questions are dropped)
hold a question that asks to go on: `want me to`, `do you want that|this|it|them|those|these ...`, `shall I`,
`should I`, `would you like me to`, `okay to proceed`, `go ahead and`, `ready to`, with no sentence end (`.` or `!`
before a space) between the phrase and the `?`. A question that names a step that leaves the machine or does not undo
(commit, push, merge, deploy, publish, release, delete, drop, reset, rebase, force, send, email, post, install,
upgrade, migrate, void, cancel, refund, revoke, submit, approve, archive, remove, overwrite, wipe, purge, truncate,
destroy, reply, notify, message, ping),
that files, opens, creates or raises a ticket, sub-ticket, subtask, issue, sub-issue, pull request or merge request
(a bare `task` does not count), that names Slack, or that files, opens, creates or raises
`them|these|those|this|it|each` in/on/to/into Jira, Linear or GitHub (the pronoun comes right after the verb), is one
to ask and does not count. A span in backticks or double quotes (straight or curly) on one line whose
whole text is one permission question is dropped first (`message_text.without_quoted_spans`): a question cited as
an example is no question asked.
"""
import re

from message_text import without_quoted_spans

PERMISSION_QUESTION = re.compile(
    r"\b(?:(?:do you |would you )?want me to|do you want (?:that|this|it|them|those|these)\b|shall I|"
    r"should I(?: go ahead| proceed)?|would you like me to|ok(?:ay)? to (?:proceed|go ahead)|go ahead and|"
    r"ready (?:for me )?to)\b(?:[^?.!]|[.!](?!\s))*\?",
    re.IGNORECASE)
OUTWARD_STEP = re.compile(
    r"\b(?:commit|push|merge|deploy|publish|release|delete|drop|reset|rebase|force|send|e-?mail|post|install|"
    r"upgrade|migrate|void|cancel|refund|revoke|submit|approve|archive|remove|overwrite|wipe|purge|truncate|destroy|"
    r"reply|replies|notify|message|ping)\w*"
    r"|\b(?:file|open|create|raise)\s+(?:an?\s+|the\s+)?(?:[\w-]+\s+){0,2}"
    r"(?:(?:sub-?)?(?:tickets?|issues?)|sub-?tasks?|pull\s+requests?|PRs?|MRs?)\b|\bslack\b"
    r"|\b(?:file|open|create|raise)\s+(?:them|these|those|this|it|each)\s+(?:in|on|to|into)\s+(?:jira|linear|github)\b",
    re.IGNORECASE)
# A quoted span counts as a cited question only when its whole inner text is the question.
OPENING_QUESTION = re.compile(r"\A(?:" + PERMISSION_QUESTION.pattern + r")\s*\Z", re.IGNORECASE)
TAIL_CHARACTERS = 400
REASON = ("Your message ends asking permission to go on. Act on it: take the step yourself. Ask only before a step "
          "that cannot be undone or leaves this machine.")


def closing_question(message):
    """The last permission question in the message's tail that names no outward step, or None."""
    unquoted_message = without_quoted_spans(OPENING_QUESTION, message.strip())
    tail = unquoted_message[-TAIL_CHARACTERS:]
    questions = [match.group(0) for match in PERMISSION_QUESTION.finditer(tail)]
    if not questions:
        return None

    last_question = questions[-1]
    if OUTWARD_STEP.search(last_question):
        return None
    return last_question
