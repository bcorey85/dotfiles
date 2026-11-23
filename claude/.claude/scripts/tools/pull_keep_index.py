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
When the staged changes clash with the pull on built pages (paths with `merge=built-page`) and the repo configures
the built-page merge driver (`merge.built-page.driver`), the saved changes go back by hand in six steps: the staged
part with the pages left out goes on the index, the index is written as a tree, the unstaged part with the pages left
out goes on the tree, the tree is read back into the index, each page is rebuilt through the driver command, and the
rebuilt pages are staged. A part that conflicts rolls the tree back to the pulled HEAD with no local changes and
exits 1 naming the conflicted files, the ref and the command that puts the changes back with conflict markers. With
no driver configured git text-merges those pages, so the run exits 1 naming `--put-back`.
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
resolved conflicts), the rebase is undone and the pulled tip is merged instead; else the run exits 1 mid-rebase.
Another live session in the repo (its registry `cwd` is the repo or inside it; a missing CLAUDE_CODE_SESSION_ID counts
as another session) plus tracked changes is the shared route: nothing is set aside, because the other session's edits
would leave the tree during the pull. The upstream tip is fetched and, when HEAD already holds it, nothing is pulled;
when it has commits HEAD lacks and HEAD has none of its own, the branch is fast-forwarded in place; when HEAD has
commits of its own the run exits 1 naming the dirty files, and when the fast-forward would overwrite a dirty file it
exits 1 naming that file. Every run, `--put-back` included, holds `<git common dir>/pull-keep-index.lock`; it waits
PULL_KEEP_INDEX_LOCK_SECONDS (a positive integer, default 300) and then exits 1."""
import datetime
import os
import pathlib
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from typing import NamedTuple

sys.path[:0] = [os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib")]
import file_lock
import script_utils
import session_registry

LOCK_SECONDS_VARIABLE = "PULL_KEEP_INDEX_LOCK_SECONDS"
DEFAULT_LOCK_SECONDS = 300
LOCK_FILE_NAME = "pull-keep-index.lock"
# Holds the fetched upstream tip for one run; the prefix differs from REF_PREFIX so the saved refs never list it.
FETCH_REF_PREFIX = "refs/pull-keep-index-fetch/"
# The variable ~/agent-evals/bin/merge_built_page.py reads for the stash commit a `git stash apply` is applying.
BUILT_PAGE_STASH = "BUILT_PAGE_STASH"
# The gitattributes value (`merge=built-page`) that marks a generated page.
BUILT_PAGE_DRIVER = "built-page"
PUT_BACK_VERB = "--put-back"
FALLBACK_REMOTE = "origin"
# Every saved-changes commit is kept under a ref with this prefix, so no run leaves the edits only in a dangling commit.
REF_PREFIX = "refs/pull-keep-index/"


class Saved(NamedTuple):
    """The local changes set aside: the stash commit that holds them and the ref that names it."""
    commit: str
    ref: str


def saved_text(saved: Saved):
    """Where the local changes are saved, with no closing punctuation so a caller can end it as it needs."""
    return f"The local changes are saved in {saved.commit} (ref {saved.ref})"


def git_command_text(repo, *arguments):
    """A git command line for the repo, quoted for the user to paste into a shell."""
    return shlex.join(["git", "-C", repo, *arguments])


def page_stage_arguments(pages):
    """The git arguments that stage the rebuilt pages by literal path; the run and the printed command share them."""
    return ("--literal-pathspecs", "add", "--", *pages)


def recovery_text(repo, saved: Saved):
    """How to put the saved changes back with the --put-back verb of this script."""
    script = os.path.realpath(__file__)
    command = f"python3 {shlex.quote(script)} {PUT_BACK_VERB} {shlex.quote(saved.ref)} {shlex.quote(repo)}"
    return f"{saved_text(saved)}; on a clean tree, run: {command}"


def refs_under_prefix(repo, *extra_arguments):
    """The names of the refs under REF_PREFIX, sorted by name; `extra_arguments` go to `for-each-ref` before the
    pattern (for example `--points-at <commit>`)."""
    listed = run_in_repo(repo, "for-each-ref", "--format=%(refname)", *extra_arguments, REF_PREFIX)
    if listed.returncode != 0:
        problem = script_utils.process_stderr_text(listed)
        sys.exit(f"pull_keep_index: could not list the refs under {REF_PREFIX}: {problem}")
    return [name for name in os.fsdecode(listed.stdout).splitlines() if name]


def keep_ref(repo, commit):
    """Give the saved commit a named ref and return its name. The empty old value makes git refuse to overwrite an
    existing ref. Exit 1 naming the saved commit when the ref cannot be made, before anything is set aside."""
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ref = f"{REF_PREFIX}{stamp}-{commit[:8]}"
    made = run_in_repo(repo, "update-ref", ref, commit, "")
    if made.returncode != 0:
        problem = script_utils.process_stderr_text(made)
        sys.exit(f"pull_keep_index: could not keep a ref {ref} for the saved changes {commit}: {problem}. "
                 "Nothing was set aside.")
    return ref


def drop_ref(repo, saved: Saved):
    """After a successful put-back delete the ref of this run only, then name any older refs left under the prefix."""
    dropped = run_in_repo(repo, "update-ref", "-d", saved.ref, saved.commit)
    if dropped.returncode != 0:
        problem = script_utils.process_stderr_text(dropped)
        sys.stderr.write(f"pull_keep_index: the changes are back but the ref {saved.ref} was not deleted: {problem}\n")
    older = [name for name in refs_under_prefix(repo) if name != saved.ref]
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


def put_back_text(repo, saved: Saved | None):
    """The tail of a stop that leaves the local changes saved: how to put them back; "" for a clean tree (None)."""
    if saved is None:
        return ""
    return " Then put the local changes back. " + recovery_text(repo, saved)


def merge_abort_text(repo):
    """What to say about undoing a failed merge: the abort command only when a merge is in progress."""
    in_progress = run_in_repo(repo, "rev-parse", "-q", "--verify", "MERGE_HEAD")
    if in_progress.returncode == 0:
        abort_command = git_command_text(repo, "merge", "--abort")
        return f"Undo it with {abort_command}."
    return "No merge is in progress."


def merge_in_place_of_rebase(repo, state_dir, saved: Saved | None):
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
                 + put_back_text(repo, saved))
    merged = run_in_repo(repo, "merge", "--no-edit", "--quiet", "FETCH_HEAD")
    if merged.returncode != 0:
        problem = script_utils.process_stderr_text(merged)
        sys.exit(f"pull_keep_index: the rebase replay conflicted, so the rebase was undone, and the merge of the "
                 f"remote failed: {problem}. {merge_abort_text(repo)}" + put_back_text(repo, saved))
    print("pull_keep_index: the rebase replay conflicted where a merge does not; merged the remote instead.")
    return True


class UpstreamRelation(NamedTuple):
    """How HEAD stands to the freshly fetched upstream tip when there is nothing to pull."""
    kind: str  # ALREADY_HELD or REWRITTEN_LOCALLY
    branch: str
    short_tip: str


ALREADY_HELD = "already held"
REWRITTEN_LOCALLY = "rewritten locally"


class UpstreamCheck(NamedTuple):
    """What the fetch of the upstream found: the relation when there is nothing to pull, and the fetched tip (empty
    when no fetch of the upstream succeeded), so a later step reads the tip and does not fetch again."""
    relation: UpstreamRelation | None
    tip: str


def upstream_relation(repo):
    """Fetch the upstream, then return the UpstreamCheck. Its relation is set when the upstream has nothing HEAD
    lacks: ALREADY_HELD when the upstream tip is an ancestor of HEAD (pushed, then built on, for instance by merging
    the integration branch in), or REWRITTEN_LOCALLY when the tip is not on HEAD but the branch's own reflog holds it
    (rebase, amend, reset). It is None otherwise, including when the fetch or any git lookup fails (the run goes on
    as before, and reports a deleted upstream); the tip is then empty after a failed fetch."""
    branch = script_utils.current_branch(repo)
    if not branch:
        return UpstreamCheck(None, "")
    merge_ref = script_utils.branch_merge_ref(repo, branch)
    if not merge_ref:
        return UpstreamCheck(None, "")
    # Without the fetch, `@{u}` is the last-fetched tip: another machine's later push would hide behind it.
    fetched = fetch_tip(repo, configured_remote(repo, branch), merge_ref)
    tip = fetched.commit
    if not tip:
        return UpstreamCheck(None, "")
    short_tip = script_utils.git_output(repo, "rev-parse", "--short", tip) or tip
    on_head = run_in_repo(repo, "merge-base", "--is-ancestor", tip, "HEAD")
    if on_head.returncode == 0:
        return UpstreamCheck(UpstreamRelation(ALREADY_HELD, branch, short_tip), tip)
    held = script_utils.git_output(repo, "rev-list", "--walk-reflogs", f"refs/heads/{branch}")
    if held is None or tip not in held.split():
        return UpstreamCheck(None, tip)
    return UpstreamCheck(UpstreamRelation(REWRITTEN_LOCALLY, branch, short_tip), tip)


def relation_text(relation):
    """The one line that says why nothing is pulled."""
    if relation.kind == ALREADY_HELD:
        return (f"pull_keep_index: {relation.branch} already holds the upstream tip {relation.short_tip}; "
                "nothing pulled.")
    return (f"pull_keep_index: {relation.branch} was rewritten locally (the upstream tip {relation.short_tip} was on "
            "it before); nothing pulled. Push with --force-with-lease.")


def set_aside(repo):
    """Save the local changes as a stash commit, keep a named ref for it, and reset to HEAD; the Saved, or None for a
    clean tree."""
    commit = script_utils.git_output(repo, "stash", "create")
    if commit is None:
        sys.exit(f"pull_keep_index: git stash create failed in {repo}")
    if not commit:
        return None
    saved = Saved(commit, keep_ref(repo, commit))

    reset = run_in_repo(repo, "reset", "--hard", "--quiet")
    if reset.returncode != 0:
        problem = script_utils.process_stderr_text(reset)
        sys.exit(f"pull_keep_index: git reset failed: {problem}. " + recovery_text(repo, saved))
    return saved


def run_in_repo(repo, *arguments, env=None, stdin=None):
    return subprocess.run(["git", "-C", repo, *arguments], capture_output=True, env=env, input=stdin)


def listed_paths(repo, *diff_arguments):
    """Paths `git diff --name-only` lists for the arguments, renames split into their two paths."""
    listed = run_in_repo(repo, "diff", "--name-only", "--no-renames", "-z", *diff_arguments)
    return [name for name in os.fsdecode(listed.stdout).split("\0") if name]


def staged_tree(repo, commit):
    """The tree the index would hold had the apply gone on cleanly: HEAD with the staged changes of the saved commit
    on it, built in a scratch index. None when git cannot build it."""
    staged_changes = run_in_repo(repo, "diff", "--binary", f"{commit}^1", f"{commit}^2")
    if staged_changes.returncode != 0:
        return None
    with tempfile.TemporaryDirectory() as scratch:
        env = {**os.environ, "GIT_INDEX_FILE": os.path.join(scratch, "index")}
        apply_arguments = ("apply", "--cached")
        for arguments, stdin in ((("read-tree", "HEAD"), None), (apply_arguments, staged_changes.stdout)):
            if run_in_repo(repo, *arguments, env=env, stdin=stdin).returncode != 0:
                return None
        written = run_in_repo(repo, "write-tree", env=env)
    if written.returncode != 0:
        return None
    return os.fsdecode(written.stdout).strip()


def restore_the_split(repo, saved: Saved, conflicts):
    """After a conflicted apply git stages every file that applied; give each one back the index entry it had.
    Return the staged tree, or exit 1 naming the recovery command when that fails."""
    tree = staged_tree(repo, saved.commit)
    if tree is None:
        sys.exit("pull_keep_index: the local changes conflict and the staged files could not be told apart. "
                 + recovery_text(repo, saved))
    base, index = f"{saved.commit}^1", f"{saved.commit}^2"
    touched = set()
    for older, newer in ((base, saved.commit), (index, saved.commit), (base, index)):
        touched.update(listed_paths(repo, older, newer))
    applied = sorted(touched - set(conflicts))
    if not applied:
        return tree
    reset = run_in_repo(repo, "--literal-pathspecs", "reset", "-q", tree, "--", *applied)
    if reset.returncode != 0:
        problem = script_utils.process_stderr_text(reset)
        sys.exit(f"pull_keep_index: could not restore the staged files: {problem}. "
                 + recovery_text(repo, saved))
    return tree


def staged_clash_paths(repo, commit):
    """The paths both the saved staged changes and the pull changed; a superset of the paths whose staged change
    cannot go on the index."""
    staged = set(listed_paths(repo, f"{commit}^1", f"{commit}^2"))
    pulled = set(listed_paths(repo, f"{commit}^1", "HEAD"))
    return sorted(staged & pulled)


def built_page_paths(repo, paths):
    """The paths whose gitattributes set `merge=built-page`."""
    checked = run_in_repo(repo, "check-attr", "-z", "merge", "--", *paths)
    if checked.returncode != 0:
        return []
    fields = os.fsdecode(checked.stdout).split("\0")[:-1]
    triples = zip(fields[0::3], fields[1::3], fields[2::3], strict=True)
    return [name for name, _attribute, value in triples if value == BUILT_PAGE_DRIVER]


def built_page_driver_command(repo):
    """The command of the built-page merge driver, or None when the repo configures none. Git text-merges a page
    whose attribute names an unconfigured driver, and that text must not be staged as a rebuilt page."""
    found = run_in_repo(repo, "config", "--get", f"merge.{BUILT_PAGE_DRIVER}.driver")
    if found.returncode != 0:
        return None
    return os.fsdecode(found.stdout).strip()


class DiffStep(NamedTuple):
    """One part of the saved changes that `put_back_by_hand` applies: the commits a diff compares (`{saved}` stands
    for the saved commit) and the `git apply` options."""
    stage: str  # "staged" or "unstaged", as the rolled-back stop words it
    older: str
    newer: str
    apply_options: tuple


STAGED_DIFF = DiffStep("staged", "{saved}^1", "{saved}^2", ("--index", "--3way"))
UNSTAGED_DIFF = DiffStep("unstaged", "{saved}^2", "{saved}", ("--3way",))


def exit_rolled_back(repo, saved: Saved, stage, pages, problem):
    """Exit 1 after a part of the saved changes would not apply on the pulled HEAD: read the conflicted files (git's
    `problem` text when there are none), then reset the tree to HEAD. The saved commit is under the ref, and untracked
    files are not touched. The stop never says a file is back."""
    conflicts = listed_paths(repo, "--diff-filter=U")
    where = " ".join(conflicts) or problem
    reset = run_in_repo(repo, "reset", "--hard", "--quiet")
    if reset.returncode != 0:
        reset_problem = script_utils.process_stderr_text(reset)
        sys.exit(f"pull_keep_index: the {stage} local changes did not go back (in {where}) and git reset --hard "
                 f"failed: {reset_problem}. " + recovery_text(repo, saved))
    apply_command = (f"{BUILT_PAGE_STASH}={saved.commit} "
                     + git_command_text(repo, "stash", "apply", saved.commit))
    sys.exit(f"pull_keep_index: the pull worked, but the {stage} local changes conflict with it in {where} and were "
             f"not put back. The tree is at the pulled HEAD with no local changes; the rebuilt pages "
             f"{' '.join(pages)} were not made. {saved_text(saved)}. To put them back with the conflicts "
             f"marked, run: `{apply_command}`, fix the markers, then stage what was staged and `git add` the pages.")


def apply_saved_diff(repo, saved: Saved, pages, step):
    """Apply one part of the saved changes, the pages left out. The diff names each page by a literal pathspec, so a
    page called `p[1]` never matches `p1`. An empty diff is skipped: `git apply` exits 128 on empty input and git 2.34
    has no `--allow-empty`. Roll back and exit 1 when the diff or the apply fails."""
    excludes = [":(top)", *[f":(top,exclude,literal){name}" for name in pages]]
    older, newer = step.older.format(saved=saved.commit), step.newer.format(saved=saved.commit)
    diff = run_in_repo(repo, "diff", "--binary", older, newer, "--", *excludes)
    if diff.returncode != 0:
        exit_rolled_back(repo, saved, step.stage, pages, script_utils.process_stderr_text(diff))
    if not diff.stdout:
        return
    applied = run_in_repo(repo, "apply", *step.apply_options, stdin=diff.stdout)
    if applied.returncode != 0:
        exit_rolled_back(repo, saved, step.stage, pages, script_utils.process_stderr_text(applied))


def write_blob(repo, name, destination):
    """Write the blob `name` (for example `<commit>:<path>`) to the file; empty when git has none, as for a page that
    does not exist on that side."""
    found = run_in_repo(repo, "cat-file", "blob", name)
    content = found.stdout if found.returncode == 0 else b""
    pathlib.Path(destination).write_bytes(content)


# git's conflict-marker size when no `conflict-marker-size` attribute is set.
DEFAULT_CONFLICT_MARKER_SIZE = "7"


def run_page_driver(repo, commit, page, template):
    """Rebuild one page through the configured merge driver command `template`: base `<commit>^1`, ours HEAD, theirs
    the saved tree. The driver runs through `sh -c` in `repo`, the top folder, with BUILT_PAGE_STASH set, as git runs
    it. On success copy its result over the page and return None; else return the driver's stderr (or its exit code)."""
    with tempfile.TemporaryDirectory() as scratch:
        base, ours, theirs = (os.path.join(scratch, name) for name in ("base", "ours", "theirs"))
        write_blob(repo, f"{commit}^1:{page}", base)
        write_blob(repo, f"HEAD:{page}", ours)
        write_blob(repo, f"{commit}:{page}", theirs)
        values = {"O": base, "A": ours, "B": theirs, "P": page, "L": DEFAULT_CONFLICT_MARKER_SIZE}
        command = re.sub(r"%([OABPL])", lambda found: shlex.quote(values[found.group(1)]), template)
        env = {**os.environ, BUILT_PAGE_STASH: commit}
        ran = subprocess.run(["sh", "-c", command], cwd=repo, env=env, capture_output=True)
        if ran.returncode != 0:
            return script_utils.process_stderr_text(ran) or f"the driver exited {ran.returncode}"
        destination = pathlib.Path(repo) / page
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ours, destination)
    return None


