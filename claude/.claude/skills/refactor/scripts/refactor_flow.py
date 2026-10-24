#!/usr/bin/env python3
"""refactor-flow: the fixed steps of the /refactor skill, one call per mode.

  refactor_flow.py branch-prep [--head REF] [--base REF]
  refactor_flow.py audit-prep <dir> [--jscpd-timeout SECONDS]
  refactor_flow.py simplify-prep <dir|file...> [--slice N]
  refactor_flow.py log --mode branch|targeted|audit|simplify --input FILE.json [--base REF]
  refactor_flow.py handoff --input FILE.json

Every verb prints its report and ends with one `NEXT:` line naming what the
model still does, or a `STOP:` line with the reason. Each prep verb deletes all but the newest 49
regular files named `refactor-flow-` plus 12 hex digits plus `.json` (not every `refactor-flow-*.json`)
in REFACTOR_LOG_INPUT_DIR (default: the system temp dir) before it names a fresh path.
Otherwise read-only except `log`, which appends rows through the existing writers
(log-escape, log-review-finding); this script never writes a second copy of those rows.
`log` is idempotent per input file: it keeps a hash of every row a writer accepted, grouped by the
resolved --input path, under ~/.claude/state/refactor-flow/ and skips a row already written for that
file. Use one input file per /refactor invocation and re-run `log` on it.
The state keeps the newest 50 input paths. The writers own
the value vocabulary (class, guard, result, ...); this script checks shape only.

Input file (JSON; `log` reads all of it, `handoff` reads only `handoff` and `modifier`):
  {"finder": "smell-reviewer", "lane": "code", "result": "NEEDS CHANGES",
   "target": ["src/orders"],   (audit and simplify: dirs; simplify: the files the prep listed)
   "findings": [{"class": "duplication", "disposition": "fix", "actioned": "fixed",
                 "file": "a.py", "line": 3, "desc": "...", "severity": "medium",
                 "escape": true}],
   "guards": {"duplication": "convention"},
   "handoff": {"files": [{"path": "a.py", "change": "..."}],
               "tests_run": "pytest a -> exit 0", "flagged": "none", "plan_impact": "none"},
   "modifier": "+fast"}
Exit codes: 0 ok or a clean stop, 1 bad input (nothing was written), 2 a writer refused a row.
"""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from stat import S_ISREG

CLAUDE = Path(os.environ.get("REFACTOR_CLAUDE_DIR", Path.home() / ".claude"))
LOG_ESCAPE = os.environ.get("REFACTOR_LOG_ESCAPE") or str(CLAUDE / "scripts" / "telemetry" / "log-escape")
LOG_FINDING = os.environ.get("REFACTOR_LOG_FINDING") or str(CLAUDE / "skills" / "review" / "log-review-finding")
BRANCH_BASE = os.environ.get("BRANCH_BASE_SCRIPT") or str(CLAUDE / "scripts" / "tools" / "branch-base")

FINDERS = {"smell-reviewer", "complexity-reviewer"}
MAX_SIMPLIFY_FILES = 25
MAX_CLONE_PAIRS = 40
MAX_STATE_INPUTS = 50
MAX_LOG_INPUTS = MAX_STATE_INPUTS
LOG_INPUT_PREFIX = "refactor-flow-"
LOG_INPUT_HEX_DIGITS = 12
LOG_INPUT_NAME = re.compile(re.escape(LOG_INPUT_PREFIX) + rf"[0-9a-f]{{{LOG_INPUT_HEX_DIGITS}}}\.json")

SWEEP_MARKERS = re.compile(r"TODO|FIXME|XXX|HACK|console\.(log|debug)|debugger\b|binding\.pry|print\(")
SWEEP_COMMENTED_CODE = re.compile(r"^\s*(//|#)\s*(if |for |while |return |const |let |var |def |function |import )")
HUNK_HEADER = re.compile(r"@@ -\S+ \+(\d+)(?:,\d+)? @@")
CLONE_SITE = re.compile(r"^\s+(?:- )?(.+?) (\[\d+:\d+ - \d+:\d+\])\s*$")

SMELL_BOUND = ("Your review bound for this run is the whole branch diff (`git diff {base}...{head}`), "
               "not a phase diff.")
SMELL_PRIORITY = ("Prioritize cross-phase smells — things no single-phase view could see (multi-task "
                  "duplication, drifted naming, orphaned dead code, idiom divergence from unchanged siblings). "
                  "Every finding must carry `file:line` (and the sibling/prior-art `file:line` for duplication).")
