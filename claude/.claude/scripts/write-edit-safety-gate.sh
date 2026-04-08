#!/usr/bin/env bash
set -euo pipefail
# CB Security Hooks
# Version: 0.1.2
# ==========
# GENERATED — edit generator/rules/write-edit-safety-gate.yaml and run: python generator/cli.py generate
# PreToolUse hook: write-edit-safety-gate
trap 'printf '"'"'{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"write-edit-safety-gate encountered an unexpected error — denying for safety"}}\n'"'"'; exit 0' ERR
[[ -n "${CLAUDE_SKIP_HOOKS:-}" ]] && exit 0
INPUT=$(cat)

block() {
    local reason
    reason=$(printf '%s' "$1" | sed 's/"/\\"/g')
    printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}\n' "$reason"
    exit 0
}


# Parse file_path with jq -> python3 -> sed fallback chain
if command -v jq &>/dev/null; then
    FILE=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
elif command -v python3 &>/dev/null; then
    FILE=$(printf '%s' "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('file_path',''))" 2>/dev/null)
else
    block "jq and python3 are unavailable — cannot safely parse hook input"
fi

if [ -z "$FILE" ]; then
    block "Could not parse file path from hook input — denying for safety"
fi

# Resolve to absolute path to catch traversal attacks (e.g. ../../.ssh/id_rsa).
# Tries python3, then realpath; falls back to the raw path if neither is available.
if command -v python3 &>/dev/null; then
    RESOLVED=$(python3 -c "import os,sys; print(os.path.realpath(sys.argv[1]))" "$FILE" 2>/dev/null) || RESOLVED="$FILE"
elif command -v realpath &>/dev/null; then
    RESOLVED=$(realpath "$FILE" 2>/dev/null) || RESOLVED="$FILE"
else
    RESOLVED="$FILE"
fi

# Case-insensitive matching for macOS (APFS is case-insensitive by default)
shopt -s nocasematch

H="$HOME"

# Shell profile and config files
case "$RESOLVED" in
    "$H"/.zshrc|"$H"/.bashrc|"$H"/.bash_profile|"$H"/.profile|"$H"/.zprofile|"$H"/.zshenv|"$H"/.bash_login|"$H"/.tcshrc|"$H"/.cshrc)
        block "Writing to shell profile files is not allowed — persists across sessions" ;;
esac
case "$FILE" in
    "$H"/.zshrc|"$H"/.bashrc|"$H"/.bash_profile|"$H"/.profile|"$H"/.zprofile|"$H"/.zshenv|"$H"/.bash_login|"$H"/.tcshrc|"$H"/.cshrc)
        block "Writing to shell profile files is not allowed — persists across sessions" ;;
esac
[[ "$RESOLVED" == ""$H"/.config/fish/"* ]] && block "Writing to fish config is not allowed"
[[ "$FILE" == ""$H"/.config/fish/"* ]] && block "Writing to fish config is not allowed"
# SSH and git credentials
[[ "$RESOLVED" == ""$H"/.ssh/"* ]] && block "Writing to ~/.ssh/ is not allowed"
[[ "$FILE" == ""$H"/.ssh/"* ]] && block "Writing to ~/.ssh/ is not allowed"
case "$RESOLVED" in
    "$H"/.gitconfig|"$H"/.git-credentials)
        block "Writing to global git config/credentials is not allowed" ;;
esac
case "$FILE" in
    "$H"/.gitconfig|"$H"/.git-credentials)
        block "Writing to global git config/credentials is not allowed" ;;
esac
# Cloud credential directories
[[ "$RESOLVED" == ""$H"/.aws/"* ]] && block "Writing to cloud credential directories is not allowed"
[[ "$FILE" == ""$H"/.aws/"* ]] && block "Writing to cloud credential directories is not allowed"
[[ "$RESOLVED" == ""$H"/.gcloud/"* ]] && block "Writing to cloud credential directories is not allowed"
[[ "$FILE" == ""$H"/.gcloud/"* ]] && block "Writing to cloud credential directories is not allowed"
[[ "$RESOLVED" == ""$H"/.config/gcloud/"* ]] && block "Writing to cloud credential directories is not allowed"
[[ "$FILE" == ""$H"/.config/gcloud/"* ]] && block "Writing to cloud credential directories is not allowed"
[[ "$RESOLVED" == ""$H"/.azure/"* ]] && block "Writing to cloud credential directories is not allowed"
[[ "$FILE" == ""$H"/.azure/"* ]] && block "Writing to cloud credential directories is not allowed"
[[ "$RESOLVED" == ""$H"/.kube/"* ]] && block "Writing to cloud credential directories is not allowed"
[[ "$FILE" == ""$H"/.kube/"* ]] && block "Writing to cloud credential directories is not allowed"
[[ "$RESOLVED" == ""$H"/.docker/"* ]] && block "Writing to cloud credential directories is not allowed"
[[ "$FILE" == ""$H"/.docker/"* ]] && block "Writing to cloud credential directories is not allowed"
# GPG and package manager credentials
[[ "$RESOLVED" == ""$H"/.gnupg/"* ]] && block "Writing to ~/.gnupg/ is not allowed"
[[ "$FILE" == ""$H"/.gnupg/"* ]] && block "Writing to ~/.gnupg/ is not allowed"
case "$RESOLVED" in
    "$H"/.npmrc|"$H"/.pypirc|"$H"/.gem/credentials)
        block "Writing to package manager credentials is not allowed" ;;
