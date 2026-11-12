"""Usage: pull_keep_index.py <repo>

Run `git pull --rebase=merges` in the repo with its local changes set aside and put back after, staged files still
staged. `--autostash` puts them back unstaged. The changes are saved as a dangling stash commit, never on the shared
stash stack. The re-apply names that commit in BUILT_PAGE_STASH, so the agent-evals built-page merge driver rebuilds a
generated page in place of a text merge. When the re-apply conflicts, every other file gets back its staged or
unstaged state and the conflicted paths stay conflicted. A branch with no upstream setting pulls `origin <branch>`
when origin has it, then sets that as its upstream; when origin lacks it, nothing is pulled or set aside and the exit
is 0, so a chained first push runs. A set upstream that the remote says is gone exits 1 naming the recovery (unset
the upstream, push with `-u <remote> HEAD`), so the chained push does not recreate it: before anything is set aside
when `@{u}` does not resolve, and after the failed pull when a stale remote-tracking ref still resolves it.
Exit 0 when the pull ran and the changes are back, or when there is nothing to pull; exit 1 otherwise, with the
recovery command when one exists. A failed branch-name lookup before the pull exits 1 naming the failed command. A
failed remote lookup before the pull (origin, or the configured remote) exits 1 with the git error, before anything is
set aside; one after a failed pull ends in the pull-failure exit.
A branch rewritten here (rebase, amend, reset) pulls nothing and exits 0 with a message to push with
--force-with-lease: the upstream tip, fetched first, is not on HEAD but is in the branch's own reflog, so the remote
holds nothing the branch never had. An upstream tip that is not in the reflog (another machine pushed) is pulled as
usual. When the fetch fails (the upstream is deleted on the remote, or the remote is unreachable), the run goes on to
the usual upstream checks and pull, so a deleted upstream still exits 1 naming it.
When the rebase stops on a conflict that a merge of the pulled tip would not have (a replayed merge commit that had
resolved conflicts), the rebase is undone and the pulled tip is merged instead; else the run exits 1 mid-rebase."""
import os
import subprocess
import sys
import tempfile

