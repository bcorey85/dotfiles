#!/usr/bin/env bash
set -euo pipefail
# CB Security Hooks
# Version: 0.1.3
# ==========
# GENERATED — do not edit directly
# PreToolUse hook: write-edit-safety-gate
trap 'printf '"'"'{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"write-edit-safety-gate encountered an unexpected error — denying for safety"}}\n'"'"'; exit 0' ERR
[[ -n "${CLAUDE_SKIP_HOOKS:-}" ]] && exit 0
HOOK_LOGGING=1  # set to 1 via: ./unix/install.sh --add-logging
INPUT=$(cat)

block() {
    local reason
    reason=$(printf '%s' "$1" | sed 's/"/\\"/g')
    printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}\n' "$reason"
    if [[ "$HOOK_LOGGING" == "1" ]]; then
        local _ts _line _val
        _ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || printf "unknown")
        _val="${CMD:-${RESOLVED:-}}"
        if command -v jq &>/dev/null; then
            _line=$(jq -cn \
                --arg ts "$_ts" \
                --arg hook "write-edit-safety-gate" \
                --arg reason "$1" \
                --arg value "$_val" \
                '{ts:$ts,hook:$hook,reason:$reason,value:$value}' 2>/dev/null) || true
        else
            local _sv _sr
            _sv=$(printf '%s' "$_val" | head -c 300 | sed 's/\\/\\\\/g; s/"/\\"/g')
            _sr=$(printf '%s' "$1"   | sed 's/\\/\\\\/g; s/"/\\"/g')
            _line=$(printf '{"ts":"%s","hook":"%s","reason":"%s","value":"%s"}' \
                "$_ts" "write-edit-safety-gate" "$_sr" "$_sv")
        fi
        [[ -n "${_line:-}" ]] && printf '%s\n' "$_line" >> "$HOME/.claude/security-hook-block-log.jsonl" 2>/dev/null || true
    fi
    exit 0
}


# Parse file_path (Read) or path (Grep/Glob) with jq -> python3 fallback chain.
# Validate JSON before extraction so malformed input denies instead of silently
# falling through to CWD (matches PS1 `catch` behavior).
if [ -z "$INPUT" ]; then
    block "Could not parse hook input — denying for safety"
fi
if command -v jq &>/dev/null; then
    if ! printf '%s' "$INPUT" | jq empty &>/dev/null; then
        block "Could not parse hook input — denying for safety"
    fi
    FILE=$(printf '%s' "$INPUT" | jq -r '(.tool_input.file_path // .tool_input.path) // empty' 2>/dev/null)
elif command -v python3 &>/dev/null; then
    if ! printf '%s' "$INPUT" | python3 -c "import sys,json; json.load(sys.stdin)" &>/dev/null; then
        block "Could not parse hook input — denying for safety"
    fi
    FILE=$(printf '%s' "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); ti=d.get('tool_input',{}); print(ti.get('file_path','') or ti.get('path',''))" 2>/dev/null)
else
    block "jq and python3 are unavailable — cannot safely parse hook input"
fi

# Grep/Glob path is optional — when omitted, the tool defaults to CWD, so check that.
if [ -z "$FILE" ]; then
    FILE="${PWD:-$(pwd)}"
fi

# Resolve to absolute path to catch traversal attacks (e.g. ../../.ssh/id_rsa).
# Tries realpath first (fast native binary), then python3; denies if neither is available.
if command -v realpath &>/dev/null; then
    RESOLVED=$(realpath "$FILE" 2>/dev/null) || RESOLVED="$FILE"
elif command -v python3 &>/dev/null; then
    RESOLVED=$(python3 -c "import os,sys; print(os.path.realpath(sys.argv[1]))" "$FILE" 2>/dev/null) || RESOLVED="$FILE"
else
    block "Cannot resolve absolute path (realpath and python3 unavailable) — denying for safety"
fi

# Case-insensitive matching for macOS (APFS is case-insensitive by default)
shopt -s nocasematch

H="$HOME"

# Shell profile and config files
case "$RESOLVED" in
    "$H"/.zshrc|"$H"/.bashrc|"$H"/.bash_profile|"$H"/.profile|"$H"/.zprofile|"$H"/.zshenv|"$H"/.bash_login|"$H"/.tcshrc|"$H"/.cshrc)
        block "[shell_profiles] [threat:6] Writing to shell profile files is not allowed — persists across sessions" ;;
esac
case "$FILE" in
    "$H"/.zshrc|"$H"/.bashrc|"$H"/.bash_profile|"$H"/.profile|"$H"/.zprofile|"$H"/.zshenv|"$H"/.bash_login|"$H"/.tcshrc|"$H"/.cshrc)
        block "[shell_profiles] [threat:6] Writing to shell profile files is not allowed — persists across sessions" ;;