AUDIT_BOUND = ("Audit mode: your bound is the existing code of `{target}` — pre-existing smells ARE the target "
               "this run, per your audit-bound clause.")
AUDIT_ASK = ("Find duplication across files, pattern/idiom drift between sibling modules, and wrong-altitude code. "
             "Each finding carries both `file:line` sites and the consolidation it proposes. Cross-module "
             "consolidations or anything moving a public contract are `[design-decision]`.")
AUDIT_CANDIDATES = ("Judge each candidate against the anti-churn line — must-stay-in-sync (flag, name the "
                    "extraction) vs looks-a-bit-similar (suppress).")
SIMPLIFY_BOUND = ("Simplify mode: your bound is the whole existing code of `{target}`. Pre-existing shape IS "
                  "the target.")
SIMPLIFY_ASK = ("Find what could be deleted if this module were shaped differently: branching a data model "
                "collapses, indirection with one implementation, configurability nothing configures, guards a "
                "stronger invariant kills, values with more than one owner. Your oracle and magnitude floor are "
                "hard gates (quantified disappearance, enabling change, unreachability proof, cost clause).")
NO_HISTORY_STOP = "STOP: {base} and {head} share no history; ask the user for --base."


class RefactorFlowError(Exception):
    """Bad input: print it, write nothing, exit 1."""


class NoSharedHistoryError(RefactorFlowError):
    """The base and the head have no merge base (orphan branch, shallow clone)."""


class NoBaseError(RefactorFlowError):
    """The branch-base helper found no base; the message is its `STOP:` line."""


def run(args, check=True):
    done = subprocess.run(args, capture_output=True, text=True, errors="replace")
    if check and done.returncode != 0:
        raise RefactorFlowError(f"`{' '.join(args)}` failed: {done.stderr.strip() or done.stdout.strip()}")
    return done


def git(*args, check=True):
    return run(["git", *args], check=check)


def repo_root():
    done = git("rev-parse", "--show-toplevel", check=False)
    if done.returncode != 0:
        raise RefactorFlowError("not inside a git repository")
    return done.stdout.strip()


def ref_exists(ref):
    return git("rev-parse", "--verify", "--quiet", ref + "^{commit}", check=False).returncode == 0


def pick_base(requested, head=None):
    """Returns (ref, where the ref came from). The branch-base helper owns the order of candidates."""
    if requested:
        if not ref_exists(requested):
            raise RefactorFlowError(f"--base {requested} is not a commit")
        return requested, "--base"

    command = ["bash", BRANCH_BASE, *(["--head", head] if head else [])]
    done = run(command, check=False)
    if done.returncode == 1 and done.stderr.startswith("STOP:"):
        raise NoBaseError(done.stderr.strip())
    if done.returncode != 0:
        raise RefactorFlowError(f"`{' '.join(command)}` failed: {done.stderr.strip() or done.stdout.strip()}")

    ref, _, source = done.stdout.strip().partition(" ")
    if not ref or not source:
        raise RefactorFlowError(f"`{' '.join(command)}` printed {done.stdout.strip()!r}; expected `<ref> <source>`")
    return ref, source


def empty_tree():
    """The empty tree id in this repo's hash algorithm (SHA-1 or SHA-256)."""
    return git("hash-object", "-t", "tree", "/dev/null").stdout.strip()


def diff_output(span, *args, pathspecs=()):
    """Run `git diff` over a span with the flags that make its output parseable under any user config."""
    limit = ["--", *pathspecs] if pathspecs else []
    done = git("--literal-pathspecs", "-c", "core.quotePath=false", "diff", "--no-color", "--no-ext-diff",
               "--no-textconv", "--no-relative", "--src-prefix=a/", "--dst-prefix=b/", *args, span, *limit,
               check=False)
    if done.returncode == 0:
        return done.stdout
    if "no merge base" in done.stderr:
        base, _, head = span.partition("...")
        raise NoSharedHistoryError(NO_HISTORY_STOP.format(base=base, head=head))
    raise RefactorFlowError(f"`git diff {span}` failed: {done.stderr.strip()}")


def sweep_matches(diff_text):
    """Added lines that match the two mechanical-sweep patterns, as (path, line, kind, text)."""
    matches = []
    path = None
    new_file_line = 0
    in_header = False

    for raw in diff_text.splitlines():
        if raw.startswith("diff --git "):
            in_header = True
            path = None
            continue

        if in_header:
            hunk = HUNK_HEADER.match(raw)
            if hunk:
                in_header = False
                new_file_line = int(hunk.group(1))
                continue
            if raw.startswith("+++ "):
                path = parse_new_path(raw)
            continue

        hunk = HUNK_HEADER.match(raw)
        if hunk:
            new_file_line = int(hunk.group(1))
            continue

        if not raw.startswith("+") or path is None:
            continue

        text = raw[1:]
        if SWEEP_MARKERS.search(text):
            matches.append((path, new_file_line, "marker", text.strip()))
        if SWEEP_COMMENTED_CODE.search(text):
            matches.append((path, new_file_line, "commented-out code", text.strip()))
        new_file_line += 1
    return matches