def put_back_by_hand(repo, saved: Saved, pages, template):
    """The staged changes clash with the pull on built pages, which a stash apply cannot put on the index. Put the
    changes back in six steps, the pages rebuilt through the driver command `template`. `repo` is the top folder.
    (1) apply the staged part, the pages left out, to the index and tree; (2) write the
    index as a tree; (3) apply the unstaged part, the pages left out, to the tree; (4) read the tree back into the
    index, so only the staged part is staged; (5) rebuild each page through the built-page merge driver; (6) stage the
    rebuilt pages. A part that conflicts (steps 1 and 3) rolls the tree back to HEAD and exits 1 with the ref
    (`exit_rolled_back`); a driver that fails (step 5) or a failed staging (step 6) exits 1 with the add command."""
    apply_saved_diff(repo, saved, pages, STAGED_DIFF)
    written = run_in_repo(repo, "write-tree")
    if written.returncode != 0:
        exit_rolled_back(repo, saved, STAGED_DIFF.stage, pages, script_utils.process_stderr_text(written))
    tree = os.fsdecode(written.stdout).strip()
    apply_saved_diff(repo, saved, pages, UNSTAGED_DIFF)
    read = run_in_repo(repo, "read-tree", tree)
    if read.returncode != 0:
        exit_rolled_back(repo, saved, UNSTAGED_DIFF.stage, pages, script_utils.process_stderr_text(read))

    stage_command = git_command_text(repo, *page_stage_arguments(pages))
    for page in pages:
        problem = run_page_driver(repo, saved.commit, page, template)
        if problem is not None:
            sys.exit(f"pull_keep_index: the built-page driver could not rebuild {page}: {problem}. Once the pages "
                     f"are rebuilt, stage them with: {stage_command}\n{saved_text(saved)}.")
    staged = run_in_repo(repo, *page_stage_arguments(pages))
    if staged.returncode != 0:
        problem = script_utils.process_stderr_text(staged)
        # The changes are already applied, so only the staging is left to do.
        sys.exit(f"pull_keep_index: could not stage the rebuilt pages: {problem}. To stage them, run: {stage_command}\n"
                 f"{saved_text(saved)}.")


