#!/usr/bin/env bash
set -euo pipefail
# CB Security Hooks
# Version: 0.1.2
# ==========
# GENERATED — edit generator/rules/block-credential-read.yaml and run: python generator/cli.py generate
# PreToolUse hook: block-credential-read
trap 'printf '"'"'{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"block-credential-read encountered an unexpected error — denying for safety"}}\n'"'"'; exit 0' ERR
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

# Cloud credential files
if printf '%s\n' "$RESOLVED" | grep -qiE '\.aws/(credentials|config)'; then
    block "Reading AWS credential files is not allowed"
fi
if printf '%s\n' "$RESOLVED" | grep -qiE '\.kube/config'; then
    block "Reading Kubernetes config is not allowed"
fi
if printf '%s\n' "$RESOLVED" | grep -qiE '\.docker/config\.json'; then
    block "Reading Docker config is not allowed"
fi
if printf '%s\n' "$RESOLVED" | grep -qiE '(\.config/gcloud/|\.gcloud/)'; then
    block "Reading GCP credential files is not allowed"
fi
if printf '%s\n' "$RESOLVED" | grep -qiE '\.azure/(accessTokens\.json|azureProfile\.json|clouds\.config|credentials|msal_token_cache)'; then
    block "Reading Azure CLI credential files is not allowed"
fi
if printf '%s\n' "$RESOLVED" | grep -qiE '(credentials\.json|service[._]account\.json|application_default_credentials\.json)'; then
    block "Reading cloud credential JSON files is not allowed"
fi
# SSH and TLS/PKI keys
if printf '%s\n' "$RESOLVED" | grep -qiE '\.ssh/(id_(rsa|ed25519|ecdsa|dsa)|authorized_keys|known_hosts|config)'; then
    block "Reading SSH key/config files is not allowed"
fi
if printf '%s\n' "$RESOLVED" | grep -qiE '\.(pem|key|p12|pfx)$'; then
    block "Reading TLS/PKI private key files is not allowed"
fi
# GPG, environment, and package manager credentials
if printf '%s\n' "$RESOLVED" | grep -qiE '\.gnupg/'; then
    block "Reading GPG keyring files is not allowed"
fi
if printf '%s\n' "$RESOLVED" | grep -qiE '(^|/)\.env(rc|(\.[a-z]+)*)?$'; then
    block "Reading .env files is not allowed — may contain secrets"
fi
if printf '%s\n' "$RESOLVED" | grep -qiE '(\.npmrc|\.pypirc|\.gem/credentials|\.nuget/NuGet\.Config)$'; then
    block "Reading package manager credential files is not allowed"
fi
if printf '%s\n' "$RESOLVED" | grep -qiE '(\.boto|\.s3cfg|\.netrc|\.git-credentials|token\.json|\.dev\.vars|\.vault-token|\.htpasswd)$'; then
    block "Reading credential/secret files is not allowed"
fi
# Other credential stores
if printf '%s\n' "$RESOLVED" | grep -qiE '\.config/gh/hosts\.yml'; then
    block "Reading GitHub CLI auth config is not allowed"
fi
if printf '%s\n' "$RESOLVED" | grep -qiE '\.tfstate$'; then
    block "Reading Terraform state files is not allowed — may contain plaintext secrets"
fi
if printf '%s\n' "$RESOLVED" | grep -qiE '(^|/)([^/]*decrypted[^/]*\.(ya?ml|json|env|txt|key|pem|gpg|enc)|[^/]+\.decrypted)$'; then
    block "Reading decrypted secret/vault files is not allowed"
fi
shopt -u nocasematch
