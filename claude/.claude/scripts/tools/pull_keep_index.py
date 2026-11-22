"""Usage: pull_keep_index.py <repo>
       pull_keep_index.py --put-back <saved> <repo>
       pull_keep_index.py --help

`--help` (or `-h`) prints this text and exits 0.
Before anything is set aside the saved changes get a named ref, `refs/pull-keep-index/<UTC stamp>-<first 8 of the
commit>`. A successful put-back deletes only its own ref, then prints one stderr line "older saved changes kept under:
<refs>" for the other refs under that prefix, which it never deletes. A failed run keeps the ref.
`--put-back` puts the changes saved in <saved> back into the repo, the way the pull does: staged files staged, built
pages rebuilt. <saved> is the commit hash or its ref; the argument is resolved to the commit once, then a ref under
the prefix is chosen (the argument itself, else the first ref by name that points at the commit, else a new one), before
the clean-tree check, so a failed put-back always leaves a named ref. Every message that leaves the local changes
saved but not applied names the commit and its ref.
When the staged changes clash with the pull on built pages (paths with `merge=built-page`), the rest of the staged
changes go onto the pulled tree (a file both changed in other hunks does) and the repo configures the built-page merge
driver (`merge.built-page.driver`), the saved changes go on with no index so the driver rebuilds those pages, and the
rebuilt pages are staged. With no driver configured git text-merges those pages,
so the run exits 1 naming `--put-back`.
A <saved> that is not a saved-changes commit (no second parent), or a repo with tracked changes
(`git status --porcelain --untracked-files=no` prints anything), exits 1 with the usage.

Run `git pull --rebase=merges` in the repo with its local changes set aside and put back after, staged files still
staged. `--autostash` puts them back unstaged. The changes are saved as a stash commit kept under a
`refs/pull-keep-index/` ref, never on the shared stash stack. The re-apply names that commit in BUILT_PAGE_STASH,
so the agent-evals built-page merge driver rebuilds a generated page in place of a text merge. When the re-apply
conflicts, every other file gets back its staged or unstaged state and the conflicted paths stay conflicted.
A branch with no upstream setting pulls `origin <branch>` when origin has it, then sets that as its upstream; when
origin lacks it, nothing is pulled or set aside and the exit is 0, so a chained first push runs.
A set upstream that the remote says is gone exits 1 naming the recovery (unset the upstream, push with
`-u <remote> HEAD`), so the chained push does not recreate it: before anything is set aside when `@{u}` does not
resolve, and after the failed pull when a stale remote-tracking ref still resolves it.
Exit 0 when the pull ran and the changes are back, or when there is nothing to pull; exit 1 otherwise, with the
recovery command when one exists. A failed branch-name lookup before the pull exits 1 naming the failed command. A
failed remote lookup before the pull (origin, or the configured remote) exits 1 with the git error, before anything is
set aside; one after a failed pull ends in the pull-failure exit.
A branch whose fetched upstream tip is already an ancestor of HEAD (pushed, then the integration branch merged in)
pulls nothing, prints one line saying so and exits 0, with the index and every commit hash untouched.
A branch rewritten here (rebase, amend, reset) pulls nothing and exits 0 with a message to push with
--force-with-lease: the upstream tip, fetched first, is not on HEAD but is in the branch's own reflog, so the remote
holds nothing the branch never had. An upstream tip that is not in the reflog (another machine pushed) is pulled as
usual. When the fetch fails (the upstream is deleted on the remote, or the remote is unreachable), the run goes on to
the usual upstream checks and pull, so a deleted upstream still exits 1 naming it.
When the rebase stops on a conflict that a merge of the pulled tip would not have (a replayed merge commit that had
resolved conflicts), the rebase is undone and the pulled tip is merged instead; else the run exits 1 mid-rebase."""
import datetime
import os
import shlex
import subprocess
import sys
import tempfile
from typing import NamedTuple

