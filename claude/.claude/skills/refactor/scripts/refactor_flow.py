#!/usr/bin/env python3
"""refactor-flow: the fixed steps of the /refactor skill, one call per mode.

  refactor_flow.py branch-prep [--head REF] [--base REF] [--jscpd-timeout SECONDS]
  refactor_flow.py audit-prep <dir> [--jscpd-timeout SECONDS]
  refactor_flow.py simplify-prep <dir|file...> [--slice N] [--diff BASE]
  refactor_flow.py log --mode branch|targeted|audit|simplify --input FILE.json [--base REF]
  refactor_flow.py handoff --input FILE.json

Every verb prints its report and ends with one `NEXT:` line naming what the
model still does, or a `STOP:` line with the reason. Each prep verb deletes all but the newest 49
regular files named `refactor-flow-` plus 12 hex digits plus `.json` (not every `refactor-flow-*.json`), and their
`.simplify-stat` sidecars, in REFACTOR_LOG_INPUT_DIR (default: `git rev-parse --git-path refactor-flow`) before it
names a fresh path. `simplify-prep` also writes that sidecar (the branch-diff record) beside the fresh
input when it finds a base. Otherwise read-only except `log`, which appends rows through the existing writers
(log-escape, log-review-finding); this script never writes a second copy of those rows.
`log` is idempotent per input file: it keeps a hash of every row a writer accepted, grouped by the
resolved --input path, under ~/.claude/state/refactor-flow/ and skips a row already written for that
file. Use one input file per /refactor invocation and re-run `log` on it.
The state keeps the newest 50 input paths. The writers own
the value vocabulary (class, guard, result, ...); this script checks shape only, and refuses
`miss_reason=unknown` (a model writes the input).

Input file (JSON; `log` reads all of it, `handoff` reads only `handoff` and `modifier`):
  {"finder": "smell-reviewer", "lane": "code", "result": "NEEDS CHANGES",
   "target": ["src/orders"],   (audit and simplify: dirs; simplify: the files the prep listed)
   "findings": [{"class": "duplication", "disposition": "fix", "actioned": "fixed",
                 "file": "a.py", "line": 3, "desc": "...", "severity": "medium",
                 "escape": true, "miss_reason": "overlooked"}],   (miss_reason: escape findings only)
   (ruled_by: "user"|"session", disposition=ask only; lets a plan_structure finding be logged actioned=fixed)
   "guards": {"duplication": "convention"},
   "handoff": {"files": [{"path": "a.py", "change": "..."}],   (optional: the printed files are the ones git shows
                changed against HEAD; a listed path keeps its `change`, any other gets a stock line)
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
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts" / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import clone_pairs
import handoff_files
import numstat
import plan_format
import script_utils
import shape_clones
import simplify_flow
import source_text
import sweep_markers
from flow_common import (
    CLAUDE,
    MAX_STATE_INPUTS,
    NoBaseError,
    NoSharedHistoryError,
    RefactorFlowError,
    classify_untracked,
    diff_output,
    fresh_log_input,
    git,
    ls_files,
    next_line,
    pick_base,
    ref_exists,
    require_repo,
    target_files,
    untracked_files,
    work_tree_merge_base,
)

LOG_ESCAPE = os.environ.get("REFACTOR_LOG_ESCAPE") or str(CLAUDE / "scripts" / "telemetry" / "log-escape")
LOG_FINDING = os.environ.get("REFACTOR_LOG_FINDING") or str(CLAUDE / "skills" / "review" / "log-review-finding")

FINDERS = {"smell-reviewer", "complexity-reviewer"}

SMELL_BOUND = ("Your review bound for this run is the whole branch diff (`git diff {base}...{head}`), "
               "not a phase diff.")
SMELL_BOUND_WORK_TREE = ("Your review bound for this run is the whole branch against the work tree "
                         "(`git diff {merge_base}`, committed and uncommitted changes) plus the untracked files "
                         "listed above, not a phase diff.")
UNTRACKED_LABEL = "untracked"
SMELL_PRIORITY = ("Prioritize cross-phase smells — things no single-phase view could see (multi-task "
                  "duplication, drifted naming, orphaned dead code, idiom divergence from unchanged siblings). "
                  "Every finding must carry `file:line` (and the sibling/prior-art `file:line` for duplication).")
PLAN_STRUCTURE_TAG = "[plan-structure]"
PLAN_STRUCTURE_RULE = (f"A finding that would remove, rename, move or reshape anything the plan names (its files, "
                       f"exports, layers) or that a Plan Deviations line records goes under `### Ask` with the "
                       f"`{PLAN_STRUCTURE_TAG}` tag, never under `### Fix`. Read the plan for the exports and "
                       f"layers it names.")
AUDIT_BOUND = ("Audit mode: your bound is the existing code of `{target}` — pre-existing smells ARE the target "
               "this run, per your audit-bound clause.")
AUDIT_ASK = ("Find duplication across files, pattern/idiom drift between sibling modules, and wrong-altitude code. "
             "Each finding carries both `file:line` sites and the consolidation it proposes. Cross-module "
             "consolidations or anything moving a public contract are `[design-decision]`.")
AUDIT_CANDIDATES = ("Judge each candidate against the anti-churn line — must-stay-in-sync (flag, name the "
                    "extraction) vs looks-a-bit-similar (suppress).")
AUDIT_NO_PAIRS_TEXT = "jscpd ran and found no clone pairs"
BRANCH_PAIR_SCOPE = " on changed lines"
BRANCH_NO_PAIRS_TEXT = "jscpd found no clone pair on changed lines"
BRANCH_CANDIDATES = ("Each pair has a site on a line this branch changed. A new helper that repeats a helper "
                     "elsewhere in the repo is a duplication finding: name the existing one to reuse. "
                     "Apply the anti-churn line before you flag a pair.")


def empty_tree():
    """The empty tree id in this repo's hash algorithm (SHA-1 or SHA-256)."""
    return git("hash-object", "-t", "tree", "/dev/null").stdout.strip()


