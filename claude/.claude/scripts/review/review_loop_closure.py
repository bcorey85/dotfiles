"""The review loop's class-closure check: the per-path stats of what the fix coder changed, and the model call that
asks whether each fixed finding's class is closed."""

import pathlib
import sys

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent)]
from review_loop_findings import reply_with_one_retry

NO_CLOSURE = "n/a - fixed[] empty"

CLOSURE_RULES = (
    'For each finding in fixed[], ask whether it is class-shaped: one member of an enumerable set of '
    'ways the same mistake can occur. Two shapes qualify:\n'
    '- Enumerable exit/branch space: the fix touched one of N exits, cases, or branches, and the other '
    'N-1 were never re-read. Close it by re-enumerating them and stating where each one lands.\n'
    '- Proxy predicate: the fix removed a cheap check standing in for the property actually needed. '
    'Close it by naming the other members that proxy was covering for.\n'
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


def closure_check(repo, out, fixed, claude_call):
    """The closure call's receipt and open findings. `claude_call` is the loop's model step."""
    if not fixed:
        return {"receipt": NO_CLOSURE, "open": []}
    prompt = (
        f"Repo root: {repo}\n\n{CLOSURE_RULES}\n\nfixed[]:\n" + "\n".join(f"- {item}" for item in fixed)
        + f"\n\nWhat the coder changed, one diff file per path under {out / 'fix-diffs'} (path, lines added and "
        "removed, diff file). Read only the diff files for paths a fixed[] finding names; never read a path marked "
        "regenerated.\n" + "\n".join(diff_stat_lines(FIX_DIFF_STATS))
        + '\n\nEnd your reply with one JSON object: {"receipt": "<the enumeration, or none plus each fixed finding '
        'and why it fits neither shape>", '
        '"open": ["<file:line - defect - correction>", ...]}. "open" is empty when every class is closed.'
    )
    parsed = reply_with_one_retry(claude_call, "class-closure", prompt, repo, out, ("open",),
                                  '{"receipt": .., "open": [..]}', model="sonnet", tools="Read,Grep")
    parsed_open = parsed.get("open")
    open_findings = ([item for item in parsed_open if isinstance(item, str) and item.strip()]
                     if isinstance(parsed_open, list) else [])
    return {"receipt": str(parsed.get("receipt", "")), "open": open_findings}
