"""Shared helpers for verify-prep and verify-log: git, plan/ticket parsing, the review signal, the saved run context."""
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent.parent / "lib")]
import plan_format
import script_utils

TOOLKIT_DIR = pathlib.Path(__file__).resolve().parents[2]
STATE_ROOT = pathlib.Path.home() / ".claude" / "state"
REVIEW_MARKER = "verify-branch"
REVIEW_GATE = "code-reviewer"
# `ledger yield` waits up to 10 s on a locked database, then exits 75. A busy ledger is never read as "no review ran".
LEDGER_BUSY_EXIT = 75
LEDGER_ATTEMPTS = 4
# The environment variables set the call timeout and the pause between tries; they exist so a test need not wait.
LEDGER_CALL_TIMEOUT_SECONDS = 60
LEDGER_BACKOFF_SECONDS = 3
LEDGER_TIMEOUT_ENV = "VERIFY_LEDGER_TIMEOUT_SECONDS"
LEDGER_BACKOFF_ENV = "VERIFY_LEDGER_BACKOFF_SECONDS"
LEDGER_BUSY_MESSAGE = ("the ledger is busy (another process holds the database), so the review state could not be "
                       "read; run this step again in a minute")
AC_HEADING = re.compile(r"^(#{2,3})\s+(?:acceptance(?:\s+criteria)?|requirements)\s*:?\s*$", re.I)
AC_HEADING_LOOSE = re.compile(r"^(#{2,3})\s+(?:acceptance|requirements)\b", re.I)
LISTITEM = re.compile(r"^(\s*)(?:[-*]|\d+[.)])\s+(?:\[[ xX]\]\s+)?(.*)$")
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


def run(argv, cwd=None, check=False, stdin=None):
    try:
        done = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, errors="replace", input=stdin)
    except OSError as error:
        raise VerifyError(f"cannot run {argv[0]}: {error}") from error
    if check and done.returncode != 0:
        raise VerifyError(f"{' '.join(argv)} failed: {done.stderr.strip()}")
    return done


def git(args, cwd, check=True):
    done = run(["git", *args], cwd=cwd, check=check)
    return done.stdout.strip()


def script_path(env_name, installed_relative):
    return os.environ.get(env_name) or str(TOOLKIT_DIR / installed_relative)


# ---------- markdown parsing ----------

def heading_level(line):
    match = re.match(r"^(#+)\s", line)
    return len(match.group(1)) if match else 0


def section_body(lines, start_index):
    """Lines under lines[start_index] up to a heading of the same or higher level, or a `---` rule."""
    level = heading_level(lines[start_index])
    body = []
    for line in lines[start_index + 1:]:
        if line.strip() == "---":
            break
        next_level = heading_level(line)
        if next_level and next_level <= level:
            break
        body.append(line)
    return body


def top_level_items(body, name="section", first_line=1):
    """Top-level list items of a section; wrapped and nested lines are folded into the item above.

    A line at column 0 that is not a list item but holds a word is prose the parse would drop: it raises Fail
    with `name:line`. `first_line` is the file line number of body[0]."""
    items = []
    for offset, line in enumerate(body):
        match = LISTITEM.match(line)
        is_prose = (not match and line.strip() and not line.startswith((" ", "\t")) and re.search(r"\w", line))
        if is_prose:
            raise VerifyError(f"{name}:{first_line + offset}: prose in the criteria section is not a list item, so it "
                       f"would be skipped: {line.strip()[:80]}")
        if match and len(match.group(1)) < 2:
            items.append(match.group(2).strip())
        elif match and items:
            items[-1] += " " + match.group(2).strip()
        elif line.strip() and line.startswith((" ", "\t")) and items:
            items[-1] += " " + line.strip()
    return items