def exit_unapplied(repo, saved: Saved):
    """Exit 1 for a failed apply: the conflict recovery when paths are conflicted, else the put-back command."""
    conflicts = listed_paths(repo, "--diff-filter=U")
    if not conflicts:
        sys.exit("pull_keep_index: the local changes did not go back on cleanly. "
                 + recovery_text(repo, saved))

    tree = restore_the_split(repo, saved, conflicts)
    reset_command = git_command_text(repo, "--literal-pathspecs", "reset", "-q", tree, "--", *conflicts)
    sys.exit(f"pull_keep_index: the local changes conflict with the pull in: {' '.join(conflicts)}. The other files "
             f"are back, staged or unstaged as before. Fix the conflict markers, then run: {reset_command}\n"
             f"That marks them resolved with their staged text. {saved_text(saved)}.")


def put_back(repo, saved: Saved):
    """Apply the saved changes with their index, naming the saved commit (never the ref) to the built-page merge
    driver of ~/agent-evals so it rebuilds a page it would else merge as text. When that fails with no conflicted
    path, the staged changes clash with the pull on a built page, and the driver is configured, `put_back_by_hand`
    puts the changes back. On success delete the ref. Else exit 1 naming the recovery command; on a conflict, first
    put back each applied file's staged or unstaged state."""
    env = {**os.environ, BUILT_PAGE_STASH: saved.commit}
    applied = run_in_repo(repo, "stash", "apply", "--index", "--quiet", saved.commit, env=env)
    if applied.returncode == 0:
        drop_ref(repo, saved)
        return
    sys.stderr.write(os.fsdecode(applied.stderr))
    has_conflicts = bool(listed_paths(repo, "--diff-filter=U"))
    clashes = [] if has_conflicts else staged_clash_paths(repo, saved.commit)
    pages = built_page_paths(repo, clashes) if clashes else []
    template = built_page_driver_command(repo) if pages else None
    if template is not None:
        put_back_by_hand(repo, saved, pages, template)
        drop_ref(repo, saved)
        return
    exit_unapplied(repo, saved)


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
    """The Saved (commit hash and the ref that names it) for the argument of --put-back (a hash or a ref).
    Exit 1 with the usage when the argument is not a saved-changes commit (no second parent)."""
    resolved = run_in_repo(repo, "rev-parse", "--verify", "-q", f"{argument}^{{commit}}")
    commit = os.fsdecode(resolved.stdout).strip()
    not_saved_text = f"pull_keep_index: {argument} is not a saved-changes commit\n{__doc__}"
    if resolved.returncode != 0:
        sys.exit(not_saved_text)
    index_parent = run_in_repo(repo, "rev-parse", "--verify", "-q", f"{commit}^2")
    if index_parent.returncode != 0:
        sys.exit(not_saved_text)
    if argument.startswith(REF_PREFIX):
        return Saved(commit, argument)
    pointing = refs_under_prefix(repo, "--points-at", commit)
    if pointing:
        return Saved(commit, pointing[0])
    return Saved(commit, keep_ref(repo, commit))