sys.path[:0] = [os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib")]
import script_utils

# The variable ~/agent-evals/bin/merge_built_page.py reads for the stash commit a `git stash apply` is applying.
BUILT_PAGE_STASH = "BUILT_PAGE_STASH"
FALLBACK_REMOTE = "origin"


def recovery_text(repo, saved):
    return f"The local changes are saved in {saved}; on a clean tree, run: git -C {repo} stash apply --index {saved}"


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
    return (f"a rebase is stopped on {branch}, {conflict_text}. Finish it with git -C {repo} rebase --continue "
            f"after resolving any conflict, or undo it with git -C {repo} rebase --abort.")


def put_back_text(repo, saved):
    """The tail of a stop that leaves the local changes saved: how to put them back; "" for a clean tree."""
    if not saved:
        return ""
    return " Then put the local changes back. " + recovery_text(repo, saved)


def merge_abort_text(repo):
    """What to say about undoing a failed merge: the abort command only when a merge is in progress."""
    in_progress = run_in_repo(repo, "rev-parse", "-q", "--verify", "MERGE_HEAD")
    if in_progress.returncode == 0:
        return f"Undo it with git -C {repo} merge --abort."
    return "No merge is in progress."


def merge_in_place_of_rebase(repo, state_dir, saved):
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


def rewritten_locally(repo):
    """(branch, short id of the upstream tip) when the freshly fetched upstream tip is not on HEAD but the branch's own
    reflog holds it, so the branch was rewritten here (rebase, amend, reset) and the remote has nothing it never had;
    None otherwise, including when the fetch or any git lookup fails (the run goes on as before, and reports a
    deleted upstream)."""
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
    on_head = run_in_repo(repo, "merge-base", "--is-ancestor", tip, "HEAD")
    if on_head.returncode == 0:
        return None
    held = script_utils.git_output(repo, "rev-list", "--walk-reflogs", f"refs/heads/{branch}")
    if held is None or tip not in held.split():
        return None
    short_tip = script_utils.git_output(repo, "rev-parse", "--short", tip)
    return branch, short_tip or tip


def set_aside(repo):
    """Save the local changes as a stash commit and reset to HEAD; the commit id, or "" for a clean tree."""
    saved = script_utils.git_output(repo, "stash", "create")
    if saved is None:
        sys.exit(f"pull_keep_index: git stash create failed in {repo}")
    if not saved:
        return saved

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


def staged_tree(repo, saved):
    """The tree the index would hold had the apply gone on cleanly: HEAD with the saved staged changes on it, built in
    a scratch index. None when git cannot build it."""
    staged_changes = run_in_repo(repo, "diff", "--binary", f"{saved}^1", f"{saved}^2")
    if staged_changes.returncode != 0:
        return None
    with tempfile.TemporaryDirectory() as scratch:
        env = {**os.environ, "GIT_INDEX_FILE": os.path.join(scratch, "index")}
        for arguments, stdin in ((("read-tree", "HEAD"), None), (("apply", "--cached"), staged_changes.stdout)):
            if run_in_repo(repo, *arguments, env=env, stdin=stdin).returncode != 0:
                return None
        written = run_in_repo(repo, "write-tree", env=env)
    if written.returncode != 0:
        return None
    return os.fsdecode(written.stdout).strip()


def restore_the_split(repo, saved, conflicts):
    """After a conflicted apply git stages every file that applied; give each one back the index entry it had.
    Return the staged tree, or exit 1 naming the recovery command when that fails."""
    tree = staged_tree(repo, saved)
    if tree is None:
        sys.exit("pull_keep_index: the local changes conflict and the staged files could not be told apart. "
                 + recovery_text(repo, saved))
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
        sys.exit(f"pull_keep_index: could not restore the staged files: {problem}. " + recovery_text(repo, saved))
    return tree


def put_back(repo, saved):
    """Apply the saved changes with their index, naming the saved commit to the built-page merge driver of
    ~/agent-evals so it rebuilds a page it would else merge as text. Exit 1 naming the recovery command when that
    fails; on a conflict, first put back each applied file's staged or unstaged state."""
    env = {**os.environ, BUILT_PAGE_STASH: saved}
    applied = run_in_repo(repo, "stash", "apply", "--index", "--quiet", saved, env=env)
    if applied.returncode == 0:
        return
    sys.stderr.write(os.fsdecode(applied.stderr))
    conflicts = listed_paths(repo, "--diff-filter=U")
    if not conflicts:
        sys.exit("pull_keep_index: the local changes did not go back on cleanly. " + recovery_text(repo, saved))

    tree = restore_the_split(repo, saved, conflicts)
    names = " ".join(conflicts)
    sys.exit(f"pull_keep_index: the local changes conflict with the pull in: {names}. The other files are back, "
             f"staged or unstaged as before. Fix the conflict markers, then run: git -C {repo} reset -q {tree} -- "
             f"{names}\nThat marks them resolved with their staged text. The local changes are saved in {saved}.")


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
    sys.exit(f"pull_keep_index: the upstream {merge_ref} of {branch} is gone from {remote}; a chained push stops here "
             f"so it does not recreate it. Nothing was pulled and the local changes are in place. To recover, run: "
             f"git -C {repo} branch --unset-upstream, then, if you mean to recreate it, push with: "
             f"git -C {repo} push -u {remote} HEAD")


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
        sys.exit(f"pull_keep_index: the pull worked but setting the upstream of {branch} failed in {repo}: {problem}. "
                 f"To set it, run: git -C {repo} config branch.{branch}.{key} {value}")


def main(arguments):
    if len(arguments) != 1:
        sys.exit(__doc__)
    repo = arguments[0]

    state_dir = stopped_rebase_dir(repo)
    if state_dir:
        sys.exit("pull_keep_index: nothing was pulled or set aside: " + stopped_rebase_text(repo, state_dir))

    rewrite = rewritten_locally(repo)
    if rewrite:
        branch, short_tip = rewrite
        print(f"pull_keep_index: {branch} was rewritten locally (the upstream tip {short_tip} was on it before); "
              "nothing pulled. Push with --force-with-lease.")
        return

    target = pull_target(repo)
    if target is None:
        print(f"pull_keep_index: the branch has no upstream and is not on {FALLBACK_REMOTE} yet; nothing to pull.")
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

    if saved:
        put_back(repo, saved)
    if pull_failed:
        exit_if_upstream_gone(repo)
        sys.exit(f"pull_keep_index: git pull failed in {repo}; the local changes are back in place.")
    if target:
        set_upstream(repo, *target)


if __name__ == "__main__":
    main(sys.argv[1:])