C_ESCAPES = {"a": 7, "b": 8, "f": 12, "n": 10, "r": 13, "t": 9, "v": 11, '"': 34, "\\": 92}
C_ESCAPE = re.compile(r'\\([0-7]{3}|[abfnrtv"\\])')


def unquote_c_path(quoted):
    """Decode a git C-quoted name (`"..."`): the escapes git writes, octal bytes, then UTF-8."""
    inner = quoted[1:-1]
    decoded = bytearray()
    position = 0
    for escape in [*C_ESCAPE.finditer(inner), None]:
        end = escape.start() if escape else len(inner)
        plain = inner[position:end]
        if "\\" in plain:
            raise RefactorFlowError(f"cannot decode quoted path {quoted!r}: unknown escape")
        decoded += plain.encode("utf-8", errors="surrogateescape")
        if escape is None:
            break
        code = escape.group(1)
        decoded.append(int(code, 8) if code[0] in "01234567" else C_ESCAPES[code])
        position = escape.end()
    return decoded.decode("utf-8", errors="replace")


def parse_new_path(header):
    target = header[4:].rstrip("\t")
    if target == "/dev/null":
        return None
    if len(target) >= 2 and target.startswith('"') and target.endswith('"'):
        target = unquote_c_path(target)
    if target.startswith("b/"):
        return target[2:]
    raise RefactorFlowError(f"cannot parse diff header {header!r}: expected `+++ b/<path>` or `+++ /dev/null`")


def binary_paths(numstat_text):
    """Paths git reports as binary in `diff --numstat -z`."""
    tokens = numstat_text.split("\0")
    binary = set()
    index = 0
    while index < len(tokens) and tokens[index]:
        added, _, rest = tokens[index].partition("\t")
        _, _, path = rest.partition("\t")
        if path == "":
            new_path = tokens[index + 2]
            index += 3
        else:
            new_path = path
            index += 1
        if added == "-":
            binary.add(new_path)
    return binary


def changed_files(span):
    """(path, label) for each file in the span; the label names deleted, renamed, copied and binary files."""
    tokens = diff_output(span, "--name-status", "-z").split("\0")
    binary = binary_paths(diff_output(span, "--numstat", "-z"))
    entries = []
    index = 0
    while index < len(tokens) and tokens[index]:
        code = tokens[index][0]
        labels = []
        if code in "RC":
            old_path, path = tokens[index + 1], tokens[index + 2]
            labels.append(("renamed" if code == "R" else "copied") + f" from {old_path}")
            index += 3
        else:
            path = tokens[index + 1]
            index += 2
            if code == "D":
                labels.append("deleted")
        if path in binary:
            labels.append("binary")
        entries.append((path, ", ".join(labels)))
    return entries


def file_line(path, label):
    return f"- {path} ({label})" if label else f"- {path}"


def next_line(text):
    return f"NEXT: {text}"


def prune_log_inputs(folder):
    """Delete all but the newest files that leave room for one more; the model writes the new path next.
    A file another session deletes mid-prune is skipped, and so is anything that is not a regular file."""
    keep = MAX_LOG_INPUTS - 1
    dated = []
    for path in folder.glob(f"{LOG_INPUT_PREFIX}*.json"):
        if not LOG_INPUT_NAME.fullmatch(path.name):
            continue
        try:
            entry = path.lstat()
        except OSError:
            continue
        if S_ISREG(entry.st_mode):
            dated.append((entry.st_mtime, path))
    dated.sort()
    for _, stale in dated[:-keep]:
        with contextlib.suppress(OSError):
            stale.unlink()


def fresh_log_input():
    """A path no earlier /refactor invocation used; `log` dedupes rows per input path."""
    folder = Path(os.environ.get("REFACTOR_LOG_INPUT_DIR") or tempfile.gettempdir())
    prune_log_inputs(folder)
    return str(folder / f"{LOG_INPUT_PREFIX}{uuid.uuid4().hex[:LOG_INPUT_HEX_DIGITS]}.json")