def ticket_criteria(ticket_text, name="ticket"):
    """Criteria from a ticket (or legacy flat plan), numbered in order and labelled by source
    (`Ticket #2`): the ticket's own numbering, never an id from the criteria file. Raises Fail when none are found
    or when a heading starts like a criteria heading but is not one."""
    lines = ticket_text.splitlines()
    for number, line in enumerate(lines, 1):
        if AC_HEADING_LOOSE.match(line) and not AC_HEADING.match(line):
            raise VerifyError(
                f"{name}:{number}: heading `{line.strip()}` is not a recognized criteria heading "
                "(`Acceptance`, `Acceptance` + `criteria`, `Requirements`); rename it or what it holds is not read"
            )
    candidates = [i for i, line in enumerate(lines) if AC_HEADING.match(line)]
    if not candidates:
        raise VerifyError("no `## Acceptance*` or `## Requirements*` heading in the ticket; "
                   "refusing to treat zero criteria as a pass")
    candidates.sort(key=lambda i: (heading_level(lines[i]), i))
    for index in candidates:
        items = top_level_items(section_body(lines, index), name, index + 2)
        if items:
            return [{"number": n, "label": f"Ticket #{n}", "text": text} for n, text in enumerate(items, 1)]
    raise VerifyError(
        f"heading `{lines[candidates[0]].strip()}` has no list items; refusing to treat zero criteria as a pass"
    )


def criteria_file(text, name="acceptance-criteria.md"):
    """(entries, manual_entries) from acceptance-criteria.md, one {id, text} per id.

    Lines are `- **ACn** — text`; the id span may carry a parenthetical or several ids. Any line that starts
    with a `**ACn` bold span (after indent and an optional list marker), or holds a closed bold id span anywhere,
    but does not match raises Fail; an unclosed `**ACn's ...` later in a line is prose and is skipped."""
    entries = []
    manual_entries = []
    in_manual = False
    for number, line in enumerate(text.splitlines(), 1):
        if heading_level(line):
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


def manual_items(plan_text, name):
    """Unchecked Manual Verification items in a plan, tagged human-only from the heading or the item.

    The items of a phase moved to another ticket (`[-]` in Phase Status) are not listed: this branch does not owe them.
    The section grammar is plan_format's; a line it does not parse, and a moved line with no ticket key or no Plan
    Deviations line, raise Fail with `name:line`."""
    try:
        parsed = plan_format.manual_verification(plan_text, name)
        moved_ids = {entry["number"] for entry in plan_format.moved_phases(plan_text, name)}
    except plan_format.PlanFormatError as error:
        raise VerifyError(str(error)) from error
    return [{"text": item["text"], "humanOnly": item["humanOnly"]} for item in parsed
            if not item["checked"] and item["phase"] not in moved_ids]


def moved_phase_notes(plan_text, name):
    """One line per phase moved to another ticket: `Phase <id> moved to <KEY>`, with the count of its unchecked Manual
    Verification items, which move with it. [] when no phase is moved."""
    try:
        parsed = plan_format.manual_verification(plan_text, name)
        moved_entries = plan_format.moved_phases(plan_text, name)
    except plan_format.PlanFormatError as error:
        raise VerifyError(str(error)) from error
    notes = []
    for entry in moved_entries:
        unchecked = sum(1 for item in parsed if item["phase"] == entry["number"] and not item["checked"])
        notes.append(f"Phase {entry['number']} moved to {entry['movedTo']}: {unchecked} unchecked Manual Verification "
                     "item(s) go with it")
    return notes


# ---------- git ----------

def repo_top(cwd):
    """The repo top level as a resolved path. Raises Fail outside a repository."""
    done = run(["git", "rev-parse", "--show-toplevel"], cwd=cwd)
    if done.returncode != 0 or not done.stdout.strip():
        raise VerifyError("not inside a git repository")
    return pathlib.Path(done.stdout.strip()).resolve()


def repo_name(top):
    script = script_path("REPO_NAME_SCRIPT", "scripts/tools/repo-name")
    done = run([script], cwd=top)
    if done.returncode == 0 and done.stdout.strip():
        return done.stdout.strip()
    return top.name


def find_base(top, override=None):
    """(ref, mergeBaseSha). An explicit override wins; otherwise origin/master, origin/main, master, main."""
    refs = [override] if override else ["origin/master", "origin/main", "master", "main"]
    for ref in refs:
        done = run(["git", "merge-base", "HEAD", ref], cwd=top)
        if done.returncode == 0 and done.stdout.strip():
            return ref, done.stdout.strip()
    raise VerifyError(f"no base found (tried {', '.join(refs)}); pass --base <ref> for a sprint branch")