def parse_branch_diff(diff_text):
    """The parsed diff files (source_text.FileDiff) of the branch diff."""
    try:
        return source_text.parse_unified_diff(diff_text)
    except ValueError as error:
        raise RefactorFlowError(f"cannot parse the branch diff: {error}") from error


def post_image_reader(root, head):
    """A function path -> the file's lines after the branch's change: the work tree file, or the file at `head`.
    None for a work-tree symlink, whose diff lines are not file text."""
    def read_post_image(file_path):
        if head:
            return git("show", "--no-textconv", f"{head}:{file_path}").stdout.split("\n")
        full_path = Path(root) / file_path
        if full_path.is_symlink():
            return None
        try:
            return full_path.read_bytes().decode("utf-8", errors="replace").split("\n")
        except OSError as error:
            raise RefactorFlowError(f"cannot read {full_path} for the sweep: {error}") from error
    return read_post_image


def binary_paths(numstat_text):
    """Paths git reports as binary in `diff --numstat -z`."""
    return {path for added, _deleted, path in numstat.numstat_rows(numstat_text) if added is None}


def labelled_span_files(span):
    """(path, label) for each file in the span; the label names deleted, renamed, copied and binary files."""
    tokens = diff_output(span, "--name-status", "-z").split("\0")
    binary = binary_paths(diff_output(span, "--numstat", "-z"))
    entries = []
    index = 0
    while index < len(tokens) and tokens[index]:
        code = tokens[index][0]
        if code in "RC":
            old_path, path = tokens[index + 1], tokens[index + 2]
            labels = [("renamed" if code == "R" else "copied") + f" from {old_path}"]
            index += 3
        else:
            path = tokens[index + 1]
            labels = ["deleted"] if code == "D" else []
            index += 2
        if path in binary:
            labels.append("binary")
        entries.append((path, ", ".join(labels)))
    return entries


def untracked_label(entry):
    return f"{UNTRACKED_LABEL}, {entry.kind}" if entry.kind else UNTRACKED_LABEL


def file_line(path, label):
    return f"- {path} ({label})" if label else f"- {path}"


def span_plans(files):
    """The plan files the branch adds or changes: the plans /code works from are committed on the branch."""
    return [path for path, label in files
            if "deleted" not in label and PurePosixPath(path).match(plan_format.PLAN_FILES_GLOB)]


def read_plan_text(plan_path, head, root):
    """A plan as of `head`; with no head, the plan as it sits in the work tree."""
    if head is None:
        try:
            return (Path(root) / plan_path).read_text()
        except (OSError, UnicodeDecodeError) as error:
            raise RefactorFlowError(f"cannot read the plan {plan_path}: {error}") from error
    return git("show", f"{head}:{plan_path}").stdout