def branch_prep(opts):
    repo_root()
    head = opts.head or "HEAD"
    if not ref_exists(head):
        if opts.head:
            raise RefactorFlowError(f"--head {head} is not a commit")
        print("Branch audit: HEAD is unborn, the repository has no commits yet.")
        print("STOP: tell the user there are no commits to audit. Dispatch nothing.")
        return 0

    try:
        base, base_source = pick_base(opts.base, opts.head)
    except NoBaseError as err:
        print(err)
        return 0

    span = f"{base}...{head}"
    try:
        files = changed_files(span)
        diff_text = diff_output(span, "-U0")
    except NoSharedHistoryError as err:
        print(f"Branch audit: {span} has no merge base.")
        print(err)
        return 0
    if not files:
        print(f"Branch audit: `git diff --name-only {span}` is empty (base `{base}` from {base_source}).")
        print("STOP: tell the user the branch diff is empty. Dispatch nothing.")
        return 0

    log_input = fresh_log_input()
    matches = sweep_matches(diff_text)
    shortstat = diff_output(span, "--shortstat").strip()

    print(f"## Branch audit scope (base `{base}` from {base_source}, head `{head}`)")
    print(f"Changed files ({len(files)}); {shortstat}")
    print()
    print(f"## Mechanical sweep ({len(matches)} match(es)) — straight onto the work list")
    for path, line, kind, text in matches:
        print(f"- {path}:{line} [{kind}] {text[:120]}")
    if not matches:
        print("- none")
    print()
    print("## smell-reviewer dispatch prompt (pinned; omit `model` unless +fast)")
    print("Changed files:")
    for path, label in files:
        print(file_line(path, label))
    print(SMELL_BOUND.format(base=base, head=head))
    print(SMELL_PRIORITY)
    print()
    print(next_line("dispatch ONE smell-reviewer with the prompt above; make the work list = findings + sweep "
                    "matches (`[design-decision]` goes to the user); then dispatch the coder, run the step-5 test "
                    "audit when the refactor could change test guarantees, run the ratchet for each distinct "
                    f"class, write the log input to {log_input}, and call "
                    f"`log --mode branch --base {base} --input {log_input}`. Nothing found: call the same "
                    "`log` empty-handed and stop."))
    return 0


def run_jscpd(target, timeout):
    """Returns (clone_pairs, note); a pair is its `Clone found` line plus its site lines.
    Never raises: detector failure is a note, not a stop."""
    no_detection = "no mechanical detection — agent prior-art search only"
    override = os.environ.get("REFACTOR_JSCPD_CMD")
    if override:
        command = shlex.split(override)
    elif shutil.which("npx"):
        command = ["npx", "--yes", "jscpd"]
    else:
        return [], no_detection

    with tempfile.TemporaryDirectory() as work_dir:
        try:
            done = subprocess.run([*command, target, "--min-tokens", "70", "--reporters", "consoleFull",
                                   "--output", work_dir],
                                  capture_output=True, text=True, timeout=timeout)
        except (subprocess.TimeoutExpired, OSError):
            return [], no_detection
    if done.returncode not in (0, 1):
        return [], no_detection

    # jscpd prints site paths relative to the target directory.
    prefix = target if Path(target).is_dir() else ""
    pairs = []
    in_clone = False
    plain = re.sub(r"\x1b\[[0-9;]*m", "", done.stdout)
    for line in plain.splitlines():
        if line.startswith("Clone found"):
            in_clone = True
            pairs.append([line])
            continue
        site = CLONE_SITE.match(line) if in_clone and " │ " not in line else None
        if site:
            site_path = os.path.join(prefix, site.group(1)) if prefix else site.group(1)
            pairs[-1].append(f"- {site_path} {site.group(2)}")
        else:
            in_clone = False
    return pairs, ""


def tracked_files(target):
    """Tracked files under the target paths, relative to the cwd (git ls-files -z)."""
    done = git("--literal-pathspecs", "ls-files", "-z", "--", *target, check=False)
    if done.returncode != 0:
        raise RefactorFlowError(f"git ls-files failed for {target}: {done.stderr.strip()}")
    return [name for name in done.stdout.split("\0") if name]


