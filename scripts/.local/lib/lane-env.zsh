# Sourced by zsh/.zshrc. In a herdr pane whose cwd is a registered lane worktree, turns Claude's
# cron off. A restored pane starts a fresh shell and types herdr's own `claude --resume`, so the
# inline CLAUDE_CODE_DISABLE_CRON=1 that herdr-dev types is gone; the shell has to supply it.
# No subprocess: this runs on every herdr shell start.

_lane_env_apply() {
    emulate -L zsh
    [[ $HERDR_ENV == 1 ]] || return 0
    # ${PWD:A} is the symlink-resolved folder, which is what the lane file records.
    # A relative XDG_STATE_HOME is ignored, as lane_entries.py does.
    local state_home=$XDG_STATE_HOME
    [[ $state_home == /* ]] || state_home=$HOME/.local/state
    local lane_file=$state_home/herdr-lanes/${PWD:A:t}.json
    [[ -r $lane_file ]] || return 0
    local lane_json
    lane_json=$(<$lane_file) || return 0
    # The lane file is pretty-printed, so the worktree sits on a line of its own.
    # This must match what lane_entries.py `_write` writes (indent 2, ensure_ascii off).
    # JSON writes a backslash and a double quote escaped, so escape $PWD the same way before the match.
    local json_pwd=${PWD:A}
    json_pwd=${json_pwd//\\/\\\\}
    json_pwd=${json_pwd//\"/\\\"}
    [[ $lane_json == *$'\n  "worktree": "'"$json_pwd"'"'* ]] || return 0
    export CLAUDE_CODE_DISABLE_CRON=1
}
_lane_env_apply
unfunction _lane_env_apply