def print_plan_structure(plan_paths, head, root):
    for plan_path in plan_paths:
        plan_text = read_plan_text(plan_path, head, root)
        structure = plan_format.required_structure(plan_text.splitlines())
        print(f"## Plan-required structure (`{plan_path}`)")
        print("Files the plan's phases name:")
        for named_path in structure["files"]:
            print(f"- {named_path}")
        if not structure["files"]:
            print("- none")
        print(f"{plan_format.DEVIATIONS_HEADING}:")
        for deviation in structure["deviations"]:
            print(deviation)
        if not structure["deviations"]:
            print("- none")
    print(PLAN_STRUCTURE_RULE)


def _sweep_text(matches):
    lines = [f"## Mechanical sweep ({len(matches)} match(es)) — straight onto the work list"]
    for path, line, kind, text in matches:
        lines.append(f"- {path}:{line} [{kind}] {text[:120]}")
    if not matches:
        lines.append("- none")
    return "\n".join(lines)


def _smell_bound(base, opts_head, diff_ref):
    if opts_head:
        return SMELL_BOUND.format(base=base, head=opts_head)
    return SMELL_BOUND_WORK_TREE.format(merge_base=diff_ref)


def _print_smell_prompt(files, bound, plan_head, root):
    print("## smell-reviewer dispatch prompt (pinned; omit `model` unless +fast)")
    print("Changed files:")
    for path, label in files:
        print(file_line(path, label))
    print(bound)
    print(SMELL_PRIORITY)
    plan_paths = span_plans(files)
    if plan_paths:
        print_plan_structure(plan_paths, plan_head, root)


class BranchSpan(NamedTuple):
    """What branch-prep reads: committed changes, plus the work tree and untracked files when no --head is named."""
    diff_ref: str  # `base...head` for --head, else the merge-base commit (git diff <commit> reads the work tree)
    files: list  # (path, label)
    diff_text: str  # the -U0 diff of committed (and, with no --head, uncommitted) changes
    shortstat: str
    untracked: list  # UntrackedFile entries; empty with --head


def read_branch_span(base, opts_head, root):
    if opts_head:
        diff_ref = f"{base}...{opts_head}"
        untracked = []
    else:
        diff_ref = work_tree_merge_base(base)
        untracked = untracked_files(root)

    files = labelled_span_files(diff_ref)
    files += [(entry.path, untracked_label(entry)) for entry in untracked]
    shortstat_parts = [diff_output(diff_ref, "--shortstat").strip()]
    if untracked:
        shortstat_parts.append(f"{len(untracked)} untracked file(s)")
    shortstat = "; ".join(part for part in shortstat_parts if part)
    return BranchSpan(diff_ref, files, diff_output(diff_ref, "-U0"), shortstat, untracked)


def branch_prep(opts):
    root = require_repo()
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

    try:
        span = read_branch_span(base, opts.head, root)
    except NoSharedHistoryError as err:
        print(f"Branch audit: `{base}` and `{head}` have no merge base.")
        print(err)
        return 0
    if not span.files:
        no_untracked = "" if opts.head else " and no file is untracked"
        print(f"Branch audit: `git diff --name-only {span.diff_ref}` is empty{no_untracked} "
              f"(base `{base}` from {base_source}).")
        print("STOP: tell the user the branch diff is empty. Dispatch nothing.")
        return 0

    _print_branch_report(span, base, base_source, opts.head, root, opts.jscpd_timeout)
    return 0


