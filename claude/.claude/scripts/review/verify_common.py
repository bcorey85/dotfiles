"""Shared helpers for verify-prep and verify-log: git, plan/ticket parsing, the review signal, the saved run context."""
import functools
import json
import os
import pathlib
import re
import sys

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent.parent / "lib")]
import plan_format
import reviewed_tree
import script_utils

TOOLKIT_DIR = pathlib.Path(__file__).resolve().parents[2]
STATE_ROOT = pathlib.Path.home() / ".claude" / "state"
REVIEW_MARKER = "verify-branch"
REVIEW_GATE = "code-reviewer"
# Accepted id spans: a plain id, an id followed by a parenthetical, an id with a qualifier inside the bold,
# or several comma-separated ids inside one bold span.
ID_LINE = re.compile(r"^\s*[-*]\s+\*\*(AC\d+[^*]*)\*\*\s*(?:\([^)]*\))?\s*[—–-]+\s*(.*)$")
# A line opens an id span at its start (after indent and an optional list marker). A bold `**ACn` later in a line
# that never closes (a status note saying `**AC4's part is OPEN**`) is prose.
ID_START = re.compile(r"^\s*(?:(?:[-*+]|\d+[.)])\s+)?(?:\[[ xX]\]\s+)?\*\*AC\d+")
# A closed bold id span anywhere in a line (a table cell, a quote, a prefix, a strikethrough) also marks a criterion
# line, so one that is written wrong fails instead of dropping out. Prose such as `**AC4's ...**` does not close.
ID_SPAN = re.compile(r"\*\*AC\d+(?:\s*\([^)]*\))?(?:,\s*AC\d+(?:\s*\([^)]*\))?)*\*\*")
AC_ID = re.compile(r"AC\d+")


class VerifyError(Exception):
    """A loud, expected failure: message to stderr, exit code `code`."""

    def __init__(self, message, code=2):
        super().__init__(message)
        self.code = code


run = functools.partial(script_utils.run_or_raise, error_type=VerifyError)
tree_fingerprint = functools.partial(reviewed_tree.tree_fingerprint, error_type=VerifyError)


def script_path(env_name, installed_relative):
    return os.environ.get(env_name) or str(TOOLKIT_DIR / installed_relative)


# ---------- markdown parsing ----------

def raising_verify_error(plan_reader):
    """The reader, with the PlanFormatError it raises raised as a VerifyError."""
    @functools.wraps(plan_reader)
    def read(*args):
        try:
            return plan_reader(*args)
        except plan_format.PlanFormatError as error:
            raise VerifyError(str(error)) from error
    return read


ticket_criteria = raising_verify_error(plan_format.ticket_criteria)


def parse_criteria_file(text, name="acceptance-criteria.md"):
    """(entries, manual_entries) from acceptance-criteria.md, one {id, text} per id.

    Lines are `- **ACn** — text`; the id span may carry a parenthetical or several ids. Any line that starts
    with a `**ACn` bold span (after indent and an optional list marker), or holds a closed bold id span anywhere,
    but does not match raises Fail; an unclosed `**ACn's ...` later in a line is prose and is skipped."""
    entries = []
    manual_entries = []
    in_manual = False
    for number, line in enumerate(text.splitlines(), 1):
        if plan_format.heading_level(line):
            in_manual = bool(re.match(r"^#+\s+manual only", line, re.I))
            continue
        match = ID_LINE.match(line)
        if not match and not (ID_START.search(line) or ID_SPAN.search(line)):
            continue
        if not match:
            raise VerifyError(f"{name}:{number}: line names an acceptance id but does not match "
                       f"`- **ACn** — text`: {line.strip()[:80]}")
        target = manual_entries if in_manual else entries
        for ac_id in AC_ID.findall(match.group(1)):
            target.append({"id": ac_id, "text": match.group(2).strip()})
    return entries, manual_entries


@raising_verify_error
def manual_items(plan_text, name):
    """Unchecked Manual Verification items in a plan, tagged human-only from the heading or the item.

    The items of a phase moved to another ticket (`[-]` in Phase Status) are not listed: this branch does not owe them.
    The section grammar is plan_format's; a line it does not parse, and a moved line with no ticket key or no Plan
    Deviations line, raise Fail with `name:line`."""
    parsed = plan_format.manual_verification(plan_text, name)
    moved_ids = {entry["number"] for entry in plan_format.moved_phases(plan_text, name)}
    return [{"text": item["text"], "humanOnly": item["humanOnly"]} for item in parsed
            if not item["checked"] and item["phase"] not in moved_ids]


