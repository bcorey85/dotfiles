# Sourced by herdr-lane-resume, herdr-worktree and .githooks/post-merge: finds the main checkout of a worktree.
# Only main_checkout_of calls fail(); its caller defines fail(), which prints its arguments and exits non-zero.

# Print the absolute folder of git's `rev-parse <flag>` answer (for example --git-dir) in folder $1.
# Resolves the path by hand: --path-format=absolute needs git 2.31.
git_folder() {
    local answer
    answer=$(git -C "$1" rev-parse "$2" 2>/dev/null) || return 1
    (cd -P "$1" && cd -P "$answer" && pwd)
}

# Returns 0 when folder $1 is inside a linked worktree, not the main checkout.
is_linked_worktree() {
    local git_dir common_dir
    git_dir=$(git_folder "$1" --git-dir) || return 1
    common_dir=$(git_folder "$1" --git-common-dir) || return 1
    [ "$git_dir" != "$common_dir" ]
}

is_worktree_top() {
    local top_level
    top_level=$(git -C "$1" rev-parse --show-toplevel 2>/dev/null) || return 1
    [ -n "$top_level" ] || return 1
    [ "$(cd -P "$top_level" && pwd)" = "$(cd -P "$1" && pwd)" ]
}

# Print the main checkout of worktree $1. The first `worktree` entry is the main checkout; a bare
# repo lists `bare` after it. A repo with a separate git dir or a submodule lists the git dir
# itself, which has no work tree. Stops when the entry is bare, missing or not a work tree.
main_checkout_of() {
    local wt="$1" listing main_checkout next_line
    listing=$(git -C "$wt" worktree list --porcelain) || fail "could not list the worktrees of $wt; nothing changed"
    main_checkout=$(sed -n '1s/^worktree //p' <<<"$listing")
    next_line=$(sed -n 2p <<<"$listing")
    if [ -z "$main_checkout" ] || [ "$next_line" = "bare" ] || ! is_worktree_top "$main_checkout"; then
        fail "the main checkout of $wt is bare, missing or not a work tree; nothing changed"
    fi
    printf '%s\n' "$main_checkout"
}