class Incoming(NamedTuple):
    """The fetched upstream tip of the shared route: the local branch name and the tip's commit."""
    branch: str
    commit: str


def fetch_source(repo, branch, target):
    """The remote and the full ref to fetch: the targeted pull's, else the configured upstream of the branch. The
    upstream is read from config, never `@{u}`, which a single-branch clone does not resolve."""
    if target:
        remote, name = target
        return remote, f"refs/heads/{name}"
    return configured_remote(repo, branch), script_utils.branch_merge_ref(repo, branch)


class FetchedTip(NamedTuple):
    """The result of `fetch_tip`: the fetched commit, or an empty commit and the problem to report."""
    commit: str
    problem: str


def fetch_tip(repo, remote, ref):
    """Fetch `ref` of `remote` into a named ref of this run (`FETCH_HEAD` can be rewritten by another session's
    fetch), read the commit, and delete the ref. A failure comes back as the problem text, for the caller to report
    or ignore."""
    fetch_ref = f"{FETCH_REF_PREFIX}{remote}/{ref.rsplit('/', 1)[-1]}"
    if run_in_repo(repo, "check-ref-format", fetch_ref).returncode != 0:
        return FetchedTip("", f"remote {remote} cannot name a fetch ref; nothing pulled or set aside")
    fetched = run_in_repo(repo, "fetch", "--quiet", remote, f"+{ref}:{fetch_ref}")
    if fetched.returncode != 0:
        problem = script_utils.process_stderr_text(fetched)
        return FetchedTip("", f"git fetch {remote} {ref} failed in {repo}: {problem}")
    commit = script_utils.git_output(repo, "rev-parse", "--verify", f"{fetch_ref}^{{commit}}")
    run_in_repo(repo, "update-ref", "-d", fetch_ref)
    if not commit:
        return FetchedTip("", f"could not read the fetched tip of {ref} from {remote} in {repo}")
    return FetchedTip(commit, "")


