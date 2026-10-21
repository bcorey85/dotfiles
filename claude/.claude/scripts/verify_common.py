"""Shared helpers for verify-prep and verify-log: git, plan/ticket parsing, the review signal, the saved run context."""
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys

import plan_format

CLAUDE_HOME = pathlib.Path.home() / ".claude"
REVIEW_MARKER = "verify-branch"
REVIEW_GATE = "code-reviewer"
AC_HEADING = re.compile(r"^(#{2,3})\s+(?:acceptance(?:\s+criteria)?|requirements)\s*:?\s*$", re.I)
AC_HEADING_LOOSE = re.compile(r"^(#{2,3})\s+(?:acceptance|requirements)\b", re.I)
LISTITEM = re.compile(r"^(\s*)(?:[-*]|\d+[.)])\s+(?:\[[ xX]\]\s+)?(.*)$")
# Accepted id spans: a plain id, an id followed by a parenthetical, an id with a qualifier inside the bold,
# or several comma-separated ids inside one bold span.
ID_LINE = re.compile(r"^\s*[-*]\s+\*\*(AC\d+[^*]*)\*\*\s*(?:\([^)]*\))?\s*[—–-]+\s*(.*)$")
ID_START = re.compile(r"\*\*AC\d+")
AC_ID = re.compile(r"AC\d+")


class Fail(Exception):
    """A loud, expected failure: message to stderr, exit code `code`."""

    def __init__(self, message, code=2):
        super().__init__(message)
        self.code = code


def run(argv, cwd=None, check=False, stdin=None):
    try:
        done = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, errors="replace", input=stdin)
    except OSError as error:
        raise Fail(f"cannot run {argv[0]}: {error}")
    if check and done.returncode != 0:
        raise Fail(f"{' '.join(argv)} failed: {done.stderr.strip()}")
    return done


def git(args, cwd, check=True):
    done = run(["git", *args], cwd=cwd, check=check)
    return done.stdout.strip()


def script_path(envName, installedRelative):
    return os.environ.get(envName) or str(CLAUDE_HOME / installedRelative)


# ---------- markdown parsing ----------

def heading_level(line):
    match = re.match(r"^(#+)\s", line)
    return len(match.group(1)) if match else 0


def section_body(lines, startIndex):
    """Lines under lines[startIndex] up to a heading of the same or higher level, or a `---` rule."""
    level = heading_level(lines[startIndex])
    body = []
    for line in lines[startIndex + 1:]:
        if line.strip() == "---":
            break
        nextLevel = heading_level(line)
        if nextLevel and nextLevel <= level:
            break
        body.append(line)
    return body


def top_level_items(body, name="section", firstLine=1):
    """Top-level list items of a section; wrapped and nested lines are folded into the item above.

    A line at column 0 that is not a list item but holds a word is prose the parse would drop: it raises Fail
    with `name:line`. `firstLine` is the file line number of body[0]."""
    items = []
    for offset, line in enumerate(body):
        match = LISTITEM.match(line)
        isProse = (not match and line.strip() and not line.startswith((" ", "\t")) and re.search(r"\w", line))
        if isProse:
            raise Fail(f"{name}:{firstLine + offset}: prose in the criteria section is not a list item, so it "
                       f"would be skipped: {line.strip()[:80]}")
        if match and len(match.group(1)) < 2:
            items.append(match.group(2).strip())
        elif match and items:
            items[-1] += " " + match.group(2).strip()
        elif line.strip() and line.startswith((" ", "\t")) and items:
            items[-1] += " " + line.strip()
    return items


def ticket_criteria(ticketText, name="ticket"):
    """Criteria from a ticket (or legacy flat plan), numbered in order and labelled by source
    (`Ticket #2`): the ticket's own numbering, never an id from the criteria file. Raises Fail when none are found
    or when a heading starts like a criteria heading but is not one."""
    lines = ticketText.splitlines()
    for number, line in enumerate(lines, 1):
        if AC_HEADING_LOOSE.match(line) and not AC_HEADING.match(line):
            raise Fail(f"{name}:{number}: heading `{line.strip()}` is not a recognized criteria heading "
                       "(`Acceptance`, `Acceptance` + `criteria`, `Requirements`); rename it or what it holds is not read")
    candidates = [i for i, line in enumerate(lines) if AC_HEADING.match(line)]
    if not candidates:
        raise Fail("no `## Acceptance*` or `## Requirements*` heading in the ticket; "
                   "refusing to treat zero criteria as a pass")
    candidates.sort(key=lambda i: (heading_level(lines[i]), i))
    for index in candidates:
        items = top_level_items(section_body(lines, index), name, index + 2)
        if items:
            return [{"number": n, "label": f"Ticket #{n}", "text": text} for n, text in enumerate(items, 1)]
    raise Fail(f"heading `{lines[candidates[0]].strip()}` has no list items; refusing to treat zero criteria as a pass")


def criteria_file(text, name="acceptance-criteria.md"):
    """(entries, manualEntries) from acceptance-criteria.md, one {id, text} per id.

    Lines are `- **ACn** — text`; the id span may carry a parenthetical or several ids. Any line that opens
    a `**ACn` bold span but does not match raises Fail."""
    entries = []
    manualEntries = []
    inManual = False
    for number, line in enumerate(text.splitlines(), 1):
        if heading_level(line):
            inManual = bool(re.match(r"^#+\s+manual only", line, re.I))
            continue
        if not ID_START.search(line):
            continue
        match = ID_LINE.match(line)
        if not match:
            raise Fail(f"{name}:{number}: line names an acceptance id but does not match "
                       f"`- **ACn** — text`: {line.strip()[:80]}")
        target = manualEntries if inManual else entries
        for acId in AC_ID.findall(match.group(1)):
            target.append({"id": acId, "text": match.group(2).strip()})
    return entries, manualEntries


