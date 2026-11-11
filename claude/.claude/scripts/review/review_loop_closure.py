"""The review loop's class-closure check: the per-path stats of what the fix coder changed, and the model call that
asks whether each fixed finding's class is closed."""

import dataclasses
import json
import pathlib
import re
import sys

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / folder) for folder in (".", "../lib")]
import script_utils
from review_loop_findings import reply_with_one_retry

NO_CLOSURE = "n/a - fixed[] empty"


@dataclasses.dataclass
class ClosureState:
    """What the class-closure pass leaves for the outcome builder to read."""

    receipt: str = NO_CLOSURE
    open_classes: list = dataclasses.field(default_factory=list)  # the members the repair pass left unfixed
    left_alone: list = dataclasses.field(default_factory=list)  # members that read the value for another purpose


OPEN_KEY = re.compile(r'"open"\s*:\s*(?=\[)')
LEFT_ALONE_KEY = re.compile(r'"left_alone"\s*:\s*(?=\[)')
RECEIPT_KEY = re.compile(r'^"receipt"\s*:\s*')

CLOSURE_RULES = (
    'For each finding in fixed[], ask whether it is class-shaped: one member of an enumerable set of '
    'ways the same mistake can occur. Two shapes qualify:\n'
    '- Enumerable exit/branch space: the fix touched one of N exits, cases, or branches, and the other '
    'N-1 were never re-read. Close it by re-enumerating them and stating where each one lands.\n'
    '- Proxy predicate: the fix removed a cheap check standing in for the property actually needed. '
    'Close it by naming the other members that proxy was covering for.\n'
    'Before you call a member open, say what it reads the value for, next to what the fixed line reads it for. '
    'A member that reads the value for a different purpose than the fixed line is not in the class: leave it, and '
    'list it under left_alone with that purpose. Never list it as open.\n'
    'Work from the fix diff files; read a repo file only to see a member the diff does not show. If a fixed finding '
    'is class-shaped and the class is NOT closed (some member still has the defect), list those members '
    'as open findings, each with file and line and the one correction. You may not edit files.'
)

# One entry per path a coder call changed: {"path", "added", "removed", "diff_file"}. Feeds the class-closure check,
# which names the diff files in its prompt and never inlines their text.
FIX_DIFF_STATS = []
# Folders whose files a tool regenerates: a closure call has no reason to read their diffs.
GENERATED_DIRS = ("generated",)


def is_generated_path(path):
    """Whether the path sits under a folder a tool regenerates."""
    return any(part in GENERATED_DIRS for part in pathlib.PurePosixPath(path).parts[:-1])


def diff_stat_lines(stats):
    """One line per changed path: its path, lines added and removed, and the file holding its diff."""
    lines = []
    for stat in stats:
        counts = f"+{stat['added']} -{stat['removed']}"
        if is_generated_path(stat["path"]):
            lines.append(f"- {stat['path']} ({counts}): regenerated, do not read")
        else:
            lines.append(f"- {stat['path']} ({counts}): {stat['diff_file']}")
    return lines


def held_clause(held_texts):
    """The receipt's tail naming the class members skipped because another session holds their file; empty when none."""
    if not held_texts:
        return ""
    return "; skipped, held by another session: " + "; ".join(held_texts)


def receipt_after_class_repair(closed_members, held_texts):
    """The closure receipt once the class-fix coder changed a file. It names only the members sent to the coder, so
    members skipped as held are not claimed fixed. It replaces the check's receipt, whose prose still calls the sent
    members open."""
    return ("the class repair fixed these class members the closure check found open: " + "; ".join(closed_members)
            + held_clause(held_texts))


def receipt_all_held(held_texts):
    """The closure receipt when every open class member is in a held file, so no coder ran."""
    return ("every open class member is in a file another session holds, so none went to a coder"
            + held_clause(held_texts))


def receipt_still_open(open_texts, held_texts):
    """The closure receipt when the class repair changed nothing. The check's receipt names the held members as open,
    so it is rebuilt from the members that stay open."""
    return ("class members still open, the class repair changed nothing: " + "; ".join(open_texts)
            + held_clause(held_texts))


