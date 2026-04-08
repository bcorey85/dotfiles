#!/usr/bin/env bash
set -euo pipefail
# GENERATED — edit generator/rules/bash-safety-gate.yaml and run: python generator/cli.py generate
# PreToolUse hook: bash-safety-gate
trap 'printf '"'"'{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"bash-safety-gate encountered an unexpected error — denying for safety"}}\n'"'"'; exit 0' ERR
[[ -n "${CLAUDE_SKIP_HOOKS:-}" ]] && exit 0
INPUT=$(cat)

block() {
    local reason
    reason=$(printf '%s' "$1" | sed 's/"/\\"/g')
    printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}\n' "$reason"
    exit 0
}


# Try jq first, then python3, then sed as last resort
if command -v jq &>/dev/null; then
    CMD=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)
elif command -v python3 &>/dev/null; then
    CMD=$(printf '%s' "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('command',''))" 2>/dev/null)
else
    CMD=$(printf '%s' "$INPUT" | sed -n 's/.*"command"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)
fi

if [ -z "$CMD" ]; then
    block "Could not parse command from hook input — denying for safety"
fi

# Indirect execution — bypasses all keyword-based rules
if printf '%s\n' "$CMD" | grep -qiE '\b(bash|sh|dash|zsh|ksh)\s+-(c|s)\b'; then
    block "Indirect shell execution (sh -c) is not allowed — prevents rule bypass"
fi
if printf '%s\n' "$CMD" | grep -qiE '\beval\s'; then
    block "eval is not allowed — prevents rule bypass via dynamic command construction"
fi
if printf '%s\n' "$CMD" | grep -qiE '\bexec\s'; then
    if ! printf '%s\n' "$CMD" | grep -qiE '\b(docker|kubectl)\s+exec\b'; then
        block "exec replaces the current process and can bypass future hooks"
    fi
fi
if printf '%s\n' "$CMD" | grep -qiE '\bsource\s|\.\s+/'; then
    block "source/dot-source is not allowed — prevents rule bypass via external scripts"
fi
# Interpreter inline execution — runs arbitrary code, bypasses all keyword rules
if printf '%s\n' "$CMD" | grep -qiE '\b(python3?|node|perl|ruby|php)\b.*\s-(c|e|r)\b'; then
    block "Interpreter inline execution (python -c, node -e, perl -e) is not allowed — prevents rule bypass"
fi
# SSH connections to remote hosts
if printf '%s\n' "$CMD" | grep -qiE '\b(ssh|scp|rsync)\b'; then
    block "SSH connections (ssh, scp, rsync) to remote hosts are not allowed"
fi
# Ansible vault operations
if printf '%s\n' "$CMD" | grep -qiE 'ansible-vault\s+(view|decrypt)\b'; then
    block "ansible-vault view/decrypt is not allowed — use ansible-vault edit instead"
fi
# Reading credential/secret files via shell
if printf '%s\n' "$CMD" | grep -qiE '(cat|head|tail|less|more)\s+.*(\.aws/credentials|\.aws/config|\.kube/config|\.docker/config\.json|\.boto|\.s3cfg|\.netrc|\.git-credentials|\.npmrc|vault/password|1pass\.txt|github\.txt|\.(pem|key|p12|pfx)|\.ssh/(id_rsa|id_ed25519|id_ecdsa|authorized_keys)|\.gnupg/)'; then
    block "Reading credential/secret files via shell is not allowed"
fi
# Destructive git operations
if printf '%s\n' "$CMD" | grep -qiE 'git\s+push\b.*--(force|force-with-lease)\b|git\s+push\s+-f\b'; then
    block "Destructive git push (--force, --force-with-lease, -f) is not allowed"
fi
if printf '%s\n' "$CMD" | grep -qiE 'git\s+(reset\s+--hard|clean\s+(-f|--force)|checkout\s+--\s+\.)'; then
    block "Destructive git commands (reset --hard, clean -f, checkout -- .) are not allowed"
fi
if printf '%s\n' "$CMD" | grep -qiE 'git\s+push\b' && \
   printf '%s\n' "$CMD" | grep -qiE '\b(main|master)\b'; then
    block "Pushing directly to main/master is not allowed"
fi
if printf '%s\n' "$CMD" | grep -qiE 'git\s+(commit|push|merge)\b.*--no-verify'; then
    block "git --no-verify bypasses pre-commit security hooks and is not allowed"
fi
if printf '%s\n' "$CMD" | grep -qiE 'git\s+stash\b'; then
    if ! printf '%s\n' "$CMD" | grep -qiE 'git\s+stash\s+(list|show)\b'; then
        block "git stash is not allowed — agents overwriting each other's work via stash is a known issue"
    fi
fi
if printf '%s\n' "$CMD" | grep -qiE 'git\s+branch\s+-[a-zA-Z]*D'; then
    block "git branch -D force-deletes local commits that may not be pushed"
fi
if printf '%s\n' "$CMD" | grep -qiE 'git\s+tag\s+(-[a-zA-Z]*[df]|--delete|--force)\b'; then
    block "git tag -d/-f may destroy release markers — not easily recovered"
fi
if printf '%s\n' "$CMD" | grep -qiE 'git\s+push\b.*--tags?\b|git\s+push\b.*refs/tags/'; then
    block "Pushing tags to remote is not easily reversible"
fi
# rm with -r or -f flags on non-safe paths
if printf '%s\n' "$CMD" | grep -qiE '\brm\b.*-[a-zA-Z]*[rf]'; then
    if ! printf '%s\n' "$CMD" | grep -qiE '(git\s+rm\b|node_modules|/dist\b|\bdist/|\b\.cache\b|/tmp/|\bcoverage\b|\.next\b|\.nuxt\b|\.turbo\b)'; then
        block "rm with -r or -f flags may delete untracked files — not git-recoverable"
    fi
fi
# Generic pipe-to-shell
if printf '%s\n' "$CMD" | grep -qiE '\|\s*(ba)?sh\b|\|\s*zsh\b|\|\s*dash\b|\|\s*ksh\b'; then
    block "Pipe-to-shell is not allowed — piping any command into a shell interpreter"
fi
# Network exfiltration — outbound data transfer
if printf '%s\n' "$CMD" | grep -qiE 'curl\b.*(-d\b|--data|--upload-file|-F\b|-T\b|--form)'; then
    block "curl with data upload flags may exfiltrate sensitive data"
fi
if printf '%s\n' "$CMD" | grep -qiE 'wget\b.*--post-(data|file)'; then
    block "wget with POST flags may exfiltrate sensitive data"
fi
if printf '%s\n' "$CMD" | grep -qiE '\b(nc|ncat|socat|telnet)\b'; then
    block "Raw network tools (nc, ncat, socat, telnet) are not allowed"
fi
if printf '%s\n' "$CMD" | grep -qiE '\b(dig|nslookup|host)\b.*\$\('; then
    block "DNS lookup tools (dig, nslookup, host) may be used for data exfiltration"
fi
# Dangerous chmod modes
if printf '%s\n' "$CMD" | grep -qiE 'chmod\s+(777|666|a\+[rwx]|o\+[rwx]|\+s)\b'; then
    block "Dangerous chmod mode (777, 666, world-writable, setuid) — use a safer mode"
fi
if printf '%s\n' "$CMD" | grep -qiE 'chmod\s+(\+x|[0-7]*[1357])\b' && \
   printf '%s\n' "$CMD" | grep -qiE '(\.zshrc|\.bashrc|\.bash_profile|\.zprofile|\.zshenv|/\.ssh/|/\.aws/|/\.kube/|/\.docker/config|\.gitconfig|\.git-credentials|\.github/workflows|\.claude/settings\.json|/etc/|Library/LaunchAgents)'; then
    block "chmod +x on protected/system paths is not allowed"
fi
# Destructive database operations
if printf '%s\n' "$CMD" | grep -qiE '\b(DROP\s+(TABLE|DATABASE|SCHEMA)|TRUNCATE\s+TABLE|DELETE\s+FROM\s+\S+\s*;)'; then
    block "Destructive database operations (DROP, TRUNCATE, unfiltered DELETE) are not allowed"
fi
# Dangerous Docker configurations
if printf '%s\n' "$CMD" | grep -qiE 'docker\s+run.*--(privileged|net=host)|docker\s+run.*-v\s+/:/'; then
    block "Docker privileged mode, host networking, and root volume mounts are not allowed"
fi
# Infrastructure destroy commands
if printf '%s\n' "$CMD" | grep -qiE '(terraform|pulumi|cdktf)\s+destroy'; then
    block "Infrastructure destroy commands are not allowed"
fi
# Package installation from arbitrary URLs
if printf '%s\n' "$CMD" | grep -qiE '(pip|pip3)\s+install\s+https?://|npm\s+install\s+https?://|yarn\s+add\s+https?://'; then
    block "Installing packages from arbitrary URLs is not allowed — use a registry"
fi
# GitHub CLI mutations
if printf '%s\n' "$CMD" | grep -qiE 'gh\s+(secret|variable)\s+(set|remove|delete)\b'; then
    block "gh secret/variable mutation is not allowed"
fi
if printf '%s\n' "$CMD" | grep -qiE 'gh\s+repo\s+(delete|rename|transfer)\b'; then
    block "gh repo destructive operations are not allowed"
fi
if printf '%s\n' "$CMD" | grep -qiE 'gh\s+release\s+delete\b'; then
    block "gh release delete is not allowed"
fi
if printf '%s\n' "$CMD" | grep -qiE 'gh\s+workflow\s+run\b'; then
    block "gh workflow run triggers external CI — not git-reversible"
fi
if printf '%s\n' "$CMD" | grep -qiE 'gh\s+release\s+create\b'; then
    block "gh release create publishes artifacts — not git-reversible"
fi
# Package publishing
if printf '%s\n' "$CMD" | grep -qiE '(pnpm|npm|yarn|bun)\s+publish\b'; then
    block "Package publishing is not git-reversible"
fi
if printf '%s\n' "$CMD" | grep -qiE '(pnpm|npm|yarn|bun)\s+run\s+(deploy|release|publish|postinstall|prepublish)\b'; then
    block "Running deploy/release/publish scripts is not git-reversible"
fi
# Environment variable mutation and dumping
if printf '%s\n' "$CMD" | grep -qiE '(export\s+)?ANTHROPIC_(BASE_URL|AUTH_TOKEN|API_KEY)\s*='; then
    block "Mutating ANTHROPIC_* environment variables may redirect API traffic or exfiltrate auth tokens"
fi
if printf '%s\n' "$CMD" | grep -qiE '^\s*(env|printenv|set)\s*$'; then
    block "Dumping environment variables may expose secrets"
fi
if printf '%s\n' "$CMD" | grep -qiE 'cat\s+/proc/self/environ'; then
    block "Reading /proc/self/environ exposes all environment variables"
fi
# Persistence mechanisms
if printf '%s\n' "$CMD" | grep -qiE '(crontab\s+(-e|[^-\s])|\bat\s+[0-9]|\blaunchctl\s+load\b|\bsystemctl\s+(enable|start)\b)'; then
    block "Persistence mechanisms (cron, at, launchd, systemctl) are not allowed"
fi
# Command substitution injection
if printf '%s\n' "$CMD" | grep -qiE '\$\([^)]*\)/'; then
    block "Command substitution inside path arguments is a code injection vector"
fi
if printf '%s\n' "$CMD" | grep -qiE '/[^[:space:]]*\$\('; then
    block "Command substitution inside path arguments is a code injection vector"
fi
if printf '%s\n' "$CMD" | grep -qiE '`[^`]*`/'; then
    block "Command substitution inside path arguments is a code injection vector"
fi
# File-write primitives to protected paths (bypass route when Edit is blocked)
if printf '%s\n' "$CMD" | grep -qiE 'sed\s+(-[a-zA-Z]*i|-i\b)' && \
   printf '%s\n' "$CMD" | grep -qiE '(\.zshrc|\.bashrc|\.bash_profile|\.zprofile|\.zshenv|/\.ssh/|/\.aws/|/\.kube/|/\.docker/config|\.gitconfig|\.git-credentials|\.github/workflows|\.claude/settings\.json|/etc/|Library/LaunchAgents)'; then
    block "sed -i on protected paths is not allowed"
fi
if printf '%s\n' "$CMD" | grep -qiE '(tee\s|>>\s*~?\/?(\.|/))' && \
   printf '%s\n' "$CMD" | grep -qiE '(\.zshrc|\.bashrc|\.bash_profile|\.zprofile|\.zshenv|/\.ssh/|/\.aws/|/\.kube/|/\.docker/config|\.gitconfig|\.git-credentials|\.github/workflows|\.claude/settings\.json|/etc/|Library/LaunchAgents)'; then
    block "Shell redirection to protected paths is not allowed"
fi
if printf '%s\n' "$CMD" | grep -qiE '(python3?|node|perl)\b.*-(c|e)\b.*(write|open|writeFile|writeSync)' && \
   printf '%s\n' "$CMD" | grep -qiE '(\.zshrc|\.bashrc|\.bash_profile|\.zprofile|\.zshenv|/\.ssh/|/\.aws/|/\.kube/|/\.docker/config|\.gitconfig|\.git-credentials|\.github/workflows|\.claude/settings\.json|/etc/|Library/LaunchAgents)'; then
    block "Scripted file writes to protected paths are not allowed"
fi