def audit_prep(opts):
    repo_root()
    target = opts.target
    files = tracked_files([target])
    if not files:
        print(f"STOP: `git ls-files {target}` is empty; ask the user for a tracked dir or module.")
        return 0
    log_input = fresh_log_input()
    pairs, note = run_jscpd(target, opts.jscpd_timeout)
    listed_pairs = pairs[:MAX_CLONE_PAIRS]
    unlisted_count = len(pairs) - len(listed_pairs)

    print(f"## Audit target `{target}` ({len(files)} tracked file(s))")
    print()
    print("## Mechanical clone detection (jscpd, --min-tokens 70)")
    if note:
        print(f"- {note}")
    elif pairs:
        print(f"- {len(pairs)} clone pair(s); {len(listed_pairs)} listed in the dispatch prompt below")
    else:
        print("- jscpd ran and found no clone pairs")
    print()
    print("## smell-reviewer dispatch prompt (omit `model` unless +fast)")
    print(AUDIT_BOUND.format(target=target))
    if listed_pairs:
        print("Candidate clone pairs (jscpd):")
        for pair in listed_pairs:
            for line in pair:
                print(line)
        if unlisted_count:
            print(f"{unlisted_count} more pair(s) not listed")
        print(AUDIT_CANDIDATES)
    print(AUDIT_ASK)
    print()
    print(next_line("dispatch ONE smell-reviewer with the prompt above; report the work list with each "
                    "finding's route (targeted /refactor, or /eng-spec for design-decision); then "
                    f"write the log input to {log_input} and call `log --mode audit --input {log_input}` with "
                    f"target [\"{target}\"] (finder rows only; no escape rows, no coders, no /review)."))
    return 0


def simplify_prep(opts):
    repo_root()
    targets = opts.target
    files = []
    seen = set()
    for target in targets:
        found = tracked_files([target])
        if not found:
            print(f"STOP: `git ls-files {target}` is empty; ask the user for a tracked dir or module.")
            return 0
        for name in found:
            if name not in seen:
                seen.add(name)
                files.append(name)

    slices = [files[i:i + MAX_SIMPLIFY_FILES] for i in range(0, len(files), MAX_SIMPLIFY_FILES)]
    if not 1 <= opts.slice <= len(slices):
        raise RefactorFlowError(f"--slice {opts.slice} out of range 1..{len(slices)}")
    chosen = slices[opts.slice - 1]
    label = " ".join(targets)
    log_input = fresh_log_input()

    print(f"## Simplify target `{label}` ({len(files)} tracked file(s))")
    if len(slices) > 1:
        print(f"Over {MAX_SIMPLIFY_FILES} files: split into {len(slices)} slices. This run is slice "
              f"{opts.slice} of {len(slices)} ({len(chosen)} files); tell the user which slice runs, "
              f"re-run with `--slice N` for the others.")
    print()
    print("## complexity-reviewer dispatch prompt (pinned; omit `model`; never +fast)")
    print("Files:")
    for name in chosen:
        print(f"- {name}")
    print(SIMPLIFY_BOUND.format(target=label))
    print(SIMPLIFY_ASK)
    print("Add any project constraint you know that makes a shape mandatory (a required layer, a framework "
          "seam, a public contract).")
    print()
    print(next_line("do NOT read the files; dispatch ONE complexity-reviewer with the prompt above; triage "
                    "(drop oracle-failures, under-floor, irreducible; `[design-decision]` to the user); present "
                    "survivors; on chosen fixes follow step 5 with the test audit mandatory; then "
                    f"write the log input to {log_input} and call `log --mode simplify --input {log_input}` "
                    "with `target` = the files listed in the prompt. Every finder finding "
                    "goes in `findings`: survivors the user declined get actioned=none, triage drops get "
                    "actioned=skipped_fp. Log empty-handed only when the finder returned nothing."))
    return 0


# ----------------------------------------------------------------------- log

def require_text(container, key, where):
    value = container.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RefactorFlowError(f"{where}: `{key}` must be a non-empty string")
    return value


def single_line(container, key, where):
    value = require_text(container, key, where)
    if "\n" in value or "\r" in value:
        raise RefactorFlowError(f"{where}: `{key}` must be one line")
    return value.strip()


SWALLOWED_PAIR = re.compile(r"[ \t\n\r\f\v][A-Za-z_][A-Za-z0-9_]*=")


def one_line_path(value, key, where):
    """A path may hold spaces: the writers get it as one argument. It must not hold a line break, or a
    ` name=` that the writers read as a second field swallowed into this one."""
    if "\n" in value or "\r" in value:
        raise RefactorFlowError(f"{where}: `{key}` must be one line")
    if SWALLOWED_PAIR.search(value):
        raise RefactorFlowError(f"{where}: `{key}` must not contain a space followed by `name=` (got {value!r})")