def fetch_incoming(repo, target, upstream_tip):
    """The Incoming tip of the shared route. `upstream_tip` is the tip `upstream_relation` already fetched from the
    configured upstream (empty when it fetched none); it stands in for a fetch only when the pull names no target of
    its own. Exit 1 on a detached HEAD, a remote that cannot name a ref, or a failed fetch."""
    branch = script_utils.current_branch(repo)
    if not branch:
        sys.exit(f"pull_keep_index: detached HEAD in a shared checkout ({repo}); nothing pulled or set aside")
    if upstream_tip and not target:
        return Incoming(branch, upstream_tip)
    remote, ref = fetch_source(repo, branch, target)
    fetched = fetch_tip(repo, remote, ref)
    if not fetched.commit:
        sys.exit(f"pull_keep_index: {fetched.problem}")
    return Incoming(branch, fetched.commit)


def exit_shared_diverged(repo, other, dirty):
    sys.exit(f"pull_keep_index: {session_registry.holder_label(other)} also works in {repo} and the branch has local "
             f"commits; nothing pulled or set aside. Dirty files: {' '.join(dirty)}. Commit them, or wait for that "
             "session to finish, then rerun.")


def exit_shared_overlap(repo, other, overlap):
    sys.exit(f"pull_keep_index: {session_registry.holder_label(other)} also works in {repo}; the pull would "
             f"overwrite: {' '.join(overlap)}. Nothing was set aside. Commit those files, or wait for that session "
             "to finish, then rerun.")