def manual_items(planText, name):
    """Unchecked Manual Verification items in a plan, tagged human-only from the heading or the item.

    The section grammar is plan_format's; a line it does not parse raises Fail with `name:line`."""
    try:
        parsed = plan_format.manual_verification(planText, name)
    except plan_format.PlanFormatError as error:
        raise Fail(str(error))
    return [{"text": item["text"], "humanOnly": item["humanOnly"]} for item in parsed if not item["checked"]]


# ---------- git ----------

def repo_top(cwd):
    """The repo top level as a resolved path. Raises Fail outside a repository."""
    done = run(["git", "rev-parse", "--show-toplevel"], cwd=cwd)
    if done.returncode != 0 or not done.stdout.strip():
        raise Fail("not inside a git repository")
    return pathlib.Path(done.stdout.strip()).resolve()


def repo_name(top):
    script = script_path("REPO_NAME_SCRIPT", "scripts/repo-name")
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
    raise Fail(f"no base found (tried {', '.join(refs)}); pass --base <ref> for a sprint branch")


def current_branch(top):
    branch = git(["branch", "--show-current"], top)
    if not branch:
        raise Fail("detached HEAD: check out the branch")
    return branch


def repo_relative(path, top):
    """`path` relative to the repo top level; None when it lies outside the repo."""
    try:
        return str(pathlib.Path(path).resolve().relative_to(top))
    except ValueError:
        return None


def is_under(name, excludeRel):
    return name == excludeRel or name.startswith(excludeRel.rstrip("/") + "/")


def tree_fingerprint(top, mergeBase, excludeRel=None):
    """Content fingerprint of the branch as it stands: `git diff <mergeBase>` plus the hash of each untracked file.

    Equal fingerprints mean equal content, whatever the commits, mtimes or renames in between. `excludeRel` (a path
    relative to the top level) leaves a file or directory out of both parts: the task dir, whose one allowed edit by
    the plan verifier must not make a finished review stale."""
    digest = hashlib.sha256()
    diffArgv = ["git", "diff", "--binary", "--no-color", "--no-ext-diff", "--no-textconv", mergeBase, "--", "."]
    if excludeRel:
        diffArgv.append(f":(exclude,literal){excludeRel}")
    digest.update(run(diffArgv, cwd=top, check=True).stdout.encode())
    listing = run(["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=top, check=True).stdout
    names = sorted(n for n in listing.split("\0") if n and not (excludeRel and is_under(n, excludeRel)))
    if any("\n" in name for name in names):
        raise Fail("an untracked file name holds a newline; rename it so the tree can be fingerprinted")
    if names:
        hashed = run(["git", "hash-object", "--stdin-paths"], cwd=top, check=True, stdin="\n".join(names) + "\n")
        fileHashes = hashed.stdout.split()
        if len(fileHashes) != len(names):
            raise Fail(f"git hash-object returned {len(fileHashes)} hashes for {len(names)} untracked files")
        for name, fileHash in zip(names, fileHashes):
            digest.update(f"\0untracked\0{name}\0{fileHash}".encode())
    return "sha256:" + digest.hexdigest()


def review_ran(repo, branch, fingerprint):
    """(ran, reason). A branch-exit code-reviewer run row that verify-log wrote (it carries REVIEW_MARKER and a tree
    fingerprint) counts when its fingerprint equals `fingerprint`."""
    logPath = pathlib.Path(os.environ.get("REVIEW_FINDINGS_FILE") or CLAUDE_HOME / "review-findings.jsonl")
    if not logPath.is_file():
        return False, "no review-findings log"
    rows = []
    for number, line in enumerate(logPath.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError as error:
            raise Fail(f"{logPath}:{number}: not valid JSON ({error}); fix or remove the line")
        isMatch = (row.get("kind") == "run" and row.get("gate") == REVIEW_GATE and row.get("scope") == "branch-exit"
                   and row.get("repo") == repo and row.get("branch") == branch
                   and row.get("source") == REVIEW_MARKER and row.get("tree"))
        if isMatch:
            rows.append(row)
    if not rows:
        return False, f"no {REVIEW_GATE} branch-exit run row from verify-log for {repo}@{branch}"

    for row in reversed(rows):
        if row["tree"] == fingerprint:
            return True, f"{REVIEW_GATE} run row at {row['date']}, tree unchanged since"
    return False, f"the tree differs from the one reviewed at {rows[-1]['date']}"


def context_path(repo, branch):
    stateDir = pathlib.Path(os.environ.get("VERIFY_STATE_DIR") or CLAUDE_HOME / "state" / "verify-branch")
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", f"{repo}-{branch}")
    return stateDir / f"{safe}.json"


def save_context(path, context):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(context, indent=1))


def load_context(path):
    if not path.is_file():
        raise Fail(f"no verify-prep context at {path}; run verify-prep first")
    return json.loads(path.read_text())


def die(error):
    print(f"{pathlib.Path(sys.argv[0]).name}: {error}", file=sys.stderr)
    sys.exit(error.code)