def validate_finding(finding, index, mode):
    where = f"findings[{index}]"
    if not isinstance(finding, dict):
        raise RefactorFlowError(f"{where}: must be an object")

    for key in ("class", "disposition", "actioned", "file"):
        require_text(finding, key, where)
    one_line_path(finding["file"], "file", where)

    line = finding.get("line")
    if isinstance(line, bool) or not isinstance(line, int):
        raise RefactorFlowError(f"{where}: `line` must be an integer (0 when the finding names no line)")

    finding["desc"] = single_line(finding, "desc", where)
    if not isinstance(finding.get("escape", False), bool):
        raise RefactorFlowError(f"{where}: `escape` must be true or false (got {finding['escape']!r})")
    if not finding.get("escape"):
        return

    if mode in ("audit", "targeted"):
        raise RefactorFlowError(f"{where}: escape rows are not logged in {mode} mode")
    if mode == "simplify" and finding["class"] != "complexity":
        raise RefactorFlowError(f"{where}: simplify escape rows must be class=complexity")
    require_text(finding, "severity", where)


def validate_handoff(handoff):
    if not isinstance(handoff, dict):
        raise RefactorFlowError("`handoff` must be an object")
    files = handoff.get("files")
    if not isinstance(files, list) or not files:
        raise RefactorFlowError("handoff.files must list at least one {path, change}")

    for entry in files:
        if not isinstance(entry, dict):
            raise RefactorFlowError("handoff.files entries must be objects")
        single_line(entry, "path", "handoff.files")
        single_line(entry, "change", "handoff.files")
    single_line(handoff, "tests_run", "handoff")
    single_line(handoff, "flagged", "handoff")

    plan_impact = handoff.get("plan_impact", "none")
    if not isinstance(plan_impact, str) or not plan_impact.strip():
        raise RefactorFlowError("handoff.plan_impact must be a non-empty string (`none` when there is none)")


def validate_log(mode, refactor_log):
    finder = refactor_log.get("finder") or None
    if mode == "targeted":
        if finder:
            raise RefactorFlowError("`finder` must be omitted in targeted mode (no finder is dispatched)")
    elif not isinstance(finder, str) or finder not in FINDERS:
        raise RefactorFlowError(f"`finder` must be one of {sorted(FINDERS)}")

    lane = None
    if finder:
        lane = require_text(refactor_log, "lane", "log input")

    findings = refactor_log.get("findings", [])
    if not isinstance(findings, list):
        raise RefactorFlowError("`findings` must be a list")
    for index, finding in enumerate(findings):
        validate_finding(finding, index, mode)

    guards = refactor_log.get("guards", {})
    if not isinstance(guards, dict):
        raise RefactorFlowError("`guards` must be an object")
    escape_classes = sorted({finding["class"] for finding in findings if finding.get("escape")})
    for escape_class in escape_classes:
        if not isinstance(guards.get(escape_class), str) or not guards[escape_class]:
            raise RefactorFlowError(f"escape class `{escape_class}` needs guards[\"{escape_class}\"] (run the ratchet)")

    verdict = refactor_log.get("result") or ("NEEDS CHANGES" if findings else "PASS")
    if not isinstance(verdict, str):
        raise RefactorFlowError("`result` must be a string")

    targets = refactor_log.get("target") or []
    if not isinstance(targets, list) or not all(isinstance(item, str) and item for item in targets):
        raise RefactorFlowError("`target` must be a list of paths")
    if finder and mode in ("audit", "simplify") and not targets:
        raise RefactorFlowError("`target` (list of dirs or files) is required in audit and simplify mode")

    handoff = refactor_log.get("handoff")
    if mode == "audit" and handoff:
        raise RefactorFlowError("audit mode never hands off to /review")
    if handoff:
        validate_handoff(handoff)

    return {"finder": finder, "lane": lane, "findings": findings, "guards": guards, "verdict": verdict,
            "targets": targets, "handoff": handoff}


def diff_loc_for(mode, base, targets):
    """Lines the finder read: the branch diff size, or the line count of the files it received."""
    if mode == "branch":
        base_ref, _ = pick_base(base)
        stat = diff_output(f"{base_ref}...HEAD", "--shortstat")
        return sum(int(count) for count in re.findall(r"(\d+) (?:insertion|deletion)", stat))

    stat = diff_output(empty_tree(), "--shortstat", pathspecs=targets)
    return sum(int(count) for count in re.findall(r"(\d+) insertion", stat))


def render_handoff(handoff, modifier):
    lines = ["handoff:", "  files:"]
    for entry in handoff["files"]:
        lines.append(f"    - path: {entry['path'].strip()}")
        lines.append(f"      change: {entry['change'].strip()}")
    lines.append(f"  tests-run: {handoff['tests_run'].strip()}")
    lines.append(f"  flagged: {handoff['flagged'].strip()}")

    plan_impact = handoff.get("plan_impact", "none").strip()
    if plan_impact == "none":
        lines.append("  plan_impact: none")
    else:
        lines.append("  plan_impact: |")
        lines += ["    " + line for line in plan_impact.splitlines()]
    lines.append("  iter: 0")
    if modifier:
        lines.append(f"(pass modifier `{modifier}` to /review)")
    return "\n".join(lines)