def _print_branch_report(span, base, base_source, opts_head, root, jscpd_timeout):
    log_input = fresh_log_input()
    diff_files = parse_branch_diff(span.diff_text)
    read_post_image = post_image_reader(root, opts_head)
    try:
        tracked_matches = sweep_markers.sweep_matches(diff_files, read_post_image)
        untracked_matches = sweep_markers.untracked_matches(span.untracked)
    except sweep_markers.PostImageMismatchError as error:
        raise RefactorFlowError(f"the sweep cannot trust the file it read: {error}") from error
    matches = tracked_matches + untracked_matches
    scope_head = f"head `{opts_head}`" if opts_head else "the work tree"
    if opts_head:
        pairs, note = [], clone_pairs.HEAD_MODE_NOTE
        shapes = shape_clones.skipped_result(clone_pairs.HEAD_MODE_NOTE)
    else:
        pairs, note = clone_pairs.branch_pairs(diff_files, span.untracked, root, jscpd_timeout)
        shapes = shape_clones.branch_shapes(diff_files, span.untracked, root)
    clone_line = clone_pairs.clone_summary_line(pairs, note, BRANCH_NO_PAIRS_TEXT, BRANCH_PAIR_SCOPE)

    print(f"## Branch audit scope (base `{base}` from {base_source}, {scope_head})")
    print(f"Changed files ({len(span.files)}); {span.shortstat}")
    print(clone_line)
    print(shape_clones.shape_summary_line(shapes))
    print(f"\n{_sweep_text(matches)}\n")
    bound = _smell_bound(base, opts_head, span.diff_ref)
    _print_smell_prompt(span.files, bound, opts_head, root)
    if pairs:
        clone_pairs.print_candidate_pairs(pairs, BRANCH_CANDIDATES)
    shape_clones.print_candidates(shapes)
    print()
    print(_branch_next(base, log_input))


def _branch_next(base, log_input):
    return next_line("dispatch ONE smell-reviewer with the prompt above; make the work list = findings + sweep "
                     f"matches (`[design-decision]` and every `### Ask` finding go to the user; log a "
                     f"`{PLAN_STRUCTURE_TAG}` finding with `plan_structure: true`); then dispatch the coder, "
                     "run the step-5 test audit when the refactor could change test guarantees, run the ratchet "
                     f"for each distinct class, write the log input to {log_input}, and call "
                     f"`log --mode branch --base {base} --input {log_input}`. Nothing found: call the same "
                     "`log` empty-handed and stop.")


def audit_prep(opts):
    require_repo()
    target = opts.target
    files = target_files([target])
    if not files:
        print(f"STOP: `{target}` holds no tracked or untracked (not ignored) file; ask the user for a dir or module.")
        return 0
    log_input = fresh_log_input()
    pairs, note = clone_pairs.run_jscpd(target, opts.jscpd_timeout)

    print(f"## Audit target `{target}` ({len(files)} file(s))")
    print()
    print(f"## Mechanical clone detection (jscpd, --min-tokens {clone_pairs.AUDIT_MIN_TOKENS})")
    print(clone_pairs.clone_summary_line(pairs, note, AUDIT_NO_PAIRS_TEXT))
    print()
    print("## smell-reviewer dispatch prompt (omit `model` unless +fast)")
    print(AUDIT_BOUND.format(target=target))
    if pairs:
        clone_pairs.print_candidate_pairs(pairs, AUDIT_CANDIDATES)
    print(AUDIT_ASK)
    print()
    print(next_line("dispatch ONE smell-reviewer with the prompt above; report the work list with each "
                    "finding's route (targeted /refactor, or /eng-spec for design-decision); then "
                    f"write the log input to {log_input} and call `log --mode audit --input {log_input}` with "
                    f"target [\"{target}\"] (finder rows only; no escape rows, no coders, no /review)."))
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
    plan_structure = finding.get("plan_structure", False)
    if not isinstance(plan_structure, bool):
        raise RefactorFlowError(f"{where}: `plan_structure` must be true or false (got {plan_structure!r})")
    ruled_by = finding.get("ruled_by")
    if ruled_by is not None and not plan_format.is_ruling_by(ruled_by):
        raise RefactorFlowError(f"{where}: `ruled_by` must be `user` or `session` (got {ruled_by!r})")
    if plan_structure and finding["disposition"] != "ask":
        raise RefactorFlowError(f"{where}: a {PLAN_STRUCTURE_TAG} finding is an ask the user answers: "
                                f"disposition=ask")
    if ruled_by is not None and finding["disposition"] != "ask":
        raise RefactorFlowError(f"{where}: `ruled_by` names who ruled on an ask: disposition=ask")
    if plan_structure and finding["actioned"] == "fixed" and ruled_by is None:
        raise RefactorFlowError(f"{where}: a {PLAN_STRUCTURE_TAG} finding is an ask the user answers: "
                                f"never actioned=fixed without `ruled_by` (`user` or `session`)")
    if not isinstance(finding.get("escape", False), bool):
        raise RefactorFlowError(f"{where}: `escape` must be true or false (got {finding['escape']!r})")
    if finding.get("escape"):
        validate_escape_finding(finding, where, mode)


