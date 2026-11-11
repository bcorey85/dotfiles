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
recovery command when one exists. A failed branch-name lookup exits 1 naming the failed command. A failed remote
lookup before the pull (origin, or the configured remote) exits 1 with the git error, before anything is set aside;
one after a failed pull ends in the pull-failure exit."""
import os
import subprocess
import sys
import tempfile

sys.path[:0] = [os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib")]
import script_utils

# The variable ~/agent-evals/bin/merge_built_page.py reads for the stash commit a `git stash apply` is applying.
BUILT_PAGE_STASH = "BUILT_PAGE_STASH"


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


def set_aside(repo):
    """Save the local changes as a stash commit and reset to HEAD; the commit id, or "" for a clean tree."""
    saved = script_utils.git_output(repo, "stash", "create")
    if saved is None:
        sys.exit(f"pull_keep_index: git stash create failed in {repo}")
    if not saved:
        return saved

    reset = run_in_repo(repo, "reset", "--hard", "--quiet")
    if reset.returncode != 0:
        sys.exit(f"pull_keep_index: git reset failed: {stderr_text(reset)}. " + recovery_text(repo, saved))
    return saved


def run_in_repo(repo, *arguments, env=None, stdin=None):
    return subprocess.run(["git", "-C", repo, *arguments], capture_output=True, env=env, input=stdin)


def stderr_text(finished):
    """What a finished git command wrote to stderr, for a failure message."""
    return os.fsdecode(finished.stderr).strip()


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
        problem = stderr_text(reset)
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


def lookup_remote_ref(repo, remote, ref):
    """(has_ref, git_error): has_ref is True when the remote has the full ref, False when it answered that it has none,
    None when the lookup fails (network, no such remote), with the git error as the second value. `ls-remote
    --exit-code` exits 2 for an answered "no such ref"."""
    listed = run_in_repo(repo, "ls-remote", "--exit-code", remote, ref)
    if listed.returncode == 0:
        return True, ""
    if listed.returncode == 2:
        return False, ""
    return None, stderr_text(listed)


def remote_has_ref(repo, remote, ref):
    """`lookup_remote_ref`, but exit 1 with the git error when the lookup fails."""
    has_ref, problem = lookup_remote_ref(repo, remote, ref)
    if has_ref is None:
        sys.exit(f"pull_keep_index: could not look up {ref} on {remote} in {repo}: {problem}")
    return has_ref


def configured_remote(repo, branch):
    return script_utils.git_output(repo, "config", "--get", f"branch.{branch}.remote") or "origin"


def configured_upstream_target(repo, branch, merge_ref):
    """[] when the remote still has the configured upstream, so `git pull` reads the branch config. Exit 1 with the
    gone-upstream recovery of the module docstring, or with the git error when the lookup fails."""
    remote = configured_remote(repo, branch)
    if remote_has_ref(repo, remote, merge_ref):
        return []
    exit_upstream_gone(repo, branch, merge_ref, remote)


def exit_upstream_gone(repo, branch, merge_ref, remote):
    sys.exit(f"pull_keep_index: the upstream {merge_ref} of {branch} is gone from {remote}; a chained push stops here "
             f"so it does not recreate it. Nothing was pulled and the local changes are in place. To recover, run: "
             f"git -C {repo} branch --unset-upstream, then, if you mean to recreate it, push with: "
             f"git -C {repo} push -u {remote} HEAD")


def pull_target(repo):
    """The remote and branch to name to `git pull`: [] when the upstream resolves or the remote still has the set
    upstream (or the head is detached), so git picks it; ["origin", branch] when no upstream is set but origin has the
    branch; None when no upstream is set and origin lacks the branch, so there is nothing to pull. Exit 1 as
    `configured_upstream_target` does when `@{u}` does not resolve, naming the failed command when the branch name
    lookup fails, and with the git error when the origin lookup fails (no upstream set)."""
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
    configured = script_utils.git_output(repo, "config", "--get", f"branch.{branch}.merge")
    if configured is not None:
        return configured_upstream_target(repo, branch, configured)

    # The full ref is passed because a bare name also matches `x/<branch>`.
    if remote_has_ref(repo, "origin", f"refs/heads/{branch}"):
        return ["origin", branch]
    return None


def exit_if_upstream_gone(repo):
    """After a failed pull, ask the remote about the configured upstream: a stale remote-tracking ref hides a deleted
    one from `pull_target`. Return when no upstream is set, the remote still has it, or the lookup fails (the caller
    then reports the plain pull failure)."""
    branch = script_utils.current_branch(repo)
    if not branch:
        return
    configured = script_utils.git_output(repo, "config", "--get", f"branch.{branch}.merge")
    if configured is None:
        return
    remote = configured_remote(repo, branch)
    has_ref, _problem = lookup_remote_ref(repo, remote, configured)
    if has_ref is False:
        exit_upstream_gone(repo, branch, configured, remote)


def set_upstream(repo, branch):
    """Track origin/<branch> after a targeted pull, so a later bare `git push` and `git pull` work. The config is
    written directly because `--set-upstream-to` needs a remote-tracking ref, which a single-branch clone never has.
    Exit 1 with the git error and the command to run when that fails."""
    settings = (("remote", "origin"), ("merge", f"refs/heads/{branch}"))
    for key, value in settings:
        written = run_in_repo(repo, "config", f"branch.{branch}.{key}", value)
        if written.returncode == 0:
            continue
        problem = stderr_text(written)
        sys.exit(f"pull_keep_index: the pull worked but setting the upstream of {branch} failed in {repo}: {problem}. "
                 f"To set it, run: git -C {repo} config branch.{branch}.{key} {value}")


def main(arguments):
    if len(arguments) != 1:
        sys.exit(__doc__)
    repo = arguments[0]

    state_dir = stopped_rebase_dir(repo)
    if state_dir:
        sys.exit("pull_keep_index: nothing was pulled or set aside: " + stopped_rebase_text(repo, state_dir))

    target = pull_target(repo)
    if target is None:
        print("pull_keep_index: the branch has no upstream and is not on origin yet; nothing to pull.")
        return

    saved = set_aside(repo)
    pulled = subprocess.run(["git", "-C", repo, "pull", "--rebase=merges", "--no-autostash", *target])
    state_dir = stopped_rebase_dir(repo)
    if pulled.returncode != 0 and state_dir:
        recovery = " Then put the local changes back. " + recovery_text(repo, saved) if saved else ""
        sys.exit("pull_keep_index: the pull stopped mid-rebase: " + stopped_rebase_text(repo, state_dir) + recovery)

    if saved:
        put_back(repo, saved)
    if pulled.returncode != 0:
        exit_if_upstream_gone(repo)
        sys.exit(f"pull_keep_index: git pull failed in {repo}; the local changes are back in place.")
    if target:
        set_upstream(repo, target[1])


if __name__ == "__main__":
    main(sys.argv[1:])