def review_dispatch_next():
    return next_line("tell the user you are auto-dispatching /review, then Skill-invoke /review with the "
                     "handoff block above (plus any modifier).")


def read_refactor_log(path):
    try:
        refactor_log = json.loads(Path(path).read_text())
    except (OSError, ValueError) as err:
        raise RefactorFlowError(f"cannot read --input {path}: {err}") from err
    if not isinstance(refactor_log, dict):
        raise RefactorFlowError(f"--input {path} must hold a JSON object")
    return refactor_log


def read_modifier(refactor_log):
    modifier = refactor_log.get("modifier")
    if modifier is not None and not isinstance(modifier, str):
        raise RefactorFlowError("`modifier` must be a string")
    return modifier


def build_writes(mode, base, validated_log):
    """Every row this log call writes, as (writer script, key=value pairs)."""
    findings, guards, finder = validated_log["findings"], validated_log["guards"], validated_log["finder"]
    scope = "branch-exit" if mode == "branch" else "standalone"
    writes = []

    # Escape rows: one per distinct smell the model marked; the guard is per class group.
    if mode in ("branch", "simplify"):
        for finding in findings:
            if not finding.get("escape"):
                continue
            pairs = ["stage_found=refactor", "gate_missed=review", f"class={finding['class']}",
                     f"severity={finding['severity']}", f"lane={validated_log['lane']}",
                     f"guard={guards[finding['class']]}", f"desc={finding['desc']}", f"file={finding['file']}"]
            if finding["line"]:
                pairs.append(f"line={finding['line']}")
            writes.append((LOG_ESCAPE, pairs))

    # Finder rows: every mode with a dispatched finder, even empty-handed.
    if finder:
        diff_loc = diff_loc_for(mode, base, validated_log["targets"])
        common = [f"lane={validated_log['lane']}", f"scope={scope}", "phase=-", "iter=0"]
        writes.append((LOG_FINDING, ["kind=run", *common, f"gate={finder}", f"n_findings={len(findings)}",
                                     f"diff_loc={diff_loc}", f"result={validated_log['verdict']}"]))
        for finding in findings:
            writes.append((LOG_FINDING, ["kind=finding", *common, f"gate={finder}",
                                         f"disposition={finding['disposition']}", f"class={finding['class']}",
                                         f"file={finding['file']}", f"line={finding['line']}",
                                         f"actioned={finding['actioned']}", f"desc={finding['desc']}"]))
    return writes


def written_state_file():
    return Path.home() / ".claude" / "state" / "refactor-flow" / "written-rows.json"


def row_hash(root, input_path, script, pairs):
    """Identity of a row. A finder run row is one per input path and gate, whatever else the input says."""
    identity = pairs
    if pairs[0] == "kind=run":
        identity = [pair for pair in pairs if pair.startswith(("kind=", "gate="))]
    content = json.dumps([root, input_path, Path(script).name, identity], ensure_ascii=False)
    return hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()


def load_written_state():
    """{resolved input path: [row hashes]}, oldest input path first. The caller holds the state lock."""
    path = written_state_file()
    if not path.exists():
        return {}
    try:
        state = json.loads(path.read_text())
    except ValueError as err:
        raise RefactorFlowError(f"cannot read {path}: {err}; delete it to reset the dedupe state") from err
    if not isinstance(state, dict):
        raise RefactorFlowError(f"{path} must hold a JSON object; delete it to reset the dedupe state")
    return state


