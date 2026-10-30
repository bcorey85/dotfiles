"""code_step_usage.py: the usage text of every verb of code_step.py, and the leading-dash check of `resume`.
`<verb> --help` prints that verb's usage and exits 0 before a verb reads or changes any state; `start` keeps its own
parser in code_step_start_args.

Imports run one way: script_utils, code_step_usage, then code_step_boundary and code_step_review, then code_step."""
import sys

import plan_format
import script_utils

ANSWER_USAGE = ('usage: code_step.py resume ["<the user\'s answer to the stopped coder>"]\n'
                'Goes on with the saved run, whatever stage or stop it is in. Only a coder that waits for the user\'s '
                'answer takes one, and the answer must not start with "-".')
VERB_USAGES = {
    "resume": ANSWER_USAGE,
    "decide": f"usage: code_step.py {plan_format.DECIDE_USAGE_STEM}\n       code_step.py decide discuss",
    "asks-done": ('usage: code_step.py asks-done [--repo <path>] [--by <user|session>] [--also "<text>"] '
                  '<accepted|rejected|modified>...\n'
                  'One outcome per ask, in order. --also carries other work the user named alongside the outcomes '
                  'to the coder. --repo names the checkout of the run that waits, when the shell is in none of them.'),
    "correct-ruling": ('usage: code_step.py correct-ruling [--repo <path>] [--by <user|session>] [--also "<text>"] '
                       '<accepted|rejected|modified>...\n'
                       'The same words as asks-done, to correct the rulings while the asks coder runs.'),
    "skill-done": ('usage: code_step.py skill-done <pass|fail> [--evidence "<text>"]... [--finding "<text>"]...\n'
                   'A closing phase\'s skill returned.'),
    "verify": ("usage: code_step.py verify\nRuns the phase gates and closes the phase, after a failed Automated "
               "Verification was fixed or once the phase's review converged."),
    "review-again": ("usage: code_step.py review-again\n"
                     "Dispatches the review loop again on the same diff, after a stop that names it."),
    "tick": "usage: code_step.py tick <phase id>\nMarks a phase done that the user finished outside /code.",
    "abort": "usage: code_step.py abort\nEnds the open run on purpose. The working tree stays as it is.",
    "guide": ('usage: code_step.py guide "<text>"\nRecords the main session\'s guidance in the open run. Every later '
              'coder and review dispatch carries it. It changes neither the task nor the plan.'),
    "status": "usage: code_step.py status\nPrints the saved state.",
    "plan": "usage: code_step.py plan check [--final]|parse <path>",
}
HOOK_USAGE = "usage: code_step.py {verb}\nA hook: it reads the hook event as JSON on stdin and takes no arguments."


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
    # Exits 2 with the usage on a refused argument; returns nothing. Only resume checks its words; every other verb
    # keeps its words as they are. Only the first word decides: an answer may hold a dashed later word (`use -v`).
    if verb == "resume" and args and args[0].startswith("-"):
        print(f"code_step.py resume: an answer must not start with '-': {args[0]!r}\n{ANSWER_USAGE}", file=sys.stderr)
        sys.exit(2)