def fast_forward(repo, incoming, other, dirty):
    """`merge --ff-only` to the fetched tip. Exit 1 when the branch diverged, when the pull would overwrite a dirty
    file, or when the merge fails."""
    if not script_utils.is_ancestor(repo, "HEAD", incoming.commit):
        exit_shared_diverged(repo, other, dirty)
    overlap = sorted(set(listed_paths(repo, "HEAD", incoming.commit)) & set(dirty))
    if overlap:
        exit_shared_overlap(repo, other, overlap)
    merged = run_in_repo(repo, "merge", "--ff-only", "--quiet", incoming.commit)
    if merged.returncode != 0:
        problem = script_utils.process_stderr_text(merged)
        sys.exit(f"pull_keep_index: git merge --ff-only failed in {repo}:\n{problem}\nNothing was set aside.")


def shared_pull(repo, target, other, dirty, upstream_tip):
    """Pull in a checkout another live session edits, with nothing set aside: that session's edits stay in the tree,
    so a fast-forward is the only move that keeps them. Fetch (unless `upstream_tip` is already fetched); already
    held pulls nothing; else fast-forward. Sets the upstream after a targeted pull."""
    incoming = fetch_incoming(repo, target, upstream_tip)
    short = script_utils.git_output(repo, "rev-parse", "--short", incoming.commit) or incoming.commit
    if script_utils.is_ancestor(repo, incoming.commit, "HEAD"):
        print(f"pull_keep_index: {incoming.branch} already holds {short}; nothing pulled.")
    else:
        fast_forward(repo, incoming, other, dirty)
    if target:
        set_upstream(repo, *target)


