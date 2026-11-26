#!/usr/bin/env python3
"""refactor-flow: the fixed steps of the /refactor skill, one call per mode.

  refactor_flow.py branch-prep [--head REF] [--base REF] [--jscpd-timeout SECONDS]
  refactor_flow.py audit-prep <dir> [--jscpd-timeout SECONDS]
  refactor_flow.py simplify-prep <dir|file...> [--slice N]
  refactor_flow.py log --mode branch|targeted|audit|simplify --input FILE.json [--base REF]
  refactor_flow.py handoff --input FILE.json

Every verb prints its report and ends with one `NEXT:` line naming what the
model still does, or a `STOP:` line with the reason. Each prep verb deletes all but the newest 49
regular files named `refactor-flow-` plus 12 hex digits plus `.json` (not every `refactor-flow-*.json`)
in REFACTOR_LOG_INPUT_DIR (default: `git rev-parse --git-path refactor-flow`) before it names a fresh path.
Otherwise read-only except `log`, which appends rows through the existing writers
(log-escape, log-review-finding); this script never writes a second copy of those rows.
`log` is idempotent per input file: it keeps a hash of every row a writer accepted, grouped by the
resolved --input path, under ~/.claude/state/refactor-flow/ and skips a row already written for that
file. Use one input file per /refactor invocation and re-run `log` on it.
The state keeps the newest 50 input paths. The writers own
the value vocabulary (class, guard, result, ...); this script checks shape only, and refuses
`miss_reason=unknown` (a model writes the input).

Input file: JSON in the shape `refactor_flow.py log --help` prints; `log` reads all of it, `handoff` reads only
`handoff` and `modifier`.
Exit codes: 0 ok or a clean stop, 1 bad input (nothing was written), 2 a writer refused a row.
"""
import argparse
import contextlib
import fcntl
import functools
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path, PurePosixPath
from stat import S_ISREG
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts" / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import clone_pairs
import handoff_files
import numstat
import plan_format
import refactor_log_input
import script_utils
import shape_clones
import simplify_slices
import single_caller_census
import source_text
import sweep_markers

CLAUDE = Path(os.environ.get("REFACTOR_CLAUDE_DIR", Path(__file__).resolve().parents[3]))
LOG_ESCAPE = os.environ.get("REFACTOR_LOG_ESCAPE") or str(CLAUDE / "scripts" / "telemetry" / "log-escape")
LOG_FINDING = os.environ.get("REFACTOR_LOG_FINDING") or str(CLAUDE / "skills" / "review" / "log-review-finding")
BRANCH_BASE = os.environ.get("BRANCH_BASE_SCRIPT") or str(CLAUDE / "scripts" / "tools" / "branch-base")

RefactorFlowError = refactor_log_input.RefactorFlowError
PLAN_STRUCTURE_TAG = refactor_log_input.PLAN_STRUCTURE_TAG
MAX_SIMPLIFY_FILES = 25
MAX_STATE_INPUTS = 50
MAX_LOG_INPUTS = MAX_STATE_INPUTS
LOG_INPUT_PREFIX = "refactor-flow-"
LOG_INPUT_HEX_DIGITS = 12
LOG_INPUT_NAME = re.compile(re.escape(LOG_INPUT_PREFIX) + rf"[0-9a-f]{{{LOG_INPUT_HEX_DIGITS}}}\.json")

SMELL_BOUND = ("Your review bound for this run is the whole branch diff (`git diff {base}...{head}`), "
               "not a phase diff.")
SMELL_BOUND_WORK_TREE = ("Your review bound for this run is the whole branch against the work tree "
                         "(`git diff {merge_base}`, committed and uncommitted changes) plus the untracked files "
                         "listed above, not a phase diff.")
UNTRACKED_LABEL = "untracked"
UNTRACKED_SYMLINK = "symlink"
UNTRACKED_NOT_A_FILE = "not a file"
UNTRACKED_BINARY = "binary"
SMELL_PRIORITY = ("Prioritize cross-phase smells — things no single-phase view could see (multi-task "
                  "duplication, drifted naming, orphaned dead code, idiom divergence from unchanged siblings). "
                  "Every finding must carry `file:line` (and the sibling/prior-art `file:line` for duplication).")
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
SIMPLIFY_BOUND = ("Simplify mode: your bound is the whole existing code of `{target}`. Pre-existing shape IS "
                  "the target.")
SIMPLIFY_ASK = ("Find what could be deleted if this module were shaped differently: branching a data model "
                "collapses, indirection with one implementation, configurability nothing configures, guards a "
                "stronger invariant kills, values with more than one owner. Your oracle and magnitude floor are "
                "hard gates (quantified disappearance, enabling change, unreachability proof, cost clause).")