@contextlib.contextmanager
def locked_state_file():
    path = written_state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path.with_suffix(".lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield path


def written_digests(input_path):
    with locked_state_file():
        return set(load_written_state().get(input_path, []))


def record_written(input_path, digest):
    with locked_state_file() as path:
        state = load_written_state()
        digests = state.pop(input_path, [])
        state[input_path] = [*digests, digest]
        for oldest in list(state)[:-MAX_STATE_INPUTS]:
            del state[oldest]

        with tempfile.NamedTemporaryFile("w", dir=path.parent, suffix=".tmp", delete=False) as staged:
            staged.write(json.dumps(state))
        os.replace(staged.name, path)


def count_rows(writes):
    escapes = sum(1 for script, _ in writes if script == LOG_ESCAPE)
    runs = sum(1 for script, pairs in writes if script == LOG_FINDING and pairs[0] == "kind=run")
    findings = sum(1 for script, pairs in writes if script == LOG_FINDING and pairs[0] == "kind=finding")
    return escapes, runs, findings


def write_rows(input_path, pending):
    """Call the writers; returns the (script, pairs, error) of each refused row. Accepted rows are recorded."""
    refused = []
    for script, pairs, digest in pending:
        done = subprocess.run(["bash", script, *pairs], capture_output=True, text=True)
        if done.returncode != 0:
            refused.append((script, pairs, done.stderr.strip()))
            continue
        record_written(input_path, digest)
    return refused


def check_targets_match(mode, validated_log):
    """A target that matches no tracked file would log diff_loc 0 as if the finder had read nothing."""
    if not validated_log["finder"] or mode not in ("audit", "simplify"):
        return
    for target in validated_log["targets"]:
        if not tracked_files([target]):
            raise RefactorFlowError(f"target `{target}` matches no tracked file; log the paths the prep listed")


def log_next(validated_log, mode):
    if validated_log["handoff"]:
        return review_dispatch_next()
    if mode == "audit":
        return next_line("done; report the work list to the user. No coders, no /review.")
    return next_line("no handoff given; if code changed, run `handoff --input FILE` with a `handoff` key "
                     "added, else done.")


def log_verb(opts):
    root = repo_root()
    refactor_log = read_refactor_log(opts.input)
    validated_log = validate_log(opts.mode, refactor_log)
    modifier = read_modifier(refactor_log)
    check_targets_match(opts.mode, validated_log)
    try:
        writes = build_writes(opts.mode, opts.base, validated_log)
    except NoBaseError as err:
        print("Logging: nothing written, the branch has no base to measure its diff against.")
        print(err)
        return 0
    except NoSharedHistoryError as err:
        print("Logging: nothing written, the base and the branch share no history.")
        print(err)
        return 0

    input_path = str(Path(opts.input).resolve())
    already_written = written_digests(input_path)
    pending = []
    for script, pairs in writes:
        digest = row_hash(root, input_path, script, pairs)
        if digest not in already_written:
            pending.append((script, pairs, digest))
    skipped = len(writes) - len(pending)

    escapes, runs, findings = count_rows([(script, pairs) for script, pairs, _ in pending])
    print(f"## Logging ({opts.mode}): {escapes} escape row(s), {runs} finder run row, {findings} finding "
          f"row(s); {skipped} already logged, skipped.")

    if validated_log["handoff"]:
        print()
        print(render_handoff(validated_log["handoff"], modifier))
        print()
    sys.stdout.flush()

    refused = write_rows(input_path, pending)
    for script, pairs, error in refused:
        print(f"writer refused: {script} {' '.join(pairs)}\n{error}", file=sys.stderr)
    if refused:
        print(f"writer refused {len(refused)} row(s), tell the user which")
    print(log_next(validated_log, opts.mode))
    return 2 if refused else 0


def handoff_verb(opts):
    refactor_log = read_refactor_log(opts.input)
    handoff = refactor_log.get("handoff")
    if not handoff:
        raise RefactorFlowError("the input has no `handoff` key")
    validate_handoff(handoff)
    modifier = read_modifier(refactor_log)

    print(render_handoff(handoff, modifier))
    print()
    print(review_dispatch_next())
    return 0


def parse():
    parser = argparse.ArgumentParser(prog="refactor-flow")
    sub = parser.add_subparsers(dest="verb", required=True)
    branch = sub.add_parser("branch-prep")
    branch.add_argument("--head")
    branch.add_argument("--base")
    audit = sub.add_parser("audit-prep")
    audit.add_argument("target")
    audit.add_argument("--jscpd-timeout", type=int, default=120)
    simplify = sub.add_parser("simplify-prep")
    simplify.add_argument("target", nargs="+")
    simplify.add_argument("--slice", type=int, default=1)
    log = sub.add_parser("log")
    log.add_argument("--mode", required=True, choices=["branch", "targeted", "audit", "simplify"])
    log.add_argument("--input", required=True)
    log.add_argument("--base")
    handoff = sub.add_parser("handoff")
    handoff.add_argument("--input", required=True)
    return parser.parse_args()


def main():
    opts = parse()
    handlers = {"branch-prep": branch_prep, "audit-prep": audit_prep, "simplify-prep": simplify_prep,
                "log": log_verb, "handoff": handoff_verb}
    try:
        return handlers[opts.verb](opts)
    except RefactorFlowError as err:
        print(f"refactor-flow: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
