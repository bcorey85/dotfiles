#!/usr/bin/env bash
# PreToolUse hook: block Write/Edit to sensitive paths
INPUT=$(cat)
FILE=$(printf '%s' "$INPUT" | sed -n 's/.*"file_path"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)
if [ -z "$FILE" ]; then exit 0; fi

# Resolve to absolute path to catch traversal attacks (e.g. ../../.ssh/id_rsa).
# Tries python3, then realpath; falls back to the raw path if neither is available.
if command -v python3 &>/dev/null; then
    RESOLVED=$(python3 -c "import os,sys; print(os.path.abspath(sys.argv[1]))" "$FILE" 2>/dev/null) || RESOLVED="$FILE"
elif command -v realpath &>/dev/null; then
    RESOLVED=$(realpath "$FILE" 2>/dev/null) || RESOLVED="$FILE"
else
    RESOLVED="$FILE"
fi

block() {
    local reason
    reason=$(printf '%s' "$1" | sed 's/"/\\"/g')
    printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}\n' "$reason"
    exit 0
}

H="$HOME"

# Shell profiles
case "$RESOLVED" in
    "$H"/.zshrc|"$H"/.bashrc|"$H"/.bash_profile|"$H"/.profile|"$H"/.zprofile|"$H"/.zshenv|"$H"/.bash_login|"$H"/.tcshrc|"$H"/.cshrc)
        block "Writing to shell profile files is not allowed — persists across sessions" ;;
esac
[[ "$RESOLVED" == "$H/.config/fish/"* ]] && block "Writing to fish config is not allowed"

# SSH
[[ "$RESOLVED" == "$H/.ssh/"* ]] && block "Writing to ~/.ssh/ is not allowed"

# Global git credentials
case "$RESOLVED" in
    "$H"/.gitconfig|"$H"/.git-credentials)
        block "Writing to global git config/credentials is not allowed" ;;
esac

# Cloud credential directories
if [[ "$RESOLVED" == "$H/.aws/"* ]] || [[ "$RESOLVED" == "$H/.gcloud/"* ]] || \
   [[ "$RESOLVED" == "$H/.kube/"* ]] || [[ "$RESOLVED" == "$H/.docker/"* ]]; then
    block "Writing to cloud credential directories is not allowed"
fi

# CI/CD pipeline files
if echo "$RESOLVED" | grep -qiE '\.github/workflows/|\.circleci/config|\.gitlab-ci\.yml$|Jenkinsfile$|azure-pipelines\.yml$|\.travis\.yml$'; then
    block "Writing to CI/CD pipeline files requires manual review"
fi

# Global Claude settings (project-level .claude/ is fine)
[[ "$RESOLVED" == "$H/.claude/settings.json" ]] && block "Writing to global Claude settings is not allowed"

# System directories
if [[ "$RESOLVED" == /etc/* ]] || [[ "$RESOLVED" == /usr/* ]] || [[ "$RESOLVED" == /System/* ]] || [[ "$RESOLVED" == /bin/* ]] || [[ "$RESOLVED" == /sbin/* ]]; then
    block "Writing to system directories is not allowed"
fi

# Persistence: launchd / cron
if [[ "$RESOLVED" == "$H/Library/LaunchAgents/"* ]] || \
   [[ "$RESOLVED" == "/Library/LaunchDaemons/"* ]] || \
   [[ "$RESOLVED" == "/var/spool/cron/"* ]]; then
    block "Writing persistence mechanism files (launchd, cron) is not allowed"
fi
