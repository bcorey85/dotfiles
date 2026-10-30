"""The verdict on one Automated Verification item after its command ran: the one rule that /code's verification and the
plan-criteria dry run both apply, so a plan item reads the same in both. Pure: it runs nothing and writes nothing."""
import re
from typing import NamedTuple

import script_utils
from check_output import FAILED_EXIT_ZERO, NO_TEST_MATCHED_NOTE, NO_TESTS_RAN, SUMMARY_FAILURE_NOTE, check_verdict
from test_run_output import matches_no_test

# A run that exits 0 but ran no test, or whose runner summary reports failures, fails the box.
NO_TEST_MATCHED_EXIT_CODE = 1
NO_TEST_MATCHED_FLAG = "matches no test: the run exits 0 but ran no test, so it reads RED until a test exists"
# An rg, grep or git grep line is a ban (exit 1, no match, holds it) unless its text, outside the command, says it
# checks presence (exit 0 passes). Ban wording on the same line wins. A search wrapped in another command, such as
# `test -n "$(git grep ...)"`, is judged by its own exit code.
SEARCH_COMMAND = re.compile(r"^(?:rg|grep|egrep|git grep)\s")
BAN_WORDING = re.compile(r"\bprohibition\b|\bno\s+(?:match(?:es)?|output|hits?)\b|\bprints?\s+nothing\b"
                         r"|\bexit(?:s|ing)?\s+(?:code\s+)?1\b|\babsent\b|\bmust\s+not\b|\bnone\b|\bnothing\b"
                         r"|\bgone\b|\bremoved\b|\bzero\b|\bno\s+longer\b",
                         re.IGNORECASE)
PRESENCE_WORDING = re.compile(r"\bpresence\b|\bpresent\b|\bexists?\b|\bcontains?\b|\bdefines?\b|\bdefined\b"
                              r"|\bfinds?\b|\bfound\b|\ba\s+hit\b|\bmatches\b", re.IGNORECASE)
SEARCH_BAN_NOTE = ("\nan rg, grep or git grep line is a ban unless its text says it checks presence "
                   "(present, exists, contains, finds)\n")
# A ban written `! rg ...` is the same ban as `rg ...`: no match holds it.
# A leading `cd <dir> &&` does not change what the command searches: it stays in the command and is ignored here.
LEADING_CD = r"(?:cd \S+ && )?"
NEGATED_SEARCH = re.compile(r"^(" + LEADING_CD + r")!\s+(?=(?:rg|grep|egrep|git grep)\s)")
# Exit codes that mean the command did not run to an answer.
NOT_RUN_EXIT_CODES = (script_utils.COMMAND_NOT_FOUND_EXIT_CODE, script_utils.TIMEOUT_EXIT_CODE)


class ItemVerdict(NamedTuple):
    """outcome: GREEN, RED or BROKEN. code: the exit-style verdict (0 holds, anything else fails), output: the command's
    output with any note on why it failed, hits: the number of matches of a search ban (None for any other item), flag:
    the dry-run flag text for a zero-test match (else None)."""
    outcome: str
    code: int
    output: str
    hits: int | None
    flag: str | None


def without_negation(span):
    """The span with the `!` of a negated search taken off, any leading `cd <dir> &&` kept."""
    return NEGATED_SEARCH.sub(r"\1", span)


def without_leading_cd_and_env(command):
    """The command with any NAME=value words and a `cd <dir> &&` it starts with taken off, for judging what it is."""
    unassigned = script_utils.without_leading_env_assignments(command)
    return re.sub(r"^cd \S+ && ", "", unassigned)


def is_search_ban(command, line):
    """True when the item is an rg, grep or git grep line that holds on no match."""
    if not SEARCH_COMMAND.match(without_leading_cd_and_env(command)):
        return False

    if any(without_negation(span) == command and span != command for span in script_utils.backticked_spans(line)):
        return True

    text = line.replace(command, "")
    if BAN_WORDING.search(text):
        return True

    return not PRESENCE_WORDING.search(text)


def ban_verdict(command, code, output):
    """(exit-style verdict, hit count) of a search ban. A plain search passes on exit 1 (no match) and fails on exit 0
    (a hit); any other exit is an error that stops. A pipe form is judged by its output: empty or 0 passes."""
    hit_rows = len([row for row in output.splitlines() if row.strip()])
    if "|" in command:
        if output.strip() in ("", "0"):
            return 0, 0
        hits = int(output) if output.strip().isdigit() else hit_rows
        return 1, hits

    if code == 1:
        return 0, 0

    if code == 0:
        return 1, hit_rows

    return code, 0


def item_verdict(command, line, code, output):
    """Judge one item whose command ran with exit `code` and `output`. `line` is the plan item's text. An exit that
    says the command did not run (not found, timed out) keeps the exit-style verdict, but reads BROKEN."""
    verdict = judge_item(command, line, code, output)
    if code in NOT_RUN_EXIT_CODES:
        return verdict._replace(outcome="BROKEN")

    return verdict


def judge_item(command, line, code, output):
    """The verdict on one item by its command's exit code and output, before the did-not-run exits read BROKEN."""
    if is_search_ban(command, line):
        verdict, hits = ban_verdict(command, code, output)
        if verdict != 0 and not PRESENCE_WORDING.search(line.replace(command, "")):
            output += SEARCH_BAN_NOTE
        if verdict == 0:
            outcome = "GREEN"
        elif code in (0, 1) or "|" in command:
            outcome = "RED"
        else:
            outcome = "BROKEN"

        return ItemVerdict(outcome, verdict, output, hits, None)

    verdict = check_verdict(command, code, output)
    if verdict == FAILED_EXIT_ZERO:
        return ItemVerdict("RED", NO_TEST_MATCHED_EXIT_CODE, output + SUMMARY_FAILURE_NOTE, None, None)

    # matches_no_test also judges a command that only names a filtered runner without running it as a test (a search,
    # a print) or negates it, which check_verdict leaves alone: a command that names a runner and matches TEST_FILTER
    # (`-k`, `-t`), or a step that runs `cargo test` on a name, with no passed test, is RED, so a presence search for
    # `pytest -k foo` reads RED too.
    # `cargo test` named only in another step's words (`echo cargo test x`) stays GREEN.
    if verdict == NO_TESTS_RAN or matches_no_test(command, code, output):
        return ItemVerdict("RED", NO_TEST_MATCHED_EXIT_CODE, output + NO_TEST_MATCHED_NOTE, None, NO_TEST_MATCHED_FLAG)

    return ItemVerdict("GREEN" if code == 0 else "RED", code, output, None, None)
