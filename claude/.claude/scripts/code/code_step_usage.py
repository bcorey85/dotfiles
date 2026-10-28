"""code_step_usage.py: the usage text of every verb of code_step.py, and the argument parser of `resume`.
`<verb> --help` prints that verb's usage and exits 0 before a verb reads or changes any state; `start` keeps its own
parser in code_step_start_args.

Imports run one way: script_utils, code_step_usage, then code_step_boundary and code_step_review, then code_step."""
import argparse
import sys

import script_utils

DECIDE_COMMAND = 'decide <adopt|keep> --by <user|session> --ruling "<the decision in one line>"'
ANSWER_USAGE = ('usage: code_step.py resume ["<the user\'s answer to the stopped coder>"]\n'
                'Goes on with the saved run, whatever stage or stop it is in. Only a coder that waits for the user\'s '
                'answer takes one, and the answer must not start with "-".')
VERB_USAGES = {
    "resume": ANSWER_USAGE,
    "decide": f"usage: code_step.py {DECIDE_COMMAND}\n       code_step.py decide discuss",
    "asks-done": ('usage: code_step.py asks-done [--by <user|session>] <accepted|rejected|modified>...\n'
                  'One outcome per ask, in order.'),
    "skill-done": ('usage: code_step.py skill-done <pass|fail> [--evidence "<text>"]... [--finding "<text>"]...\n'
                   'A closing phase\'s skill returned.'),
    "verify": "usage: code_step.py verify\nRe-runs the phase gates after a failed Automated Verification was fixed.",
    "review-again": ("usage: code_step.py review-again\n"
                     "Dispatches the review loop again on the same diff, after a stop that names it."),
    "tick": "usage: code_step.py tick <phase id>\nMarks a phase done that the user finished outside /code.",
    "abort": "usage: code_step.py abort\nEnds the open run on purpose. The working tree stays as it is.",
    "status": "usage: code_step.py status\nPrints the saved state.",
    "plan": "usage: code_step.py plan check [--final]|parse <path>",
}
HOOK_USAGE = "usage: code_step.py {verb}\nA hook: it reads the hook event as JSON on stdin and takes no arguments."


def answer_word(word):
    if word.startswith("-"):
        raise argparse.ArgumentTypeError(f"an answer must not start with '-': {word!r}")
    return word


class VerbParser(argparse.ArgumentParser):
    def error(self, message):
        print(f"code_step.py {self.prog}: {message}\n{self.usage}", file=sys.stderr)
        sys.exit(2)


def resume_parser():
    parser = VerbParser(prog="resume", usage=ANSWER_USAGE, add_help=False, allow_abbrev=False)
    # Only the first word decides: an answer may hold a dashed word later (`use the -v flag`).
    parser.add_argument("first_answer_word", nargs="?", type=answer_word)
    parser.add_argument("other_answer_words", nargs="*")
    return parser


def usage_text(verb, is_hook=False):
    # The usage of a verb, or None for a verb that prints its own (start) or has none.
    if is_hook:
        return HOOK_USAGE.format(verb=verb)
    return VERB_USAGES.get(verb)


def print_usage_if_asked(verb, args, is_hook=False):
    # True after printing the verb's usage for a `--help` or `-h` argument; the caller then changes nothing.
    text = usage_text(verb, is_hook)
    if text is None or not script_utils.usage_requested(args):
        return False
    print(text)
    return True


def check_verb_arguments(verb, args):
    # Exits 2 with the usage on a refused argument; returns nothing. Only resume reads its words with a strict grammar;
    # every other verb keeps its words as they are.
    if verb == "resume":
        # "--" makes every word an answer word, so a mistyped flag gets the dash refusal, not a bare "unrecognized".
        resume_parser().parse_args(["--", *args])