sys.path[:0] = [os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib")]
import script_utils

# The variable ~/agent-evals/bin/merge_built_page.py reads for the stash commit a `git stash apply` is applying.
BUILT_PAGE_STASH = "BUILT_PAGE_STASH"
# The gitattributes value (`merge=built-page`) that marks a generated page.
BUILT_PAGE_DRIVER = "built-page"
PUT_BACK_VERB = "--put-back"
FALLBACK_REMOTE = "origin"
# Every saved-changes commit is kept under a ref with this prefix, so no run leaves the edits only in a dangling commit.
REF_PREFIX = "refs/pull-keep-index/"


def saved_text(saved, ref):
    """Where the local changes are saved, with no closing punctuation so a caller can end it as it needs."""
    return f"The local changes are saved in {saved} (ref {ref})"


def git_command_text(repo, *arguments):
    """A git command line for the repo, quoted for the user to paste into a shell."""
    return shlex.join(["git", "-C", repo, *arguments])


def page_stage_arguments(pages):
    """The git arguments that stage the rebuilt pages by literal path; the run and the printed command share them."""
    return ("--literal-pathspecs", "add", "--", *pages)


def recovery_text(repo, saved, ref):
    """How to put the saved changes back with the --put-back verb of this script."""
    script = os.path.realpath(__file__)
    command = f"python3 {shlex.quote(script)} {PUT_BACK_VERB} {shlex.quote(ref)} {shlex.quote(repo)}"
    return f"{saved_text(saved, ref)}; on a clean tree, run: {command}"


def refs_under_prefix(repo, *extra_arguments):
    """The names of the refs under REF_PREFIX, sorted by name; `extra_arguments` go to `for-each-ref` before the
    pattern (for example `--points-at <commit>`)."""
    listed = run_in_repo(repo, "for-each-ref", "--format=%(refname)", *extra_arguments, REF_PREFIX)
    if listed.returncode != 0:
        problem = script_utils.process_stderr_text(listed)
        sys.exit(f"pull_keep_index: could not list the refs under {REF_PREFIX}: {problem}")
    return [name for name in os.fsdecode(listed.stdout).splitlines() if name]


def keep_ref(repo, saved):
    """Give the saved commit a named ref and return its name. The empty old value makes git refuse to overwrite an
    existing ref. Exit 1 naming the saved commit when the ref cannot be made, before anything is set aside."""
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ref = f"{REF_PREFIX}{stamp}-{saved[:8]}"
    made = run_in_repo(repo, "update-ref", ref, saved, "")
    if made.returncode != 0:
        problem = script_utils.process_stderr_text(made)
        sys.exit(f"pull_keep_index: could not keep a ref {ref} for the saved changes {saved}: {problem}. "
                 "Nothing was set aside.")
    return ref


def drop_ref(repo, saved, ref):
    """After a successful put-back delete the ref of this run only, then name any older refs left under the prefix."""
    dropped = run_in_repo(repo, "update-ref", "-d", ref, saved)
    if dropped.returncode != 0:
        problem = script_utils.process_stderr_text(dropped)
        sys.stderr.write(f"pull_keep_index: the changes are back but the ref {ref} was not deleted: {problem}\n")
    older = [name for name in refs_under_prefix(repo) if name != ref]
    if older:
        sys.stderr.write(f"pull_keep_index: older saved changes kept under: {' '.join(older)}\n")


def stopped_rebase_dir(repo):
    """The state folder of a rebase stopped in the repo, or None when no rebase is in progress."""
    for name in ("rebase-merge", "rebase-apply"):
        found = script_utils.git_output(repo, "rev-parse", "--git-path", name)
        if not found:
            continue
        state_dir = os.path.join(repo, found)
        if os.path.isdir(state_dir):
            return state_dir
    return None


def stopped_rebase_text(repo, state_dir):
    """What a stopped rebase holds and the two ways out of it."""
    head_name_file = os.path.join(state_dir, "head-name")
    branch = "an unknown branch"
    if os.path.exists(head_name_file):
        with open(head_name_file) as head_name:
            branch = head_name.read().strip()
    conflicts = listed_paths(repo, "--diff-filter=U")
    conflict_text = "conflicted paths: " + " ".join(conflicts) if conflicts else "no conflicted paths"
    continue_command = git_command_text(repo, "rebase", "--continue")
    abort_command = git_command_text(repo, "rebase", "--abort")
    return (f"a rebase is stopped on {branch}, {conflict_text}. Finish it with {continue_command} "
            f"after resolving any conflict, or undo it with {abort_command}.")


def put_back_text(repo, saved, ref):
    """The tail of a stop that leaves the local changes saved: how to put them back; "" for a clean tree."""
    if not saved:
        return ""
    return " Then put the local changes back. " + recovery_text(repo, saved, ref)


def merge_abort_text(repo):
    """What to say about undoing a failed merge: the abort command only when a merge is in progress."""
    in_progress = run_in_repo(repo, "rev-parse", "-q", "--verify", "MERGE_HEAD")
    if in_progress.returncode == 0:
        abort_command = git_command_text(repo, "merge", "--abort")
        return f"Undo it with {abort_command}."
    return "No merge is in progress."


def merge_in_place_of_rebase(repo, state_dir, saved, ref):
    """When the stopped rebase's branch merges cleanly with the pulled tip (FETCH_HEAD), abort the rebase and merge;
    True when the merge commit is made. A replay of a merge commit that resolved conflicts hits them again, where a
    merge of the remote does not. False, with the rebase left stopped, when the merge would conflict too, when git
    has no `merge-tree --write-tree` (before 2.38), or when the branch tip cannot be read."""
    orig_head_file = os.path.join(state_dir, "orig-head")
    if not os.path.exists(orig_head_file):
        return False
    with open(orig_head_file) as orig_head:
        branch_tip = orig_head.read().strip()
    trial = run_in_repo(repo, "merge-tree", "--write-tree", "--quiet", branch_tip, "FETCH_HEAD")
    if trial.returncode != 0:
        return False

    aborted = run_in_repo(repo, "rebase", "--abort")
    if aborted.returncode != 0:
        problem = script_utils.process_stderr_text(aborted)
        sys.exit(f"pull_keep_index: the rebase replay conflicted and git rebase --abort failed: {problem}"
                 + put_back_text(repo, saved, ref))
    merged = run_in_repo(repo, "merge", "--no-edit", "--quiet", "FETCH_HEAD")
    if merged.returncode != 0:
        problem = script_utils.process_stderr_text(merged)
        sys.exit(f"pull_keep_index: the rebase replay conflicted, so the rebase was undone, and the merge of the "
                 f"remote failed: {problem}. {merge_abort_text(repo)}" + put_back_text(repo, saved, ref))
    print("pull_keep_index: the rebase replay conflicted where a merge does not; merged the remote instead.")
    return True


class UpstreamRelation(NamedTuple):
    """How HEAD stands to the freshly fetched upstream tip when there is nothing to pull."""
    kind: str  # ALREADY_HELD or REWRITTEN_LOCALLY
    branch: str
    short_tip: str


ALREADY_HELD = "already held"
REWRITTEN_LOCALLY = "rewritten locally"


def upstream_relation(repo):
    """After a fetch, the UpstreamRelation when the upstream has nothing HEAD lacks: ALREADY_HELD when the upstream
    tip is an ancestor of HEAD (pushed, then built on, for instance by merging the integration branch in), or
    REWRITTEN_LOCALLY when the tip is not on HEAD but the branch's own reflog holds it (rebase, amend, reset). None
    otherwise, including when the fetch or any git lookup fails (the run goes on as before, and reports a deleted
    upstream)."""
    branch = script_utils.current_branch(repo)
    if not branch:
        return None
    merge_ref = script_utils.branch_merge_ref(repo, branch)
    if not merge_ref:
        return None
    # Without the fetch, `@{u}` is the last-fetched tip: another machine's later push would hide behind it.
    fetched = run_in_repo(repo, "fetch", "--quiet", configured_remote(repo, branch), merge_ref)
    if fetched.returncode != 0:
        return None
    tip = script_utils.git_output(repo, "rev-parse", "--verify", "--quiet", "@{u}^{commit}")
    if not tip:
        return None
    short_tip = script_utils.git_output(repo, "rev-parse", "--short", tip) or tip
    on_head = run_in_repo(repo, "merge-base", "--is-ancestor", tip, "HEAD")
    if on_head.returncode == 0:
        return UpstreamRelation(ALREADY_HELD, branch, short_tip)
    held = script_utils.git_output(repo, "rev-list", "--walk-reflogs", f"refs/heads/{branch}")
    if held is None or tip not in held.split():
        return None
    return UpstreamRelation(REWRITTEN_LOCALLY, branch, short_tip)


def relation_text(relation):
    """The one line that says why nothing is pulled."""
    if relation.kind == ALREADY_HELD:
        return (f"pull_keep_index: {relation.branch} already holds the upstream tip {relation.short_tip}; "
                "nothing pulled.")
    return (f"pull_keep_index: {relation.branch} was rewritten locally (the upstream tip {relation.short_tip} was on "
            "it before); nothing pulled. Push with --force-with-lease.")


def set_aside(repo):
    """Save the local changes as a stash commit, keep a named ref for it, and reset to HEAD; (commit id, ref), or
    ("", "") for a clean tree."""
    saved = script_utils.git_output(repo, "stash", "create")
    if saved is None:
        sys.exit(f"pull_keep_index: git stash create failed in {repo}")
    if not saved:
        return "", ""
    ref = keep_ref(repo, saved)

    reset = run_in_repo(repo, "reset", "--hard", "--quiet")
    if reset.returncode != 0:
        problem = script_utils.process_stderr_text(reset)
        sys.exit(f"pull_keep_index: git reset failed: {problem}. " + recovery_text(repo, saved, ref))
    return saved, ref


def run_in_repo(repo, *arguments, env=None, stdin=None):
    return subprocess.run(["git", "-C", repo, *arguments], capture_output=True, env=env, input=stdin)


def listed_paths(repo, *diff_arguments):
    """Paths `git diff --name-only` lists for the arguments, renames split into their two paths."""
    listed = run_in_repo(repo, "diff", "--name-only", "--no-renames", "-z", *diff_arguments)
    return [name for name in os.fsdecode(listed.stdout).split("\0") if name]


def staged_tree(repo, saved, left_out=()):
    """The tree the index would hold had the apply gone on cleanly: HEAD with the saved staged changes on it, built in
    a scratch index. The `left_out` paths keep their HEAD text. None when git cannot build it."""
    staged_changes = run_in_repo(repo, "diff", "--binary", f"{saved}^1", f"{saved}^2")
    if staged_changes.returncode != 0:
        return None
    exclusions = [f"--exclude={script_utils.escaped_glob(name)}" for name in left_out]
    with tempfile.TemporaryDirectory() as scratch:
        env = {**os.environ, "GIT_INDEX_FILE": os.path.join(scratch, "index")}
        apply_arguments = ("apply", "--cached", *exclusions)
        for arguments, stdin in ((("read-tree", "HEAD"), None), (apply_arguments, staged_changes.stdout)):
            if run_in_repo(repo, *arguments, env=env, stdin=stdin).returncode != 0:
                return None
        written = run_in_repo(repo, "write-tree", env=env)
    if written.returncode != 0:
        return None
    return os.fsdecode(written.stdout).strip()


def restore_the_split(repo, saved, ref, conflicts, left_out=()):
    """After a conflicted apply git stages every file that applied; give each one back the index entry it had.
    The `left_out` paths (rebuilt pages the caller stages itself) are not in the staged tree.
    Return the staged tree, or exit 1 naming the recovery command when that fails."""
    tree = staged_tree(repo, saved, left_out)
    if tree is None:
        sys.exit("pull_keep_index: the local changes conflict and the staged files could not be told apart. "
                 + recovery_text(repo, saved, ref))
    base, index = f"{saved}^1", f"{saved}^2"
    touched = set()
    for older, newer in ((base, saved), (index, saved), (base, index)):
        touched.update(listed_paths(repo, older, newer))
    applied = sorted(touched - set(conflicts))
    if not applied:
        return tree
    reset = run_in_repo(repo, "--literal-pathspecs", "reset", "-q", tree, "--", *applied)
    if reset.returncode != 0:
        problem = script_utils.process_stderr_text(reset)
        sys.exit(f"pull_keep_index: could not restore the staged files: {problem}. "
                 + recovery_text(repo, saved, ref))
    return tree


def staged_clash_paths(repo, saved):
    """The paths both the saved staged changes and the pull changed; a superset of the paths whose staged change
    cannot go on the index."""
    staged = set(listed_paths(repo, f"{saved}^1", f"{saved}^2"))
    pulled = set(listed_paths(repo, f"{saved}^1", "HEAD"))
    return sorted(staged & pulled)


def built_page_paths(repo, paths):
    """The paths whose gitattributes set `merge=built-page`."""
    checked = run_in_repo(repo, "check-attr", "-z", "merge", "--", *paths)
    if checked.returncode != 0:
        return []
    fields = os.fsdecode(checked.stdout).split("\0")[:-1]
    triples = zip(fields[0::3], fields[1::3], fields[2::3], strict=True)
    return [name for name, _attribute, value in triples if value == BUILT_PAGE_DRIVER]


def built_page_driver_configured(repo):
    """Whether the repo configures the built-page merge driver. Git text-merges a page whose attribute names an
    unconfigured driver, and that text must not be staged as a rebuilt page."""
    found = run_in_repo(repo, "config", "--get", f"merge.{BUILT_PAGE_DRIVER}.driver")
    return found.returncode == 0


def clashing_built_pages(repo, saved):
    """The built pages that make the apply with the index fail, or [] when the apply needs another route. A page both
    the saved staged changes and the pull changed clashes; so may an ordinary file they both changed, which applies
    anyway when the hunks do not overlap. The staged changes minus those pages must go onto HEAD: when they do not, an
    ordinary file really clashes and the caller stops. [] too when the repo configures no built-page merge driver, since
    git text-merges such a page and that text must not be staged as rebuilt."""
    clashes = staged_clash_paths(repo, saved)
    pages = built_page_paths(repo, clashes) if clashes else []
    if not pages or not built_page_driver_configured(repo):
        return []
    if staged_tree(repo, saved, left_out=pages) is None:
        return []
    return pages


def put_back_without_index(repo, saved, ref, pages, env):
    """The staged changes clash with the pull only on built pages: apply the saved changes with no index so the merge
    driver rebuilds those pages, then give every other file its staged or unstaged state and stage the rebuilt pages."""
    applied = run_in_repo(repo, "stash", "apply", "--quiet", saved, env=env)
    if applied.returncode != 0:
        sys.stderr.write(os.fsdecode(applied.stderr))
        exit_unapplied(repo, saved, ref, left_out=pages)
    restore_the_split(repo, saved, ref, pages, left_out=pages)
    staged = run_in_repo(repo, *page_stage_arguments(pages))
    if staged.returncode != 0:
        problem = script_utils.process_stderr_text(staged)
        # The changes are already applied, so only the staging is left to do.
        stage_command = git_command_text(repo, *page_stage_arguments(pages))
        sys.exit(f"pull_keep_index: could not stage the rebuilt pages: {problem}. To stage them, run: {stage_command}\n"
                 f"{saved_text(saved, ref)}.")


def exit_unapplied(repo, saved, ref, left_out=()):
    """Exit 1 for a failed apply: the conflict recovery when paths are conflicted, else the put-back command.
    The `left_out` paths are rebuilt pages: the user stages them with `git add`, not a reset to the staged tree."""
    conflicts = listed_paths(repo, "--diff-filter=U")
    if not conflicts:
        sys.exit("pull_keep_index: the local changes did not go back on cleanly. "
                 + recovery_text(repo, saved, ref))

    tree = restore_the_split(repo, saved, ref, [*conflicts, *left_out], left_out)
    conflicted_files = [name for name in conflicts if name not in left_out]
    message = (f"pull_keep_index: the local changes conflict with the pull in: {' '.join(conflicts)}. The other files "
               f"are back, staged or unstaged as before. Fix the conflict markers, then run: ")
    stage_lead = ""
    if conflicted_files:
        reset_command = git_command_text(repo, "--literal-pathspecs", "reset", "-q", tree, "--", *conflicted_files)
        message += f"{reset_command}\nThat marks them resolved with their staged text. "
        stage_lead = "Then stage the pages: "
    if left_out:
        add_command = git_command_text(repo, *page_stage_arguments(left_out))
        message += f"{stage_lead}{add_command}\n"
    sys.exit(message + f"{saved_text(saved, ref)}.")


def put_back(repo, saved, ref):
    """Apply the saved changes with their index, naming the saved commit (never the ref) to the built-page merge
    driver of ~/agent-evals so it rebuilds a page it would else merge as text. When the index clash is on built pages
    alone, apply without the index and stage the rebuilt pages. On success delete the ref. Exit 1 naming the recovery
    command when that fails; on a conflict, first put back each applied file's staged or unstaged state."""
    env = {**os.environ, BUILT_PAGE_STASH: saved}
    applied = run_in_repo(repo, "stash", "apply", "--index", "--quiet", saved, env=env)
    if applied.returncode == 0:
        drop_ref(repo, saved, ref)
        return
    sys.stderr.write(os.fsdecode(applied.stderr))
    has_conflicts = bool(listed_paths(repo, "--diff-filter=U"))
    pages = [] if has_conflicts else clashing_built_pages(repo, saved)
    if pages:
        put_back_without_index(repo, saved, ref, pages, env)
        drop_ref(repo, saved, ref)
        return
    exit_unapplied(repo, saved, ref)


def remote_has_ref(repo, remote, ref):
    """`script_utils.remote_ref_state`, but exit 1 with the git error when the lookup fails."""
    has_ref, problem = script_utils.remote_ref_state(repo, remote, ref)
    if has_ref is None:
        sys.exit(f"pull_keep_index: could not look up {ref} on {remote} in {repo}: {problem}")
    return has_ref


def configured_remote(repo, branch):
    """The remote set for the branch, or FALLBACK_REMOTE when none is set."""
    return script_utils.branch_remote(repo, branch) or FALLBACK_REMOTE


def exit_upstream_gone(repo, branch, merge_ref, remote):
    """Exit 1 naming the gone upstream and the recovery commands."""
    unset_command = git_command_text(repo, "branch", "--unset-upstream")
    push_command = git_command_text(repo, "push", "-u", remote, "HEAD")
    sys.exit(f"pull_keep_index: the upstream {merge_ref} of {branch} is gone from {remote}; a chained push stops here "
             f"so it does not recreate it. Nothing was pulled and the local changes are in place. To recover, run: "
             f"{unset_command}, then, if you mean to recreate it, push with: {push_command}")


def pull_target(repo):
    """The remote and branch to name to `git pull`: [] when the upstream resolves or the remote still has the set
    upstream (or the head is detached), so git picks it; ["origin", branch] when no upstream is set but origin has the
    branch; None when no upstream is set and origin lacks the branch, so there is nothing to pull. Exit 1 with the
    gone-upstream recovery of the module docstring when `@{u}` does not resolve and the remote lacks the set upstream,
    naming the failed command when the branch name lookup fails, and with the git error when a remote lookup fails."""
    upstream = run_in_repo(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if upstream.returncode == 0:
        return []
    branch = script_utils.current_branch(repo)
    if branch is None:
        sys.exit(f"pull_keep_index: git branch --show-current failed in {repo}")
    if not branch:
        return []

    # `@{u}` also fails when an upstream is set but not fetched (a single-branch clone) or deleted and pruned. The
    # remote decides: a deleted one stops here, before anything is set aside, or a chained `git push` would recreate it.
    configured = script_utils.branch_merge_ref(repo, branch)
    if configured is not None:
        remote = configured_remote(repo, branch)
        if not remote_has_ref(repo, remote, configured):
            exit_upstream_gone(repo, branch, configured, remote)
        return []

    # The full ref is passed because a bare name also matches `x/<branch>`.
    if remote_has_ref(repo, FALLBACK_REMOTE, f"refs/heads/{branch}"):
        return [FALLBACK_REMOTE, branch]
    return None


def exit_if_upstream_gone(repo):
    """After a failed pull, ask the remote about the configured upstream: a stale remote-tracking ref hides a deleted
    one from `pull_target`. Return when no upstream is set, the remote still has it, or the lookup fails (the caller
    then reports the plain pull failure)."""
    branch = script_utils.current_branch(repo)
    if not branch:
        return
    configured = script_utils.branch_merge_ref(repo, branch)
    if configured is None:
        return
    remote = configured_remote(repo, branch)
    has_ref, _problem = script_utils.remote_ref_state(repo, remote, configured)
    if has_ref is False:
        exit_upstream_gone(repo, branch, configured, remote)


def set_upstream(repo, remote, branch):
    """Track <remote>/<branch> after a targeted pull, so a later bare `git push` and `git pull` work. The config is
    written directly because `--set-upstream-to` needs a remote-tracking ref, which a single-branch clone never has.
    Exit 1 with the git error and the command to run when that fails."""
    settings = (("remote", remote), ("merge", f"refs/heads/{branch}"))
    for key, value in settings:
        written = run_in_repo(repo, "config", f"branch.{branch}.{key}", value)
        if written.returncode == 0:
            continue
        problem = script_utils.process_stderr_text(written)
        retry = git_command_text(repo, "config", f"branch.{branch}.{key}", value)
        sys.exit(f"pull_keep_index: the pull worked but setting the upstream of {branch} failed in {repo}: {problem}. "
                 f"To set it, run: {retry}")


def resolve_saved(repo, argument):
    """The saved-changes commit hash and the ref that names it, for the argument of --put-back (a hash or a ref).
    Exit 1 with the usage when the argument is not a saved-changes commit (no second parent)."""
    resolved = run_in_repo(repo, "rev-parse", "--verify", "-q", f"{argument}^{{commit}}")
    saved = os.fsdecode(resolved.stdout).strip()
    not_saved_text = f"pull_keep_index: {argument} is not a saved-changes commit\n{__doc__}"
    if resolved.returncode != 0:
        sys.exit(not_saved_text)
    index_parent = run_in_repo(repo, "rev-parse", "--verify", "-q", f"{saved}^2")
    if index_parent.returncode != 0:
        sys.exit(not_saved_text)
    if argument.startswith(REF_PREFIX):
        return saved, argument
    pointing = refs_under_prefix(repo, "--points-at", saved)
    if pointing:
        return saved, pointing[0]
    return saved, keep_ref(repo, saved)


def main(arguments):
    if arguments and arguments[0] in ("-h", "--help"):
        print(__doc__)
        return
    if len(arguments) == 3 and arguments[0] == PUT_BACK_VERB:
        repo = arguments[2]
        saved, ref = resolve_saved(repo, arguments[1])
        tracked_changes = run_in_repo(repo, "status", "--porcelain", "--untracked-files=no")
        if tracked_changes.stdout:
            sys.exit(f"pull_keep_index: {repo} has tracked changes; --put-back needs a clean tree. "
                     f"{saved_text(saved, ref)}.\n{__doc__}")
        put_back(repo, saved, ref)
        return
    if arguments in (["-h"], ["--help"]):
        print(__doc__)
        return
    is_put_back_call = bool(arguments) and arguments[0] == PUT_BACK_VERB
    if len(arguments) != 1 or is_put_back_call:
        sys.exit(__doc__)
    repo = arguments[0]

    state_dir = stopped_rebase_dir(repo)
    if state_dir:
        sys.exit("pull_keep_index: nothing was pulled or set aside: " + stopped_rebase_text(repo, state_dir))

    relation = upstream_relation(repo)
    if relation:
        print(relation_text(relation))
        return

    target = pull_target(repo)
    if target is None:
        print(f"pull_keep_index: the branch has no upstream and is not on {FALLBACK_REMOTE} yet; nothing to pull.")
        return

    saved, ref = set_aside(repo)
    pulled = subprocess.run(["git", "-C", repo, "pull", "--rebase=merges", "--no-autostash", *target])
    pull_failed = pulled.returncode != 0
    state_dir = stopped_rebase_dir(repo)
    stopped_mid_rebase = pull_failed and state_dir
    if stopped_mid_rebase:
        merged = merge_in_place_of_rebase(repo, state_dir, saved, ref)
        if not merged:
            sys.exit("pull_keep_index: the pull stopped mid-rebase: " + stopped_rebase_text(repo, state_dir)
                     + put_back_text(repo, saved, ref))
        pull_failed = False

    if saved:
        put_back(repo, saved, ref)
    if pull_failed:
        exit_if_upstream_gone(repo)
        sys.exit(f"pull_keep_index: git pull failed in {repo}; the local changes are back in place.")
    if target:
        set_upstream(repo, *target)


if __name__ == "__main__":
    main(sys.argv[1:])