@raising_verify_error
def moved_phase_notes(plan_text, name):
    """One line per phase moved to another ticket: `Phase <id> moved to <KEY>`, with the count of its unchecked Manual
    Verification items, which move with it. [] when no phase is moved."""
    parsed = plan_format.manual_verification(plan_text, name)
    moved_entries = plan_format.moved_phases(plan_text, name)
    notes = []
    for entry in moved_entries:
        unchecked = sum(1 for item in parsed if item["phase"] == entry["number"] and not item["checked"])
        notes.append(f"Phase {entry['number']} moved to {entry['movedTo']}: {unchecked} unchecked Manual Verification "
                     "item(s) go with it")
    return notes


# ---------- git ----------

def repo_top(cwd):
    """The repo top level as a resolved path. Raises Fail outside a repository."""
    top = script_utils.repo_root(cwd)
    if top is None:
        raise VerifyError("not inside a git repository")
    return top.resolve()


def find_base(top, override=None):
    """(ref, mergeBaseSha). An explicit override wins; otherwise origin/master, origin/main, master, main."""
    refs = [override] if override else ["origin/master", "origin/main", "master", "main"]
    for ref in refs:
        done = run(["git", "merge-base", "HEAD", ref], cwd=top)
        if done.returncode == 0 and done.stdout.strip():
            return ref, done.stdout.strip()
    raise VerifyError(f"no base found (tried {', '.join(refs)}); pass --base <ref> for a sprint branch")


def require_branch(top):
    branch = script_utils.current_branch(top)
    if not branch:
        raise VerifyError("detached HEAD: check out the branch")
    return branch


def repo_relative(path, top):
    """`path` relative to the repo top level; None when it lies outside the repo."""
    try:
        return str(pathlib.Path(path).resolve().relative_to(top))
    except ValueError:
        return None


def review_ran(repo, branch, fingerprint):
    """(ran, reason). A branch-exit code-reviewer run row that verify-log wrote (it carries REVIEW_MARKER and a tree
    fingerprint) counts when its fingerprint equals `fingerprint`. `ledger yield --review-trees` lists the
    fingerprints of the checkout the process runs in, so `repo` and `branch` come from that checkout. Raises
    script_utils.LedgerUnreadError when the ledger is not installed, stays busy after the shared wait, or fails."""
    try:
        listed = script_utils.read_ledger(["yield", "--review-trees"])
    except OSError as error:
        raise script_utils.LedgerUnreadError(f"ledger yield --review-trees: cannot run ledger: {error}") from error

    if listed.returncode != 0:
        raise script_utils.LedgerUnreadError(
            f"ledger yield --review-trees: {script_utils.ledger_failure_reason(listed)}")

    trees = listed.stdout.splitlines()[1:]
    if not trees:
        return False, f"no {REVIEW_GATE} branch-exit run row from verify-log for {repo}@{branch}"
    if fingerprint in trees:
        return True, f"{REVIEW_GATE} run row in the ledger, tree unchanged since"
    return False, "the tree differs from the one reviewed"


def review_state(repo, branch, fingerprint, logged_tree):
    """{"read", "ran", "reason"} for the context's `review`. read is True when the ledger answered. When it gives no
    answer (not installed, busy or failing), read is False, and the review counts as ran only when verify-log logged
    one for this same tree from this branch's saved context (`logged_tree` is the fingerprint it saved there)."""
    try:
        ran, reason = review_ran(repo, branch, fingerprint)
    except script_utils.LedgerUnreadError as error:
        logged_here = logged_tree == fingerprint
        record = ("verify-log logged a review of this tree from this checkout" if logged_here
                  else "no review of this tree was logged from this checkout")
        return {"read": False, "ran": logged_here, "reason": f"{error}; {record}"}
    return {"read": True, "ran": ran, "reason": reason}


def context_path(repo, branch):
    state_dir = pathlib.Path(os.environ.get("VERIFY_STATE_DIR") or STATE_ROOT / "verify-branch")
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", f"{repo}-{branch}")
    return state_dir / f"{safe}.json"


def save_context(path, context):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(context, indent=1))


def load_context(path):
    if not path.is_file():
        raise VerifyError(f"no verify-prep context at {path}; run verify-prep first")
    return json.loads(path.read_text())


def die(error):
    print(f"{pathlib.Path(sys.argv[0]).name}: {error}", file=sys.stderr)
    sys.exit(error.code)
