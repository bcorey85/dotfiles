# Sourced by herdr-worktree. One claim file per repo and branch under $XDG_STATE_HOME/branch-claims.
# A claim blocks another session while its branch exists and for this many minutes after its last claim.
BRANCH_CLAIM_GRACE_MINUTES=2

# write_claim_json <session name> <branch> <main checkout>
write_claim_json() {
    jq -n --arg owner "$1" --arg branch "$2" --arg repo "$3" '{owner: $owner, branch: $branch, repo: $repo}'
}

# claim_branch <main checkout> <branch> <session name>
# Returns 0 when the session holds the claim (new, its own or taken over from a stale one).
# Returns 1 and prints the owner's name on stdout when another live claim holds the branch.
claim_branch() {
    local main_checkout="$1" branch="$2" session_name="$3"
    local claim_dir key claim_file owner
    claim_dir="${XDG_STATE_HOME:-$HOME/.local/state}/branch-claims"
    mkdir -p "$claim_dir"
    key=$(printf '%s\n%s' "$main_checkout" "$branch" | cksum | cut -d' ' -f1)
    claim_file="$claim_dir/$key.json"

    # noclobber makes the write fail when another session wrote the file first.
    if (set -o noclobber; write_claim_json "$session_name" "$branch" "$main_checkout" >"$claim_file") 2>/dev/null; then
        return 0
    fi

    owner=$(jq -r '.owner // empty' "$claim_file" 2>/dev/null) || owner=""
    if [ "$owner" = "$session_name" ]; then
        touch "$claim_file"
        return 0
    fi

    local branch_exists=""
    git -C "$main_checkout" show-ref --verify --quiet "refs/heads/$branch" && branch_exists=1
    local recent=""
    [ -z "$(find "$claim_file" -mmin "-$BRANCH_CLAIM_GRACE_MINUTES" 2>/dev/null)" ] || recent=1
    if [ -n "$branch_exists" ] || [ -n "$recent" ]; then
        echo "${owner:-unknown}"
        return 1
    fi

    write_claim_json "$session_name" "$branch" "$main_checkout" >"$claim_file"
    return 0
}
