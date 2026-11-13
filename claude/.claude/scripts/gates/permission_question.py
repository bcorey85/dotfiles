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
`them|these|those|this|it|each` in/on/to/into Jira, Linear or GitHub (the pronoun comes right after the verb), that
says `public` or `publicly`, or that names an outside destination after `to`, `on`, `in` or `off` with at most two
words between (PR, MR, pull request, merge request, issue, ticket, thread, upstream, `#<number>`; Jira, which has its
own branch that takes a `.com`, `.io` or `.app` suffix as a host name; GitHub, GitLab
and case-sensitive Linear after `to`, `in` or `off` only, so `look it up on GitHub` stays a local step; GitHub,
GitLab or Linear followed by actions, workflows, cli, pages, docs, api, copilot, desktop, codespaces, packages, gist
or interpolation is local; every OUTWARD_STEP branch that names a destination has no word character or `-`, and no
`.` or `/` followed by a word character, right after it, so a file such as `issues.py` or `github.py` is local; on
the Slack branch, the pronoun branch (Jira, Linear, GitHub) and the GitHub, GitLab and Linear branch a `.com`, `.io`
or `.app` suffix is no file name, so `github.com`, `gitlab.com`, `slack.com` and a capitalised `Linear.app` count as
outside destinations (the pronoun branch also matches lowercase `linear.app`); the outward-step search starts
after the opening phrase, so the `to` of `want me to`, `ready to` and `do you want it to` is no preposition, and
neither is `to` after try, start, begin, need, have or going), is one to ask and does not count.
A span in backticks or double quotes (straight or curly) on one line whose whole text is one permission
question is dropped first (`message_text.without_quoted_spans`): a question cited as an example is no question asked.

A reply to a user prompt that asks a question passes (`answers_users_question`): the answer stands, offer and all. The
prompt asks when the user's own words hold a `?` or open on a question word, and do not open on a request such as `can
you` or `please`. A transcript that cannot be read gives no prompt, so the message is judged alone.
"""
import re

from message_text import without_quoted_spans
from user_prompts import latest_prompt, user_words

PERMISSION_QUESTION = re.compile(
    r"\b(?P<opening>(?:do you |would you )?want me to|do you want (?:that|this|it|them|those|these)(?: to)?|shall I|"
    r"should I(?: go ahead| proceed)?|would you like me to|ok(?:ay)? to (?:proceed|go ahead)|go ahead and|"
    r"ready (?:for me )?to)\b(?:[^?.!]|[.!](?!\s))*\?",
    re.IGNORECASE)
# A `to` after these verbs is an infinitive (`try to fix`), not a preposition.
INFINITIVE_LEAD_IN = r"(?<!\btry )(?<!\bstart )(?<!\bbegin )(?<!\bneed )(?<!\bhave )(?<!\bgoing )"
# What may follow a destination name: a file name (`issues.py`, `github-x`, `a/b`) means a local file.
FILE_NAME_AFTER = r"(?![\w-]|[./]\w)"
# Same, except a `.com`, `.io` or `.app` suffix is a host name, so `github.com` stays a destination.
HOST_NAME_AFTER = r"(?![\w-]|/\w|\.(?!(?:com|io|app)\b)\w)"
# Up to two words may sit between a destination preposition and the destination name (`on the main PR`).
WORDS_BEFORE_DESTINATION = r"\s+(?:[\w-]+\s+){0,2}"
OUTWARD_STEP = re.compile(
    r"\b(?:commit|push|merge|deploy|publish|release|delete|drop|reset|rebase|force|send|e-?mail|post|install|"
    r"upgrade|migrate|void|cancel|refund|revoke|submit|approve|archive|remove|overwrite|wipe|purge|truncate|destroy|"
    r"reply|replies|notify|message|ping)\w*"
    r"|\b(?:file|open|create|raise)\s+(?:an?\s+|the\s+)?(?:[\w-]+\s+){0,2}"
    r"(?:(?:sub-?)?(?:tickets?|issues?)|sub-?tasks?|pull\s+requests?|PRs?|MRs?)" + FILE_NAME_AFTER +
    r"|\bslack" + HOST_NAME_AFTER +
    r"|\b(?:file|open|create|raise)\s+(?:them|these|those|this|it|each)\s+(?:in|on|to|into)\s+(?:jira|linear|github)"
    + HOST_NAME_AFTER +
    r"|\b(?:publicly|public)\b(?![./]\w)"
    r"|\b" + INFINITIVE_LEAD_IN + r"(?:to|on|in|off)" + WORDS_BEFORE_DESTINATION +
    r"(?:PRs?|MRs?|pull\s+requests?|merge\s+requests?|"
    r"issues?|tickets?|threads?|upstream|#\d+)" + FILE_NAME_AFTER +
    r"|\b" + INFINITIVE_LEAD_IN + r"(?:to|on|in|off)" + WORDS_BEFORE_DESTINATION + r"jira" + HOST_NAME_AFTER +
    r"|\b" + INFINITIVE_LEAD_IN + r"(?:to|in|off)" + WORDS_BEFORE_DESTINATION +
    r"(?:git(?:hub|lab)|(?-i:Linear))" + HOST_NAME_AFTER +
    r"(?!\s+(?:actions|workflows?|cli|pages|docs|api|copilot|desktop|codespaces|packages|gist|interpolation)\b)",
    re.IGNORECASE)
# A quoted span counts as a cited question only when its whole inner text is the question.
OPENING_QUESTION = re.compile(r"\A(?:" + PERMISSION_QUESTION.pattern + r")\Z", re.IGNORECASE)
TAIL_CHARACTERS = 400
REQUEST_OPENING = re.compile(r"\A\W*(?:(?:can|could|would|will) you|please)\b", re.IGNORECASE)
QUESTION_OPENING = re.compile(
    r"\A\W*(?:what|why|how|when|where|which|who|whose|is|are|was|were|do|does|did|can|could|will|would|should|"
    r"has|have|any|whats|hows|isnt|doesnt)\b", re.IGNORECASE)
REASON = ("Your message ends asking permission to go on. Send it again without that closing question. Do not start "
          "the step it offers unless the user's request already covers it. Ask only before a step that cannot be "
          "undone or leaves this machine.")


def asks_a_question(prompt):
    """Whether the user's own words in a prompt ask a question rather than hand over a task."""
    words = user_words(prompt).strip()
    if REQUEST_OPENING.match(words):
        return False
    return "?" in words or bool(QUESTION_OPENING.match(words))


def answers_users_question(transcript_path):
    """Whether the newest prompt the user typed asks a question; False when the transcript cannot be read."""
    if not transcript_path:
        return False
    prompt = latest_prompt(transcript_path)
    if prompt is None:
        return False
    return asks_a_question(prompt)


def closing_question(message):
    """The last permission question in the message's tail that names no outward step, or None."""
    unquoted_message = without_quoted_spans(OPENING_QUESTION, message.strip())
    tail = unquoted_message[-TAIL_CHARACTERS:]
    matches = list(PERMISSION_QUESTION.finditer(tail))
    if not matches:
        return None

    last_match = matches[-1]
    # The opening phrase is not searched: its `to` is an infinitive, not a destination.
    asked_step = last_match.group(0)[last_match.end("opening") - last_match.start():]
    if OUTWARD_STEP.search(asked_step):
        return None
    return last_match.group(0)