esac
[[ "$RESOLVED" == ""$H"/.config/fish/"* ]] && block "[fish_config] [threat:6] Writing to fish config is not allowed"
[[ "$FILE" == ""$H"/.config/fish/"* ]] && block "[fish_config] [threat:6] Writing to fish config is not allowed"
# SSH and git credentials
[[ "$RESOLVED" == ""$H"/.ssh/"* ]] && block "[ssh_dir] [threat:6] Writing to ~/.ssh/ is not allowed"
[[ "$FILE" == ""$H"/.ssh/"* ]] && block "[ssh_dir] [threat:6] Writing to ~/.ssh/ is not allowed"
case "$RESOLVED" in
    "$H"/.gitconfig|"$H"/.git-credentials)
        block "[git_creds] [threat:6] Writing to global git config/credentials is not allowed" ;;
esac
case "$FILE" in
    "$H"/.gitconfig|"$H"/.git-credentials)
        block "[git_creds] [threat:6] Writing to global git config/credentials is not allowed" ;;
esac
# Cloud credential directories
[[ "$RESOLVED" == ""$H"/.aws/"* ]] && block "[aws_dir] [threat:6] Writing to cloud credential directories is not allowed"
[[ "$FILE" == ""$H"/.aws/"* ]] && block "[aws_dir] [threat:6] Writing to cloud credential directories is not allowed"
[[ "$RESOLVED" == ""$H"/.gcloud/"* ]] && block "[gcloud_dir] [threat:6] Writing to cloud credential directories is not allowed"
[[ "$FILE" == ""$H"/.gcloud/"* ]] && block "[gcloud_dir] [threat:6] Writing to cloud credential directories is not allowed"
[[ "$RESOLVED" == ""$H"/.config/gcloud/"* ]] && block "[config_gcloud_dir] [threat:6] Writing to cloud credential directories is not allowed"
[[ "$FILE" == ""$H"/.config/gcloud/"* ]] && block "[config_gcloud_dir] [threat:6] Writing to cloud credential directories is not allowed"
[[ "$RESOLVED" == ""$H"/.azure/"* ]] && block "[azure_dir] [threat:6] Writing to cloud credential directories is not allowed"
[[ "$FILE" == ""$H"/.azure/"* ]] && block "[azure_dir] [threat:6] Writing to cloud credential directories is not allowed"
[[ "$RESOLVED" == ""$H"/.kube/"* ]] && block "[kube_dir] [threat:6] Writing to cloud credential directories is not allowed"
[[ "$FILE" == ""$H"/.kube/"* ]] && block "[kube_dir] [threat:6] Writing to cloud credential directories is not allowed"
[[ "$RESOLVED" == ""$H"/.docker/"* ]] && block "[docker_dir] [threat:6] Writing to cloud credential directories is not allowed"
[[ "$FILE" == ""$H"/.docker/"* ]] && block "[docker_dir] [threat:6] Writing to cloud credential directories is not allowed"
# GPG and package manager credentials
[[ "$RESOLVED" == ""$H"/.gnupg/"* ]] && block "[gnupg_dir] [threat:5] Writing to ~/.gnupg/ is not allowed"
[[ "$FILE" == ""$H"/.gnupg/"* ]] && block "[gnupg_dir] [threat:5] Writing to ~/.gnupg/ is not allowed"
case "$RESOLVED" in
    "$H"/.npmrc|"$H"/.pypirc|"$H"/.gem/credentials)
        block "[pkg_creds] [threat:5] Writing to package manager credentials is not allowed" ;;
esac
case "$FILE" in
    "$H"/.npmrc|"$H"/.pypirc|"$H"/.gem/credentials)
        block "[pkg_creds] [threat:5] Writing to package manager credentials is not allowed" ;;
esac
# GitHub CLI auth and vault
[[ "$RESOLVED" == ""$H"/.config/gh/"* ]] && block "[gh_config] [threat:5] Writing to GitHub CLI auth config is not allowed"
[[ "$FILE" == ""$H"/.config/gh/"* ]] && block "[gh_config] [threat:5] Writing to GitHub CLI auth config is not allowed"
case "$RESOLVED" in
    "$H"/.vault-token)
        block "[vault_token] [threat:5] Writing to vault token is not allowed" ;;
esac
case "$FILE" in
    "$H"/.vault-token)
        block "[vault_token] [threat:5] Writing to vault token is not allowed" ;;
esac
# Environment files, MCP config, and Claude settings
case "$RESOLVED" in
    "$H"/.claude/settings.json)
        block "[claude_global_settings] [threat:7] Writing to global Claude settings is not allowed" ;;
esac
case "$FILE" in
    "$H"/.claude/settings.json)
        block "[claude_global_settings] [threat:7] Writing to global Claude settings is not allowed" ;;
