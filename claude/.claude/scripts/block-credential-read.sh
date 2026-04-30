#!/usr/bin/env bash
set -euo pipefail
# CB Security Hooks
# Version: 0.1.4
# ==========
# GENERATED — do not edit directly
# PreToolUse hook: block-credential-read
trap 'printf '"'"'{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"block-credential-read encountered an unexpected error — denying for safety"}}\n'"'"'; exit 0' ERR
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
                --arg hook "block-credential-read" \
                --arg reason "$1" \
                --arg value "$_val" \
                '{ts:$ts,hook:$hook,reason:$reason,value:$value}' 2>/dev/null) || true
        else
            local _sv _sr
            _sv=$(printf '%s' "$_val" | head -c 300 | sed 's/\\/\\\\/g; s/"/\\"/g')
            _sr=$(printf '%s' "$1"   | sed 's/\\/\\\\/g; s/"/\\"/g')
            _line=$(printf '{"ts":"%s","hook":"%s","reason":"%s","value":"%s"}' \
                "$_ts" "block-credential-read" "$_sr" "$_sv")
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

# Fast path: if nothing in the input can match any rule, allow immediately
if ! grep -qiE '(\.aws/(credentials|config))|(\.kube/config)|(\.docker/config\.json)|((\.config/gcloud/|\.gcloud/))|(\.azure/(accessTokens\.json|azureProfile\.json|clouds\.config|credentials|msal_token_cache))|((credentials\.json|service[._]account\.json|application_default_credentials\.json))|(\.ssh/(id_(rsa|ed25519|ecdsa|dsa)|authorized_keys|known_hosts|config))|(\.(pem|key|p12|pfx)$)|(\.gnupg/)|((^|/)\.env(rc|(\.[a-z]+)*)?$)|((\.npmrc|\.pypirc|\.gem/credentials|\.nuget/NuGet\.Config)$)|((\.boto|\.s3cfg|\.netrc|\.git-credentials|token\.json|\.dev\.vars|\.vault-token|\.htpasswd)$)|((^|/)\.(bash_history|zsh_history|sh_history|python_history|node_repl_history|mysql_history|psql_history|irb_history|rediscli_history|lesshst|viminfo)$)|((Chrome|Chromium|Google/Chrome)/(Default|Profile\s*\d+)/(Login Data|Cookies|Web Data))|(\.mozilla/firefox/[^/]+/(logins\.json|cookies\.sqlite|key[34]\.db|cert9\.db))|(Library/Cookies/Cookies\.binarycookies)|(\.config/gh/hosts\.yml)|(\.tfstate$)|((^|/)([^/]*decrypted[^/]*\.(ya?ml|json|env|txt|key|pem|gpg|enc)|[^/]+\.decrypted)$)' <<< "$RESOLVED"; then
    exit 0
fi
# Cloud credential files
if grep -qiE '\.aws/(credentials|config)' <<< "$RESOLVED"; then
    block "[aws_creds] [threat:6] Reading AWS credential files is not allowed"
fi
if grep -qiE '\.kube/config' <<< "$RESOLVED"; then
    block "[kube_config] [threat:6] Reading Kubernetes config is not allowed"
fi
if grep -qiE '\.docker/config\.json' <<< "$RESOLVED"; then
    block "[docker_config] [threat:6] Reading Docker config is not allowed"
fi
if grep -qiE '(\.config/gcloud/|\.gcloud/)' <<< "$RESOLVED"; then
    block "[gcp_creds] [threat:6] Reading GCP credential files is not allowed"
fi
if grep -qiE '\.azure/(accessTokens\.json|azureProfile\.json|clouds\.config|credentials|msal_token_cache)' <<< "$RESOLVED"; then
    block "[azure_creds] [threat:6] Reading Azure CLI credential files is not allowed"
fi
if grep -qiE '(credentials\.json|service[._]account\.json|application_default_credentials\.json)' <<< "$RESOLVED"; then
    block "[cloud_json_creds] [threat:6] Reading cloud credential JSON files is not allowed"
fi
# SSH and TLS/PKI keys
if grep -qiE '\.ssh/(id_(rsa|ed25519|ecdsa|dsa)|authorized_keys|known_hosts|config)' <<< "$RESOLVED"; then
    block "[ssh_keys] [threat:6] Reading SSH key/config files is not allowed"
fi
if grep -qiE '\.(pem|key|p12|pfx)$' <<< "$RESOLVED"; then
    block "[tls_keys] [threat:6] Reading TLS/PKI private key files is not allowed"
fi
# GPG, environment, and package manager credentials
if grep -qiE '\.gnupg/' <<< "$RESOLVED"; then
    block "[gpg] [threat:5] Reading GPG keyring files is not allowed"
fi
if grep -qiE '(^|/)\.env(rc|(\.[a-z]+)*)?$' <<< "$RESOLVED"; then
    if ! grep -qiE '\.(example|sample|template|dist|defaults|schema|test)$' <<< "$RESOLVED"; then
        block "[env_files] [threat:5] Reading .env files is not allowed — may contain secrets"
    fi
fi
if grep -qiE '(\.npmrc|\.pypirc|\.gem/credentials|\.nuget/NuGet\.Config)$' <<< "$RESOLVED"; then
    block "[pkg_creds] [threat:5] Reading package manager credential files is not allowed"
fi
if grep -qiE '(\.boto|\.s3cfg|\.netrc|\.git-credentials|token\.json|\.dev\.vars|\.vault-token|\.htpasswd)$' <<< "$RESOLVED"; then
    block "[misc_creds] [threat:5] Reading credential/secret files is not allowed"
fi
# Shell history files — may contain credentials typed on the command line (MITRE T1552.003)
if grep -qiE '(^|/)\.(bash_history|zsh_history|sh_history|python_history|node_repl_history|mysql_history|psql_history|irb_history|rediscli_history|lesshst|viminfo)$' <<< "$RESOLVED"; then
    block "[shell_history] [threat:6] Reading shell history files is not allowed — may contain credentials"
fi
# Browser credential and cookie stores
if grep -qiE '(Chrome|Chromium|Google/Chrome)/(Default|Profile\s*\d+)/(Login Data|Cookies|Web Data)' <<< "$RESOLVED"; then
    block "[chrome_creds] [threat:6] Reading browser credential stores is not allowed"
fi
if grep -qiE '\.mozilla/firefox/[^/]+/(logins\.json|cookies\.sqlite|key[34]\.db|cert9\.db)' <<< "$RESOLVED"; then
    block "[firefox_creds] [threat:6] Reading browser credential stores is not allowed"
fi
if grep -qiE 'Library/Cookies/Cookies\.binarycookies' <<< "$RESOLVED"; then
    block "[safari_cookies] [threat:6] Reading browser credential stores is not allowed"
fi
# Other credential stores
if grep -qiE '\.config/gh/hosts\.yml' <<< "$RESOLVED"; then
    block "[gh_auth] [threat:5] Reading GitHub CLI auth config is not allowed"
fi
if grep -qiE '\.tfstate$' <<< "$RESOLVED"; then
    block "[terraform_state] [threat:6] Reading Terraform state files is not allowed — may contain plaintext secrets"
fi
if grep -qiE '(^|/)([^/]*decrypted[^/]*\.(ya?ml|json|env|txt|key|pem|gpg|enc)|[^/]+\.decrypted)$' <<< "$RESOLVED"; then
    block "[decrypted_files] [threat:6] Reading decrypted secret/vault files is not allowed"
fi
shopt -u nocasematch