esac
case "$FILE" in
    "$H"/.npmrc|"$H"/.pypirc|"$H"/.gem/credentials)
        block "Writing to package manager credentials is not allowed" ;;
esac
# GitHub CLI auth and vault
[[ "$RESOLVED" == ""$H"/.config/gh/"* ]] && block "Writing to GitHub CLI auth config is not allowed"
[[ "$FILE" == ""$H"/.config/gh/"* ]] && block "Writing to GitHub CLI auth config is not allowed"
case "$RESOLVED" in
    "$H"/.vault-token)
        block "Writing to vault token is not allowed" ;;
esac
case "$FILE" in
    "$H"/.vault-token)
        block "Writing to vault token is not allowed" ;;
esac
# Environment files, MCP config, and Claude settings
if printf '%s\n' "$RESOLVED" | grep -qiE '(^|/)\.env(rc|(\.[a-z]+)*)?$'; then
    block "Writing to .env files requires manual review — may contain secrets"
fi
if printf '%s\n' "$RESOLVED" | grep -qiE '(^|/)\.mcp\.json$'; then
    block "Writing to .mcp.json requires manual review — potential MCP server injection"
fi
if printf '%s\n' "$RESOLVED" | grep -qiE '\.claude/settings(\.local)?\.json$'; then
    block "Writing to project-level Claude settings requires manual review"
fi
case "$RESOLVED" in
    "$H"/.claude/settings.json)
        block "Writing to global Claude settings is not allowed" ;;
esac
case "$FILE" in
    "$H"/.claude/settings.json)
        block "Writing to global Claude settings is not allowed" ;;
esac
[[ "$RESOLVED" == ""$H"/.claude/scripts/"* ]] && block "Writing to Claude hook scripts is not allowed — prevents disabling security hooks"
[[ "$FILE" == ""$H"/.claude/scripts/"* ]] && block "Writing to Claude hook scripts is not allowed — prevents disabling security hooks"
[[ "$RESOLVED" == ""$H"/.claude/hooks/"* ]] && block "Writing to Claude hook scripts is not allowed — prevents disabling security hooks"
[[ "$FILE" == ""$H"/.claude/hooks/"* ]] && block "Writing to Claude hook scripts is not allowed — prevents disabling security hooks"
# CI/CD pipeline files
if printf '%s\n' "$RESOLVED" | grep -qiE '\.github/workflows/|\.gitlab-ci\.yml$|Jenkinsfile$|azure-pipelines\.yml$|\.travis\.yml$|bitbucket-pipelines\.yml$|\.buildkite/|\.circleci/'; then
    block "Writing to CI/CD pipeline files requires manual review"
fi
# System directories
[[ "$RESOLVED" == "/etc/"* ]] && block "Writing to system directories is not allowed"
[[ "$RESOLVED" == "/usr/"* ]] && block "Writing to system directories is not allowed"
[[ "$RESOLVED" == "/System/"* ]] && block "Writing to system directories is not allowed"
[[ "$RESOLVED" == "/bin/"* ]] && block "Writing to system directories is not allowed"
[[ "$RESOLVED" == "/sbin/"* ]] && block "Writing to system directories is not allowed"
[[ "$RESOLVED" == "/private/etc/"* ]] && block "Writing to system directories is not allowed"
[[ "$RESOLVED" == "/private/bin/"* ]] && block "Writing to system binary directories is not allowed"
[[ "$RESOLVED" == "/private/sbin/"* ]] && block "Writing to system binary directories is not allowed"
# Persistence mechanisms (launchd, cron, systemd, autostart)
[[ "$RESOLVED" == ""$H"/Library/LaunchAgents/"* ]] && block "Writing persistence mechanism files (launchd, cron) is not allowed"
[[ "$FILE" == ""$H"/Library/LaunchAgents/"* ]] && block "Writing persistence mechanism files (launchd, cron) is not allowed"
[[ "$RESOLVED" == "/Library/LaunchDaemons/"* ]] && block "Writing persistence mechanism files (launchd, cron) is not allowed"
[[ "$RESOLVED" == "/var/spool/cron/"* ]] && block "Writing persistence mechanism files (launchd, cron) is not allowed"
[[ "$RESOLVED" == "/private/var/spool/cron/"* ]] && block "Writing persistence mechanism files (launchd, cron) is not allowed"
[[ "$RESOLVED" == ""$H"/.config/autostart/"* ]] && block "Writing to XDG autostart is not allowed"
[[ "$FILE" == ""$H"/.config/autostart/"* ]] && block "Writing to XDG autostart is not allowed"
[[ "$RESOLVED" == ""$H"/.local/share/systemd/user/"* ]] && block "Writing to user systemd units is not allowed"
[[ "$FILE" == ""$H"/.local/share/systemd/user/"* ]] && block "Writing to user systemd units is not allowed"
shopt -u nocasematch