esac
[[ "$RESOLVED" == ""$H"/.claude/scripts/"* ]] && block "[claude_hooks] [threat:8] Writing to Claude hook scripts is not allowed — prevents disabling security hooks"
[[ "$FILE" == ""$H"/.claude/scripts/"* ]] && block "[claude_hooks] [threat:8] Writing to Claude hook scripts is not allowed — prevents disabling security hooks"
[[ "$RESOLVED" == ""$H"/.claude/hooks/"* ]] && block "[claude_hooks_dir] [threat:8] Writing to Claude hook scripts is not allowed — prevents disabling security hooks"
[[ "$FILE" == ""$H"/.claude/hooks/"* ]] && block "[claude_hooks_dir] [threat:8] Writing to Claude hook scripts is not allowed — prevents disabling security hooks"
# System directories
[[ "$RESOLVED" == "/etc/"* ]] && block "[etc_dir] [threat:7] Writing to system directories is not allowed"
[[ "$RESOLVED" == "/usr/"* ]] && block "[usr_dir] [threat:7] Writing to system directories is not allowed"
[[ "$RESOLVED" == "/System/"* ]] && block "[system_dir] [threat:7] Writing to system directories is not allowed"
[[ "$RESOLVED" == "/bin/"* ]] && block "[bin_dir] [threat:7] Writing to system directories is not allowed"
[[ "$RESOLVED" == "/sbin/"* ]] && block "[sbin_dir] [threat:7] Writing to system directories is not allowed"
[[ "$RESOLVED" == "/private/etc/"* ]] && block "[private_etc_dir] [threat:7] Writing to system directories is not allowed"
[[ "$RESOLVED" == "/private/bin/"* ]] && block "[private_bin] [threat:7] Writing to system binary directories is not allowed"
[[ "$RESOLVED" == "/private/sbin/"* ]] && block "[private_sbin] [threat:7] Writing to system binary directories is not allowed"
# Persistence mechanisms (launchd, cron, systemd, autostart)
[[ "$RESOLVED" == ""$H"/Library/LaunchAgents/"* ]] && block "[launchagents] [threat:7] Writing persistence mechanism files (launchd, cron) is not allowed"
[[ "$FILE" == ""$H"/Library/LaunchAgents/"* ]] && block "[launchagents] [threat:7] Writing persistence mechanism files (launchd, cron) is not allowed"
[[ "$RESOLVED" == "/Library/LaunchDaemons/"* ]] && block "[launchdaemons] [threat:7] Writing persistence mechanism files (launchd, cron) is not allowed"
[[ "$RESOLVED" == "/var/spool/cron/"* ]] && block "[cron_spool] [threat:7] Writing persistence mechanism files (launchd, cron) is not allowed"
[[ "$RESOLVED" == "/private/var/spool/cron/"* ]] && block "[private_var_cron_spool] [threat:7] Writing persistence mechanism files (launchd, cron) is not allowed"
[[ "$RESOLVED" == ""$H"/.config/autostart/"* ]] && block "[xdg_autostart] [threat:7] Writing to XDG autostart is not allowed"
[[ "$FILE" == ""$H"/.config/autostart/"* ]] && block "[xdg_autostart] [threat:7] Writing to XDG autostart is not allowed"
[[ "$RESOLVED" == ""$H"/.local/share/systemd/user/"* ]] && block "[systemd_user] [threat:7] Writing to user systemd units is not allowed"
[[ "$FILE" == ""$H"/.local/share/systemd/user/"* ]] && block "[systemd_user] [threat:7] Writing to user systemd units is not allowed"
# Fast path: if nothing in the input can match any rule, allow immediately
if ! grep -qiE '((^|/)\.env(rc|(\.[a-zA-Z0-9]+)*)?$)|((^|/)\.mcp\.json$)|(\.claude/settings(\.local)?\.json$)|((^|/)\.git/hooks/)|(\.github/workflows/|\.gitlab-ci\.yml$|Jenkinsfile$|azure-pipelines\.yml$|\.travis\.yml$|bitbucket-pipelines\.yml$|\.buildkite/|\.circleci/)' <<< "$RESOLVED"; then
    exit 0
fi
if grep -qiE '(^|/)\.env(rc|(\.[a-zA-Z0-9]+)*)?$' <<< "$RESOLVED"; then
    if ! grep -qiE '\.(example|sample|template|dist|defaults|schema|test)$' <<< "$RESOLVED"; then
        block "[env_files] [threat:5] Writing to .env files requires manual review — may contain secrets"
    fi
fi
if grep -qiE '(^|/)\.mcp\.json$' <<< "$RESOLVED"; then
    block "[mcp_json] [threat:7] Writing to .mcp.json requires manual review — potential MCP server injection"
fi
if grep -qiE '\.claude/settings(\.local)?\.json$' <<< "$RESOLVED"; then
    block "[claude_project_settings] [threat:7] Writing to project-level Claude settings requires manual review"
fi
# Git hook scripts — persistence mechanism within repositories
if grep -qiE '(^|/)\.git/hooks/' <<< "$RESOLVED"; then
    block "[git_hooks_dir] [threat:6] Writing to .git/hooks/ is not allowed — git hooks execute automatically and persist in the repository"
fi
# CI/CD pipeline files
if grep -qiE '\.github/workflows/|\.gitlab-ci\.yml$|Jenkinsfile$|azure-pipelines\.yml$|\.travis\.yml$|bitbucket-pipelines\.yml$|\.buildkite/|\.circleci/' <<< "$RESOLVED"; then
    block "[cicd_files] [threat:6] Writing to CI/CD pipeline files requires manual review"
fi
shopt -u nocasematch
