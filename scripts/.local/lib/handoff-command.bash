# Sourced by hunk-review-popup and hunk-review-pane. The one list of handoff targets the
# claude-review extension can write into $HUNK_REVIEW_HANDOFF.

is_handoff_target() {
    case "$1" in
        lazygit | nvim) return 0 ;;
        *) return 1 ;;
    esac
}

# Replaces the calling shell with the tool for target $1 (callers run it in a subshell when
# they must survive). Returns 1 with a message, and no exec, for an unknown target.
exec_handoff_tool() {
    if ! is_handoff_target "$1"; then
        echo "$(basename "$0"): unknown handoff target '$1' — enter to close"
        read -r _
        return 1
    fi
    exec env -u HUNK_REVIEW_HANDOFF -u HUNK_REVIEW_PIDFILE "$1"
}