def validate_escape_finding(finding, where, mode):
    """The extra checks for a finding marked as an escape."""
    if mode in ("audit", "targeted"):
        raise RefactorFlowError(f"{where}: escape rows are not logged in {mode} mode")
    if mode == "simplify" and finding["class"] != "complexity":
        raise RefactorFlowError(f"{where}: simplify escape rows must be class=complexity")
    require_text(finding, "severity", where)
    # The writer's --check owns the label list; a model writes this input, so `unknown` is refused here.
    miss_reason = finding.get("miss_reason")
    if not isinstance(miss_reason, str) or miss_reason in ("", "unknown"):
        raise RefactorFlowError(f"{where}: an escape finding needs `miss_reason`, a label from "
                                f"escape-ratchet.md other than `unknown` (got {miss_reason!r})")


def validate_handoff(handoff):
    if not isinstance(handoff, dict):
        raise RefactorFlowError("`handoff` must be an object")
    files = handoff.get("files", [])
    if not isinstance(files, list):
        raise RefactorFlowError("handoff.files must be a list of {path, change}; the file list comes from git")

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


def require_escape_guards(findings, guards):
    escape_classes = sorted({finding["class"] for finding in findings if finding.get("escape")})
    for escape_class in escape_classes:
        if not isinstance(guards.get(escape_class), str) or not guards[escape_class]:
            raise RefactorFlowError(f"escape class `{escape_class}` needs guards[\"{escape_class}\"] (run the ratchet)")


def validated_targets(refactor_log, finder, mode):
    targets = refactor_log.get("target") or []
    if not isinstance(targets, list) or not all(isinstance(item, str) and item for item in targets):
        raise RefactorFlowError("`target` must be a list of paths")
    if finder and mode in ("audit", "simplify") and not targets:
        raise RefactorFlowError("`target` (list of dirs or files) is required in audit and simplify mode")
    return targets


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
    require_escape_guards(findings, guards)

    verdict = refactor_log.get("result") or ("NEEDS CHANGES" if findings else "PASS")
    if not isinstance(verdict, str):
        raise RefactorFlowError("`result` must be a string")

    targets = validated_targets(refactor_log, finder, mode)

    handoff = refactor_log.get("handoff")
    if mode == "audit" and handoff:
        raise RefactorFlowError("audit mode never hands off to /review")
    if handoff:
        validate_handoff(handoff)

    return {"finder": finder, "lane": lane, "findings": findings, "guards": guards, "verdict": verdict,
            "targets": targets, "handoff": handoff}


def untracked_line_count(live_targets):
    """Lines in the untracked (not ignored) text files under the targets; `git diff` never sees them."""
    total = 0
    for name in ls_files(live_targets, "--others"):
        total += len(classify_untracked(".", name).added_lines)
    return total


def diff_loc_for(mode, base, targets):
    """The committed branch diff size (not the uncommitted or untracked work the finder also read), or the line count
    of the files it received."""
    if mode == "branch":
        base_ref, _ = pick_base(base)
        stat = diff_output(f"{base_ref}...HEAD", "--shortstat")
        return sum(int(count) for count in re.findall(r"(\d+) (?:insertion|deletion)", stat))

    live = [target for target in targets if target_files([target])]
    # A repo with no commit has nothing deleted from HEAD.
    deleted_names = ""
    if ref_exists("HEAD"):
        deleted_names = diff_output("HEAD", "--name-only", "-z", "--diff-filter=D", pathspecs=targets)
    deleted = [name for name in deleted_names.split("\0") if name]
    tree = empty_tree()
    stat = diff_output(tree, "--shortstat", pathspecs=live) if live else ""
    # A file deleted in the index adds no lines to the work tree; the finder read it at HEAD.
    deleted_stat = diff_output(f"{tree}..HEAD", "--shortstat", pathspecs=deleted) if deleted else ""
    tracked_lines = sum(int(count) for count in re.findall(r"(\d+) insertion", stat + deleted_stat))
    return tracked_lines + untracked_line_count(live)


def render_handoff(root, handoff, modifier):
    """The review handoff block. Its files are the ones git shows changed against HEAD in root (the refactor's edits
    are uncommitted, and no commit marks where they started), untracked files included. The `change` text of a
    handoff.files entry is kept for the path it names."""
    change_by_path = {entry["path"].strip(): entry["change"].strip() for entry in handoff.get("files", [])}
    changed = script_utils.changed_files(root, "HEAD")
    lines = ["handoff:", "  files: []" if not changed else "  files:"]
    lines += handoff_files.file_entry_lines(changed, change_by_path, "changed in the working tree against HEAD")
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


