"""The closing permission question of a final message, for the Stop hook in staged_claim_gate.py.

A message ends on a permission question when its last 400 characters hold a question that asks to go on: `want me
to`, `do you want that|this|it|them|those|these ...`, `shall I`, `should I`, `would you like me to`, `okay to
proceed`, `go ahead and`, `ready to`. A question that names a step that leaves the machine or does not undo
(commit, push, merge, deploy, publish, release, delete, drop, reset, rebase, force, send, email, post, install,
upgrade, migrate) is one to ask and does not count.
"""
import re

PERMISSION_QUESTION = re.compile(
    r"\b(?:(?:do you |would you )?want me to|do you want (?:that|this|it|them|those|these)\b|shall I|"
    r"should I(?: go ahead| proceed)?|would you like me to|ok(?:ay)? to (?:proceed|go ahead)|go ahead and|"
    r"ready (?:for me )?to)\b[^?]*\?",
    re.IGNORECASE)
OUTWARD_STEP = re.compile(
    r"\b(?:commit|push|merge|deploy|publish|release|delete|drop|reset|rebase|force|send|e-?mail|post|install|"
    r"upgrade|migrate)\w*",
    re.IGNORECASE)
TAIL_CHARACTERS = 400
REASON = ("Your message ends asking permission to go on. Act on it: take the step yourself. Ask only before a step "
          "that cannot be undone or leaves this machine.")


def closing_question(message):
    """The last permission question in the message's tail that names no outward step, or None."""
    tail = message.strip()[-TAIL_CHARACTERS:]
    questions = [match.group(0) for match in PERMISSION_QUESTION.finditer(tail)]
    if not questions:
        return None

    last_question = questions[-1]
    if OUTWARD_STEP.search(last_question):
        return None
    return last_question