NO_HISTORY_STOP = "STOP: {base} and {head} share no history; ask the user for --base."


class NoSharedHistoryError(RefactorFlowError):
    """The base and the head have no merge base (orphan branch, shallow clone)."""


class NoBaseError(RefactorFlowError):
    """The branch-base helper found no base; the message is its `STOP:` line."""


run = functools.partial(script_utils.run_or_raise, error_type=RefactorFlowError, check=True)


def git(*args, check=True):
    return run(["git", *args], check=check)


def require_repo():
    root = script_utils.repo_root(".")
    if root is None:
        raise RefactorFlowError("not inside a git repository")
    return str(root)


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
               "--no-textconv", "--no-relative", "--no-prefix", *args, span, *limit,
               check=False)
    if done.returncode == 0:
        return done.stdout
    if "no merge base" in done.stderr:
        base, _, head = span.partition("...")
        raise NoSharedHistoryError(NO_HISTORY_STOP.format(base=base, head=head))
    raise RefactorFlowError(f"`git diff {span}` failed: {done.stderr.strip()}")


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


def work_tree_merge_base(base):
    """The commit the work-tree span starts from: where HEAD left `base`."""
    done = git("merge-base", base, "HEAD", check=False)
    if done.returncode == 1 and not done.stderr.strip():
        raise NoSharedHistoryError(NO_HISTORY_STOP.format(base=base, head="HEAD"))
    if done.returncode != 0:
        raise RefactorFlowError(f"`git merge-base {base} HEAD` failed: {done.stderr.strip()}")
    return done.stdout.strip()


class UntrackedFile(NamedTuple):
    path: str
    added_lines: list  # (line number, text) pairs; empty when kind is set
    kind: str  # why a file is not read as text: UNTRACKED_SYMLINK, UNTRACKED_NOT_A_FILE, UNTRACKED_BINARY; else ""


def untracked_files(root):
    """Untracked files git does not ignore, root-relative; a symlink, a non-regular entry or a file that cannot be
    read as UTF-8 text is listed with its kind and no lines."""
    names = script_utils.untracked_paths(root)
    if names is None:
        raise RefactorFlowError(f"git could not list the untracked files in {root}")
    return [classify_untracked(root, name) for name in names]


def classify_untracked(root, name):
    """One untracked file, with its lines when it is a regular UTF-8 text file."""
    full_path = Path(root) / name
    if full_path.is_symlink():
        return UntrackedFile(name, [], UNTRACKED_SYMLINK)
    if not full_path.is_file():
        return UntrackedFile(name, [], UNTRACKED_NOT_A_FILE)
    numbered = script_utils.read_text_lines(full_path)
    if numbered is None:
        return UntrackedFile(name, [], UNTRACKED_BINARY)
    return UntrackedFile(name, numbered, "")


def untracked_label(entry):
    return f"{UNTRACKED_LABEL}, {entry.kind}" if entry.kind else UNTRACKED_LABEL


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


def log_input_folder():
    """REFACTOR_LOG_INPUT_DIR, else the repo's own git dir, which outlives the system temp folder."""
    override = os.environ.get("REFACTOR_LOG_INPUT_DIR")
    if override:
        return Path(override)
    folder = script_utils.git_path(".", "refactor-flow")
    if folder is None:
        raise RefactorFlowError("git could not give the refactor-flow folder of this repo")
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def fresh_log_input():
    """A path no earlier /refactor invocation used; `log` dedupes rows per input path."""
    folder = log_input_folder()
    prune_log_inputs(folder)
    return str(folder / f"{LOG_INPUT_PREFIX}{uuid.uuid4().hex[:LOG_INPUT_HEX_DIGITS]}.json")


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
    if opts_head:
        print(single_caller_census.CENSUS_HEADING)
        print("The census reads only the work tree; it was not run for --head.")
    else:
        print("\n".join(single_caller_census.census_report_lines(root, span.diff_ref)))
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


def ls_files(targets, *flags):
    """Files under the target paths (relative to the cwd) that `git ls-files` lists for the flags.

    Ignored files are left out.
    """
    done = git("--literal-pathspecs", "ls-files", "-z", *flags, "--exclude-standard", "--", *targets, check=False)
    if done.returncode != 0:
        raise RefactorFlowError(f"git ls-files failed for {targets}: {done.stderr.strip()}")
    return [name for name in done.stdout.split("\0") if name]


def target_files(target):
    """Tracked and untracked (not ignored) files under the target paths, relative to the cwd."""
    return ls_files(target, "--cached", "--others")


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


