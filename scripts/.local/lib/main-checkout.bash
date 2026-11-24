# Sourced by herdr-lane-resume and herdr-worktree: finds the main checkout of a worktree.
# The sourcing script defines fail(), which prints its arguments and exits non-zero.

# Print the absolute folder of git's `rev-parse <flag>` answer (for example --git-dir) in folder $1.
# Resolves the path by hand: --path-format=absolute needs git 2.31.
git_folder() {
    local answer
    answer=$(git -C "$1" rev-parse "$2" 2>/dev/null) || return 1
    (cd -P "$1" && cd -P "$answer" && pwd)
}

# Print the main checkout of worktree $1. The first `worktree` entry is the main checkout; a bare
# repo lists `bare` after it. A repo with a separate git dir or a submodule lists the git dir
# itself, which has no work tree. Stops when the entry is bare, missing or not a work tree.
main_checkout_of() {
    local wt="$1" listing main_checkout next_line top_level
    listing=$(git -C "$wt" worktree list --porcelain) || fail "could not list the worktrees of $wt; nothing changed"
    main_checkout=$(sed -n '1s/^worktree //p' <<<"$listing")
    next_line=$(sed -n 2p <<<"$listing")
    if [ -z "$main_checkout" ] || [ "$next_line" = "bare" ]; then
        fail "the main checkout of $wt is bare, missing or not a work tree; nothing changed"
    fi
    top_level=$(git -C "$main_checkout" rev-parse --show-toplevel 2>/dev/null) || top_level=""
    if [ -z "$top_level" ] || [ "$(cd -P "$top_level" && pwd)" != "$(cd -P "$main_checkout" && pwd)" ]; then
        fail "the main checkout of $wt is bare, missing or not a work tree; nothing changed"
    fi
    printf '%s\n' "$main_checkout"
}
