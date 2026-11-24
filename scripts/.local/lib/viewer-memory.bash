# Sourced by hunk-review-pane: the review viewer's memory cap. lane-status reads it through
# 'hunk-review-pane --viewers', which prints:
#   {"cap_bytes": 1073741824,
#    "viewers": [{"pane": "w5M_p2", "root": "/home/brandon/some-checkout", "pid": 936851}]}
# One row per state dir holding `hunk.pid`; `root` is the `root` file's content or "". Rows are
# raw: liveness and identity are the reader's job. No state root: {"cap_bytes": N, "viewers": []},
# exit 0. A pidfile not all digits: exit 2, `hunk-review-pane: <file>: expected a pid`. Bad cap: exit 2.

viewer_memory_max="${HUNK_REVIEW_MEMORY_MAX:-1G}"
viewer_restart_window_seconds="${HUNK_REVIEW_RESTART_WINDOW_SECONDS:-60}"
viewer_cap_prefix=()

# viewer_window_max_digits and viewer_memory_digit_limit keep the byte count and the seconds
# under 2^63, so bash arithmetic never wraps.
viewer_window_max_digits=18

# Prints the most significant digits a cap with suffix $1 may have.
viewer_memory_digit_limit() {
    case "$1" in
        K) echo 15 ;;
        M) echo 12 ;;
        G) echo 9 ;;
    esac
}

viewer_memory_checked() {
    local status=0
    # Digits are spelled out: [0-9] also matches non-ASCII digits in some UTF-8 locales, such as en_US.UTF-8.
    if ! [[ $viewer_memory_max =~ ^[0123456789]+[KMG]$ ]]; then
        echo "hunk-review-pane: HUNK_REVIEW_MEMORY_MAX=$viewer_memory_max: expected digits then K, M or G" >&2
        status=1
    elif viewer_memory_is_zero; then
        echo "hunk-review-pane: HUNK_REVIEW_MEMORY_MAX=$viewer_memory_max: must be more than zero" >&2
        status=1
    elif viewer_memory_overflows; then
        echo "hunk-review-pane: HUNK_REVIEW_MEMORY_MAX=$viewer_memory_max: too large (at most $(viewer_memory_digit_limit K) digits for K, $(viewer_memory_digit_limit M) for M, $(viewer_memory_digit_limit G) for G)" >&2
        status=1
    fi
    if ! [[ $viewer_restart_window_seconds =~ ^[0123456789]+$ ]]; then
        echo "hunk-review-pane: HUNK_REVIEW_RESTART_WINDOW_SECONDS=$viewer_restart_window_seconds: expected digits" >&2
        status=1
    elif viewer_window_overflows; then
        echo "hunk-review-pane: HUNK_REVIEW_RESTART_WINDOW_SECONDS=$viewer_restart_window_seconds: too large (at most $viewer_window_max_digits digits)" >&2
        status=1
    else
        # Base 10, so a leading zero (08) is not read as octal by later arithmetic.
        viewer_restart_window_seconds=$((10#$viewer_restart_window_seconds))
    fi
    return "$status"
}

# Prints $1 without its leading zeros.
viewer_significant_digits() {
    local value="$1"
    echo "${value#"${value%%[!0]*}"}"
}

# Returns 0 when the cap is all zeros: MemoryMax=0 would kill the viewer at start.
viewer_memory_is_zero() {
    local digits
    digits=$(viewer_significant_digits "${viewer_memory_max%?}")
    [[ -z $digits ]]
}

# Returns 0 when the cap has more digits than viewer_memory_digit_limit allows for its suffix
# (leading zeros left out).
viewer_memory_overflows() {
    local digits limit
    digits=$(viewer_significant_digits "${viewer_memory_max%?}")
    limit=$(viewer_memory_digit_limit "${viewer_memory_max: -1}")
    (( ${#digits} > limit ))
}

# Returns 0 when the restart window has more significant digits than viewer_window_max_digits
# (leading zeros left out).
viewer_window_overflows() {
    local digits
    digits=$(viewer_significant_digits "$viewer_restart_window_seconds")
    (( ${#digits} > viewer_window_max_digits ))
}

viewer_memory_max_bytes() {
    local digits="${viewer_memory_max%?}"
    local suffix="${viewer_memory_max: -1}"
    case "$suffix" in
        K) echo $((10#$digits * 1024)) ;;
        M) echo $((10#$digits * 1024 * 1024)) ;;
        G) echo $((10#$digits * 1024 * 1024 * 1024)) ;;
    esac
}

# Twin of claude/.claude/scripts/lib/memory_cap_scope.py cap_available: change one, change both.
# One deliberate difference: this side also needs systemctl, for viewer_scope_was_oom_killed.
memory_cap_available() {
    [[ "$(uname -s)" == Linux ]] || return 1
    command -v systemd-run >/dev/null 2>&1 || return 1
    command -v systemctl >/dev/null 2>&1 || return 1
    [[ -n ${XDG_RUNTIME_DIR:-} && -e $XDG_RUNTIME_DIR/bus ]]
}

set_viewer_cap_prefix() {
    local unit="$1"
    if ! memory_cap_available; then
        viewer_cap_prefix=()
        return 0
    fi
    viewer_cap_prefix=(systemd-run --user --scope --quiet "--unit=$unit" -p "MemoryMax=$viewer_memory_max" -p MemorySwapMax=0)
}

# Returns 0 when scope $1 was ended by the kernel for passing its cap. The failed scope is reset
# on every call so the unit name can be reused.
viewer_scope_was_oom_killed() {
    local unit="$1"
    local result
    result=$(systemctl --user show "$unit.scope" -p Result --value 2>/dev/null) || result=""
    systemctl --user reset-failed "$unit.scope" 2>/dev/null
    [[ "$result" == oom-kill ]]
}