REVIEW_DISPATCH_STEP = ("tell the user you are auto-dispatching /review, then Skill-invoke /review with the "
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
    writes = []
    # Escape rows: one per distinct smell the model marked; the guard is per class group.
    if mode in ("branch", "simplify"):
        writes += escape_row_writes(validated_log)

    # Finder rows: every mode with a dispatched finder, even empty-handed.
    if validated_log["finder"]:
        writes += finder_row_writes(mode, base, validated_log)
    return writes


def escape_row_writes(validated_log):
    escape_findings = [finding for finding in validated_log["findings"] if finding.get("escape")]
    return [(LOG_ESCAPE, escape_row_pairs(finding, validated_log)) for finding in escape_findings]


def escape_row_pairs(finding, validated_log):
    pairs = ["stage_found=refactor", "gate_missed=review", f"class={finding['class']}",
             f"severity={finding['severity']}", f"lane={validated_log['lane']}",
             f"guard={validated_log['guards'][finding['class']]}", f"miss_reason={finding['miss_reason']}",
             f"desc={finding['desc']}", f"file={finding['file']}"]
    if finding["line"]:
        pairs.append(f"line={finding['line']}")
    return pairs


def finder_row_writes(mode, base, validated_log):
    """The finder's run row, then one row per finding."""
    findings, finder = validated_log["findings"], validated_log["finder"]
    scope = "branch-exit" if mode == "branch" else "standalone"
    diff_loc = diff_loc_for(mode, base, validated_log["targets"])
    common = [f"lane={validated_log['lane']}", f"scope={scope}", "phase=-", "iter=0"]
    writes = [(LOG_FINDING, ["kind=run", *common, f"gate={finder}", f"n_findings={len(findings)}",
                             f"diff_loc={diff_loc}", f"result={validated_log['verdict']}"])]
    for finding in findings:
        pairs = ["kind=finding", *common, f"gate={finder}",
                 f"disposition={finding['disposition']}", f"class={finding['class']}",
                 f"file={finding['file']}", f"line={finding['line']}",
                 f"actioned={finding['actioned']}", f"desc={finding['desc']}"]
        if finding.get("ruled_by"):
            pairs.append(f"ask_decided_by={finding['ruled_by']}")
        writes.append((LOG_FINDING, pairs))
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


class RowCounts(NamedTuple):
    escapes: int
    runs: int
    findings: int


def count_rows(writes):
    escapes = sum(1 for script, _ in writes if script == LOG_ESCAPE)
    runs = sum(1 for script, pairs in writes if script == LOG_FINDING and pairs[0] == "kind=run")
    findings = sum(1 for script, pairs in writes if script == LOG_FINDING and pairs[0] == "kind=finding")
    return RowCounts(escapes, runs, findings)


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


def check_writer_rows(writes):
    """The writer owns the run and escape rows' vocabulary; its --check refuses a bad row before anything is written."""
    for script, pairs in writes:
        is_run_row = script == LOG_FINDING and pairs[0] == "kind=run"
        if script != LOG_ESCAPE and not is_run_row:
            continue
        done = subprocess.run(["bash", script, "--check", *pairs], capture_output=True, text=True)
        if done.returncode != 0:
            kind = "escape" if script == LOG_ESCAPE else "run"
            raise RefactorFlowError(f"writer refused the {kind} row, nothing written:\n{done.stderr.strip()}")


def tracked_at_head(target):
    """True when the target names a file in the HEAD tree."""
    done = git("--literal-pathspecs", "ls-tree", "-r", "--name-only", "-z", "HEAD", "--", target, check=False)
    if done.returncode != 0:
        raise RefactorFlowError(f"git ls-tree failed for {target}: {done.stderr.strip()}")
    return bool(done.stdout.strip("\0"))


def check_targets_match(mode, validated_log):
    """A target that matches no tracked or untracked file would log diff_loc 0 as if the finder had read nothing.
    A target the branch deleted (tracked at HEAD, gone from the index) is the slice that ran: it is accepted,
    and diff_loc_for counts its lines from HEAD."""
    if not validated_log["finder"] or mode not in ("audit", "simplify"):
        return
    for target in validated_log["targets"]:
        if target_files([target]):
            continue
        if tracked_at_head(target):
            print(f"target `{target}` is deleted in the index (tracked at HEAD)")
            continue
        raise RefactorFlowError(
            f"target `{target}` matches no file (tracked or untracked); log the paths the prep listed"
        )


def log_next(validated_log, mode):
    if validated_log["handoff"]:
        return REVIEW_DISPATCH_STEP
    if mode == "audit":
        return "done; report the work list to the user. No coders, no /review."
    return ("no handoff given; if code changed, run `handoff --input FILE` with a `handoff` key "
            "added, else done.")


def final_line(comparison, validated_log, mode):
    """The last line `log` prints. The grown-diff STOP carries the step `log_next` would print, after the user's
    ruling."""
    step = log_next(validated_log, mode)
    if not (comparison and comparison.stop):
        return next_line(step)
    return f"{comparison.stop} After they rule: {step}"


def pending_rows(root, input_path, writes):
    """The (script, pairs, digest) of each row not yet written for this input file."""
    already_written = written_digests(input_path)
    pending = []
    for script, pairs in writes:
        digest = row_hash(root, input_path, script, pairs)
        if digest not in already_written:
            pending.append((script, pairs, digest))
    return pending


def log_verb(opts):
    root = require_repo()
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

    check_writer_rows(writes)

    comparison = None
    if opts.mode == "simplify":
        comparison = simplify_flow.compare_branch_diff(opts.input, root)

    input_path = str(Path(opts.input).resolve())
    pending = pending_rows(root, input_path, writes)
    skipped = len(writes) - len(pending)

    counts = count_rows([(script, pairs) for script, pairs, _ in pending])
    print(f"## Logging ({opts.mode}): {counts.escapes} escape row(s), {counts.runs} finder run row, "
          f"{counts.findings} finding row(s); {skipped} already logged, skipped.")
    if comparison:
        print("\n".join(comparison.lines))

    if validated_log["handoff"]:
        print()
        print(render_handoff(root, validated_log["handoff"], modifier))
        print()
    sys.stdout.flush()

    refused = write_rows(input_path, pending)
    for script, pairs, error in refused:
        print(f"writer refused: {script} {' '.join(pairs)}\n{error}", file=sys.stderr)
    if refused:
        print(f"writer refused {len(refused)} row(s), tell the user which")
    print(final_line(comparison, validated_log, opts.mode))
    return 2 if refused else 0


def handoff_verb(opts):
    root = require_repo()
    refactor_log = read_refactor_log(opts.input)
    handoff = refactor_log.get("handoff")
    if not handoff:
        raise RefactorFlowError("the input has no `handoff` key")
    validate_handoff(handoff)
    modifier = read_modifier(refactor_log)

    print(render_handoff(root, handoff, modifier))
    print()
    print(next_line(REVIEW_DISPATCH_STEP))
    return 0


def parse_arguments():
    parser = argparse.ArgumentParser(prog="refactor-flow")
    sub = parser.add_subparsers(dest="verb", required=True)
    branch = sub.add_parser("branch-prep")
    branch.add_argument("--head")
    branch.add_argument("--base")
    branch.add_argument("--jscpd-timeout", type=int, default=clone_pairs.JSCPD_TIMEOUT_SECONDS)
    audit = sub.add_parser("audit-prep")
    audit.add_argument("target")
    audit.add_argument("--jscpd-timeout", type=int, default=clone_pairs.JSCPD_TIMEOUT_SECONDS)
    simplify = sub.add_parser("simplify-prep")
    simplify.add_argument("target", nargs="+")
    simplify.add_argument("--slice", type=int, default=1)
    simplify.add_argument("--diff", metavar="BASE")
    log = sub.add_parser("log")
    log.add_argument("--mode", required=True, choices=["branch", "targeted", "audit", "simplify"])
    log.add_argument("--input", required=True)
    log.add_argument("--base")
    handoff = sub.add_parser("handoff")
    handoff.add_argument("--input", required=True)
    return parser.parse_args()


def main():
    opts = parse_arguments()
    handlers = {"branch-prep": branch_prep, "audit-prep": audit_prep, "simplify-prep": simplify_flow.simplify_prep,
                "log": log_verb, "handoff": handoff_verb}
    try:
        return handlers[opts.verb](opts)
    except RefactorFlowError as err:
        print(f"refactor-flow: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