def current_branch(top):
    branch = git(["branch", "--show-current"], top)
    if not branch:
        raise VerifyError("detached HEAD: check out the branch")
    return branch


def repo_relative(path, top):
    """`path` relative to the repo top level; None when it lies outside the repo."""
    try:
        return str(pathlib.Path(path).resolve().relative_to(top))
    except ValueError:
        return None


def is_under(name, exclude_rel):
    return name == exclude_rel or name.startswith(exclude_rel.rstrip("/") + "/")


def tree_fingerprint(top, merge_base, exclude_rel=None):
    """Content fingerprint of the branch as it stands: `git diff <mergeBase>` plus the hash of each untracked file.

    Equal fingerprints mean equal content, whatever the commits, mtimes or renames in between. `excludeRel` (a path
    relative to the top level) leaves a file or directory out of both parts: the task dir, whose one allowed edit by
    the plan verifier must not make a finished review stale."""
    digest = hashlib.sha256()
    diff_argv = ["git", "diff", "--binary", "--no-color", "--no-ext-diff", "--no-textconv", merge_base, "--", "."]
    if exclude_rel:
        diff_argv.append(f":(exclude,literal){exclude_rel}")
    digest.update(run(diff_argv, cwd=top, check=True).stdout.encode())
    listing = run(["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=top, check=True).stdout
    names = sorted(n for n in listing.split("\0") if n and not (exclude_rel and is_under(n, exclude_rel)))
    if any("\n" in name for name in names):
        raise VerifyError("an untracked file name holds a newline; rename it so the tree can be fingerprinted")
    if names:
        hashed = run(["git", "hash-object", "--stdin-paths"], cwd=top, check=True, stdin="\n".join(names) + "\n")
        file_hashes = hashed.stdout.split()
        if len(file_hashes) != len(names):
            raise VerifyError(f"git hash-object returned {len(file_hashes)} hashes for {len(names)} untracked files")
        for name, file_hash in zip(names, file_hashes, strict=False):
            digest.update(f"\0untracked\0{name}\0{file_hash}".encode())
    return "sha256:" + digest.hexdigest()


def review_ran(repo, branch, fingerprint):
    """(ran, reason). A branch-exit code-reviewer run row that verify-log wrote (it carries REVIEW_MARKER and a tree
    fingerprint) counts when its fingerprint equals `fingerprint`. `ledger yield --review-trees` lists the
    fingerprints of the checkout the process runs in, so `repo` and `branch` come from that checkout."""
    if shutil.which("ledger") is None:
        return False, "ledger not installed"
    try:
        listed = script_utils.run_retrying(
            ["ledger", "yield", "--review-trees"], (LEDGER_BUSY_EXIT,), LEDGER_ATTEMPTS,
            float(os.environ.get(LEDGER_BACKOFF_ENV, LEDGER_BACKOFF_SECONDS)),
            float(os.environ.get(LEDGER_TIMEOUT_ENV, LEDGER_CALL_TIMEOUT_SECONDS)))
    except OSError as error:
        raise VerifyError(f"cannot run ledger: {error}") from error
    except subprocess.TimeoutExpired:
        raise VerifyError(LEDGER_BUSY_MESSAGE) from None
    if listed.returncode == LEDGER_BUSY_EXIT:
        raise VerifyError(LEDGER_BUSY_MESSAGE)
    if listed.returncode != 0:
        error_lines = listed.stderr.strip().splitlines()
        raise VerifyError(error_lines[-1] if error_lines else f"ledger yield --review-trees exited {listed.returncode}")

    trees = listed.stdout.splitlines()[1:]
    if not trees:
        return False, f"no {REVIEW_GATE} branch-exit run row from verify-log for {repo}@{branch}"
    if fingerprint in trees:
        return True, f"{REVIEW_GATE} run row in the ledger, tree unchanged since"
    return False, "the tree differs from the one reviewed"


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