def _print_complexity_prompt(chosen, label):
    print("## complexity-reviewer dispatch prompt (pinned; omit `model`; never +fast)")
    print("Files:")
    for name in chosen:
        print(f"- {name}")
    print(SIMPLIFY_BOUND.format(target=label))
    print(SIMPLIFY_ASK)
    print("Add any project constraint you know that makes a shape mandatory (a required layer, a framework "
          "seam, a public contract).")


def simplify_prep(opts):
    require_repo()
    targets = opts.target
    files_by_target = []
    for target in targets:
        found = target_files([target])
        if not found:
            print(
                f"STOP: `{target}` holds no tracked or untracked (not ignored) file; "
                "ask the user for a dir or module."
            )
            return 0
        files_by_target.append((target, found))
    return _simplify_report(opts, files_by_target)


def _simplify_report(opts, files_by_target):
    label = " ".join(target for target, _files in files_by_target)
    try:
        plan = simplify_slices.plan_slices(files_by_target, MAX_SIMPLIFY_FILES)
    except simplify_slices.SliceError as error:
        raise RefactorFlowError(f"simplify-prep: {error}") from error
    dropped_text = simplify_slices.dropped_summary(plan.dropped)
    slices = plan.slices
    if not slices:
        print(f"STOP: `{label}` holds only test, index, style or generated files ({dropped_text} "
              f"dropped); ask the user for a source dir or module.")
        return 0
    if not 1 <= opts.slice <= len(slices):
        raise RefactorFlowError(f"--slice {opts.slice} out of range 1..{len(slices)}")
    chosen = slices[opts.slice - 1]
    log_input = fresh_log_input()

    print(f"## Simplify target `{label}` ({plan.kept} source file(s))")
    print(f"Dropped as not source: {dropped_text} file(s).")
    if len(slices) > 1:
        print(f"Over {MAX_SIMPLIFY_FILES} files: split into {len(slices)} slices along module folders. This run "
              f"is slice {opts.slice} of {len(slices)} ({len(chosen.files)} files); modules: "
              f"{', '.join(chosen.modules)}; tell the user which slice runs, "
              f"re-run with `--slice N` for the others.")
    print()
    _print_complexity_prompt(chosen.files, label)
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


def review_dispatch_next():
    return next_line("tell the user you are auto-dispatching /review, then Skill-invoke /review with the "
                     "handoff block above (plus any modifier).")


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
        return review_dispatch_next()
    if mode == "audit":
        return next_line("done; report the work list to the user. No coders, no /review.")
    return next_line("no handoff given; if code changed, run `handoff --input FILE` with a `handoff` key "
                     "added, else done.")


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
    refactor_log = refactor_log_input.read_refactor_log(opts.input)
    validated_log = refactor_log_input.validate_log(opts.mode, refactor_log)
    modifier = refactor_log_input.read_modifier(refactor_log)
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

    input_path = str(Path(opts.input).resolve())
    pending = pending_rows(root, input_path, writes)
    skipped = len(writes) - len(pending)

    counts = count_rows([(script, pairs) for script, pairs, _ in pending])
    print(f"## Logging ({opts.mode}): {counts.escapes} escape row(s), {counts.runs} finder run row, "
          f"{counts.findings} finding row(s); {skipped} already logged, skipped.")

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
    print(log_next(validated_log, opts.mode))
    return 2 if refused else 0


def handoff_verb(opts):
    root = require_repo()
    refactor_log = refactor_log_input.read_refactor_log(opts.input)
    handoff = refactor_log.get("handoff")
    if not handoff:
        raise RefactorFlowError("the input has no `handoff` key")
    refactor_log_input.validate_handoff(handoff)
    modifier = refactor_log_input.read_modifier(refactor_log)

    print(render_handoff(root, handoff, modifier))
    print()
    print(review_dispatch_next())
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
    log = sub.add_parser("log", help="append the escape and finder rows of one /refactor run",
                         epilog=refactor_log_input.log_help_epilog(),
                         formatter_class=argparse.RawDescriptionHelpFormatter)
    log.add_argument("--mode", required=True, choices=["branch", "targeted", "audit", "simplify"])
    log.add_argument("--input", required=True)
    log.add_argument("--base")
    handoff = sub.add_parser("handoff")
    handoff.add_argument("--input", required=True)
    return parser.parse_args()


def main():
    opts = parse_arguments()
    handlers = {"branch-prep": branch_prep, "audit-prep": audit_prep, "simplify-prep": simplify_prep,
                "log": log_verb, "handoff": handoff_verb}
    try:
        return handlers[opts.verb](opts)
    except RefactorFlowError as err:
        print(f"refactor-flow: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