def lock_seconds():
    """How long to wait for the lock: PULL_KEEP_INDEX_LOCK_SECONDS, read once, a positive integer; exit 1 otherwise."""
    raw = os.environ.get(LOCK_SECONDS_VARIABLE)
    if raw is None:
        return DEFAULT_LOCK_SECONDS
    if not re.fullmatch(r"[0-9]+", raw) or int(raw) <= 0:
        sys.exit(f"pull_keep_index: {LOCK_SECONDS_VARIABLE} must be a positive integer, got {raw!r}")
    return int(raw)


def lock_path(repo):
    """The lock file in the git common dir, shared by every work tree of the repo. Exit 1 outside a repo."""
    common_dir = script_utils.git_output(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if not common_dir:
        sys.exit(f"pull_keep_index: {repo} is not a git repository (git rev-parse --git-common-dir failed)")
    return os.path.join(common_dir, LOCK_FILE_NAME)


def run_put_back(repo, saved_argument):
    saved = resolve_saved(repo, saved_argument)
    tracked_changes = run_in_repo(repo, "status", "--porcelain", "--untracked-files=no")
    if tracked_changes.stdout:
        sys.exit(f"pull_keep_index: {repo} has tracked changes; --put-back needs a clean tree. "
                 f"{saved_text(saved)}.\n{__doc__}")
    put_back(repo, saved)


def parse_request(arguments):
    """(saved argument or None, repo argument) for the two call forms; exit with the usage for any other."""
    if len(arguments) == 3 and arguments[0] == PUT_BACK_VERB:
        return arguments[1], arguments[2]
    if len(arguments) == 1 and arguments[0] != PUT_BACK_VERB:
        return None, arguments[0]
    sys.exit(__doc__)


def main(arguments):
    if arguments and arguments[0] in ("-h", "--help"):
        print(__doc__)
        return
    saved_argument, repo_argument = parse_request(arguments)
    # Run from a subfolder, `git apply` skips paths outside it and still exits 0, so every step runs from the top.
    top = script_utils.repo_root(repo_argument)
    repo = str(top) if top else repo_argument
    seconds = lock_seconds()
    lock = lock_path(repo)
    try:
        with file_lock.hold_exclusive(lock, seconds):
            if saved_argument is None:
                run_pull(repo)
            else:
                run_put_back(repo, saved_argument)
    except file_lock.LockTimeoutError:
        sys.exit(f"pull_keep_index: another run holds {lock}; nothing pulled or set aside")


def run_pull(repo):
    state_dir = stopped_rebase_dir(repo)
    if state_dir:
        sys.exit("pull_keep_index: nothing was pulled or set aside: " + stopped_rebase_text(repo, state_dir))

    checked = upstream_relation(repo)
    if checked.relation:
        print(relation_text(checked.relation))
        return

    target = pull_target(repo)
    if target is None:
        print(f"pull_keep_index: the branch has no upstream and is not on {FALLBACK_REMOTE} yet; nothing to pull.")
        return

    dirty = listed_paths(repo, "HEAD")
    other = session_registry.other_live_session_in(repo, os.environ.get("CLAUDE_CODE_SESSION_ID"))
    if dirty and other is not None:
        shared_pull(repo, target, other, dirty, checked.tip)
        return

    saved = set_aside(repo)
    pulled = subprocess.run(["git", "-C", repo, "pull", "--rebase=merges", "--no-autostash", *target])
    pull_failed = pulled.returncode != 0
    state_dir = stopped_rebase_dir(repo)
    stopped_mid_rebase = pull_failed and state_dir
    if stopped_mid_rebase:
        merged = merge_in_place_of_rebase(repo, state_dir, saved)
        if not merged:
            sys.exit("pull_keep_index: the pull stopped mid-rebase: " + stopped_rebase_text(repo, state_dir)
                     + put_back_text(repo, saved))
        pull_failed = False

    if saved is not None:
        put_back(repo, saved)
    if pull_failed:
        exit_if_upstream_gone(repo)
        sys.exit(f"pull_keep_index: git pull failed in {repo}; the local changes are back in place.")
    if target:
        set_upstream(repo, *target)


if __name__ == "__main__":
    main(sys.argv[1:])