def closure_check(repo, out, fixed, claude_call):
    """The closure call's receipt, open findings and the members it left alone. `claude_call` is the loop's model
    step."""
    if not fixed:
        return {"receipt": NO_CLOSURE, "open": [], "left_alone": []}
    prompt = (
        f"Repo root: {repo}\n\n{CLOSURE_RULES}\n\nfixed[]:\n" + "\n".join(f"- {item}" for item in fixed)
        + f"\n\nWhat the coder changed, one diff file per path under {out / 'fix-diffs'} (path, lines added and "
        "removed, diff file). Read only the diff files for paths a fixed[] finding names; never read a path marked "
        "regenerated.\n" + "\n".join(diff_stat_lines(FIX_DIFF_STATS))
        + '\n\nEnd your reply with one JSON object: {"receipt": "<the enumeration, or none plus each fixed finding '
        'and why it fits neither shape>", "open": ["<file:line - defect - correction>", ...], '
        '"left_alone": ["<file:line - what it reads the value for>", ...]}. "open" is empty when every class is '
        'closed; "left_alone" is empty when no member was left alone. It must parse as JSON: escape every double '
        'quote inside the receipt as \\".'
    )
    parsed = reply_with_one_retry(claude_call, "class-closure", prompt, repo, out, ("open",),
                                  '{"receipt": .., "open": [..], "left_alone": [..]}', recover=closure_from_open_list,
                                  problem=closure_list_problem, model="sonnet", tools="Read,Grep")
    return {"receipt": str(parsed.get("receipt", "")), "open": parsed["open"],
            "left_alone": parsed.get("left_alone", [])}


def closure_list_problem(parsed):
    """A sentence naming the first of `open` and `left_alone` that the reply holds and that is not a list of
    non-blank strings; None when both are fine."""
    for key in ("open", "left_alone"):
        if key in parsed and not script_utils.is_nonblank_string_list(parsed[key]):
            return f"'{key}' must be a list of non-blank strings"
    return None


def closure_from_open_list(reply):
    """The receipt, open list and left-alone list of a closure reply whose object does not decode, as when the
    receipt holds a raw double quote: decodes the lists after the last `"open": [` and the last `"left_alone": [`,
    and keeps the text after the `"receipt":` key, without its wrapping quotes, as the receipt. The left-alone
    list is empty when its key is absent. The receipt text stops at the first list key after it. None when
    no open list decodes or the left-alone list is present and does not decode."""
    open_found, parsed_open, open_key_start = list_after_last_key(reply, OPEN_KEY)
    if not open_found or parsed_open is None:
        return None

    left_alone_found, left_alone, left_alone_key_start = list_after_last_key(reply, LEFT_ALONE_KEY)
    if left_alone_found and left_alone is None:
        return None

    receipt_start = reply.rfind('"receipt"', 0, open_key_start)
    receipt_end = open_key_start
    if left_alone_found and receipt_start < left_alone_key_start < open_key_start:
        receipt_end = left_alone_key_start
    receipt_text = RECEIPT_KEY.sub("", reply[receipt_start:receipt_end]) if receipt_start >= 0 else ""
    receipt = receipt_text.strip().rstrip(",").strip()
    if len(receipt) > 1 and receipt.startswith('"') and receipt.endswith('"'):
        receipt = receipt[1:-1]

    return {"receipt": receipt, "open": parsed_open, "left_alone": left_alone if left_alone_found else []}


def list_after_last_key(reply, key_pattern):
    """(found, value, key_start) for the list after the last match of `key_pattern` in a reply. `found` is False when
    the key is absent; `value` is None when the key is present and its list does not decode."""
    keys = list(key_pattern.finditer(reply))
    if not keys:
        return False, None, -1

    last_key = keys[-1]
    try:
        value, _ = json.JSONDecoder().raw_decode(reply, last_key.end())
    except json.JSONDecodeError:
        return True, None, last_key.start()
    return True, value, last_key.start()
