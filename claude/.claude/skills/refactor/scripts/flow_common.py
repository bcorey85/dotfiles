"""What the refactor flow's modes share: the base-error types (RefactorFlowError itself lives in
`refactor_log_input`), git calls, the base and merge base, the target file
listing, untracked-file reads and the log-input paths. `refactor_flow` and `simplify_flow` import from here, so
neither imports the other."""
import contextlib
import functools
import os
import re
import uuid
from pathlib import Path
from stat import S_ISREG

import script_utils
import source_text
import untracked_listing
from refactor_log_input import RefactorFlowError

CLAUDE = Path(os.environ.get("REFACTOR_CLAUDE_DIR", Path(__file__).resolve().parents[3]))
BRANCH_BASE = os.environ.get("BRANCH_BASE_SCRIPT") or str(CLAUDE / "scripts" / "tools" / "branch-base")

MAX_STATE_INPUTS = 50
MAX_LOG_INPUTS = MAX_STATE_INPUTS
LOG_INPUT_PREFIX = "refactor-flow-"
LOG_INPUT_HEX_DIGITS = 12
LOG_INPUT_NAME = re.compile(re.escape(LOG_INPUT_PREFIX) + rf"[0-9a-f]{{{LOG_INPUT_HEX_DIGITS}}}\.json")
# A file kept beside a log input (the simplify prep's branch-diff record); pruned with its input.
LOG_INPUT_SIDECAR_SUFFIX = ".simplify-stat"

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


def diff_output(span, *args, pathspecs=()):
    """Run `git diff` over a span with source_text.DIFF_COMMAND_ARGS."""
    limit = ["--", *pathspecs] if pathspecs else []
    done = git(*source_text.DIFF_COMMAND_ARGS, *args, span, *limit, check=False)
    if done.returncode == 0:
        return done.stdout
    if "no merge base" in done.stderr:
        base, _, head = span.partition("...")
        raise NoSharedHistoryError(NO_HISTORY_STOP.format(base=base, head=head))
    raise RefactorFlowError(f"`git diff {span}` failed: {done.stderr.strip()}")


def work_tree_merge_base(base):
    """The commit the work-tree span starts from: where HEAD left `base`."""
    done = git("merge-base", base, "HEAD", check=False)
    if done.returncode == 1 and not done.stderr.strip():
        raise NoSharedHistoryError(NO_HISTORY_STOP.format(base=base, head="HEAD"))
    if done.returncode != 0:
        raise RefactorFlowError(f"`git merge-base {base} HEAD` failed: {done.stderr.strip()}")
    return done.stdout.strip()


def untracked_files(root):
    """untracked_listing.untracked_files, with a listing failure raised as RefactorFlowError."""
    try:
        return untracked_listing.untracked_files(root)
    except untracked_listing.UntrackedListError as error:
        raise RefactorFlowError(str(error)) from error


def next_line(text):
    return f"NEXT: {text}"


def prune_log_inputs(folder):
    """Delete all but the newest files that leave room for one more; the model writes the new path next.
    A log input counts with its sidecar as one file; a sidecar whose input was never written counts on its own.
    A file another session deletes mid-prune is skipped, and so is anything that is not a regular file."""
    keep = MAX_LOG_INPUTS - 1
    dated = []
    for path in folder.glob(f"{LOG_INPUT_PREFIX}*"):
        is_sidecar = path.name.endswith(LOG_INPUT_SIDECAR_SUFFIX)
        input_name = path.name.removesuffix(LOG_INPUT_SIDECAR_SUFFIX)
        if not LOG_INPUT_NAME.fullmatch(input_name):
            continue
        if is_sidecar and (path.parent / input_name).exists():
            continue  # pruned together with its input
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
        with contextlib.suppress(OSError):
            stale.with_name(stale.name + LOG_INPUT_SIDECAR_SUFFIX).unlink()


def log_input_folder():
    """REFACTOR_LOG_INPUT_DIR, else the repo's own git dir, which outlives the system temp folder."""
    override = os.environ.get("REFACTOR_LOG_INPUT_DIR")
    if override:
        folder = Path(override)
        folder.mkdir(parents=True, exist_ok=True)
        return folder
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
