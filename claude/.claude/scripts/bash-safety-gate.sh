#!/usr/bin/env bash
INPUT=$(cat)
CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
if [ -z "$CMD" ]; then exit 0; fi

block() {
    jq -n --arg reason "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$reason}}'
    exit 0
}

if echo "$CMD" | grep -qiE '\b(ssh|scp|rsync)\b'; then
    block "SSH connections (ssh, scp, rsync) to remote hosts are not allowed"
fi

if echo "$CMD" | grep -qiE 'ansible-vault\s+(view|decrypt)\b'; then
    block "ansible-vault view/decrypt is not allowed — use ansible-vault edit instead"
fi

if echo "$CMD" | grep -qiE '(cat|head|tail|less|more)\s+.*(\.aws/credentials|\.aws/config|\.kube/config|\.docker/config\.json|\.boto|\.s3cfg|\.netrc|\.git-credentials|\.npmrc|vault/password|1pass\.txt|github\.txt|\.(pem|key|p12|pfx)|\.ssh/(id_rsa|id_ed25519|id_ecdsa|authorized_keys)|\.gnupg/)'; then
    block "Reading credential/secret files via shell is not allowed"
fi

if echo "$CMD" | grep -qiE 'git\s+push\b.*--(force|force-with-lease)\b|git\s+push\s+-f\b'; then
    block "Destructive git push (--force, --force-with-lease, -f) is not allowed"
fi

if echo "$CMD" | grep -qiE 'git\s+(reset\s+--hard|clean\s+-f)'; then
    block "Destructive git commands (reset --hard, clean -f) are not allowed"
fi

if echo "$CMD" | grep -qiE 'git\s+push\b' && echo "$CMD" | grep -qiE '\b(main|master)\b'; then
    block "Pushing directly to main/master is not allowed"
fi

if echo "$CMD" | grep -qE '\brm\b'; then
    if echo "$CMD" | grep -qiE '\brm\b.*-[a-zA-Z]*[rf]'; then
        if ! echo "$CMD" | grep -qiE '(node_modules|/dist\b|\bdist/|\b\.cache\b|/tmp/|\bcoverage\b|\.next\b|\.nuxt\b|\.turbo\b)'; then
            block "rm with -r or -f flags may delete untracked files — not git-recoverable"
        fi
    fi
fi

if echo "$CMD" | grep -qiE '(curl|wget)\s.*\|\s*(ba)?sh'; then
    block "Pipe-to-shell (curl|bash) is not allowed"
fi

if echo "$CMD" | grep -qiE 'chmod\s+777'; then
    block "chmod 777 sets world-writable permissions — use a safer mode"
fi

if echo "$CMD" | grep -qiE '\b(DROP\s+(TABLE|DATABASE|SCHEMA)|TRUNCATE\s+TABLE|DELETE\s+FROM\s+\S+\s*;)'; then
    block "Destructive database operations (DROP, TRUNCATE, unfiltered DELETE) are not allowed"
fi

if echo "$CMD" | grep -qiE 'docker\s+run.*--(privileged|net=host)|docker\s+run.*-v\s+/:/'; then
    block "Docker privileged mode, host networking, and root volume mounts are not allowed"
fi

if echo "$CMD" | grep -qiE '(terraform|pulumi|cdktf)\s+destroy'; then
    block "Infrastructure destroy commands are not allowed"
fi

if echo "$CMD" | grep -qiE '(pip|pip3)\s+install\s+https?://|npm\s+install\s+https?://|yarn\s+add\s+https?://'; then
    block "Installing packages from arbitrary URLs is not allowed — use a registry"
fi

if echo "$CMD" | grep -qiE 'gh\s+(secret|variable)\s+(set|remove|delete)\b'; then
    block "gh secret/variable mutation is not allowed"
fi

if echo "$CMD" | grep -qiE 'gh\s+repo\s+(delete|rename|transfer)\b'; then
    block "gh repo destructive operations are not allowed"
fi

if echo "$CMD" | grep -qiE 'gh\s+release\s+delete\b'; then
    block "gh release delete is not allowed"
fi

if echo "$CMD" | grep -qiE '(pnpm|npm|yarn|bun)\s+publish\b'; then
    block "Package publishing is not git-reversible"
fi

if echo "$CMD" | grep -qiE 'git\s+push\b.*--tags?\b|git\s+push\b.*refs/tags/'; then
    block "Pushing tags to remote is not easily reversible"
fi

if echo "$CMD" | grep -qiE 'git\s+stash\b' && ! echo "$CMD" | grep -qiE 'git\s+stash\s+(list|show)\b'; then
    block "git stash is not allowed — agents overwriting each other's work via stash is a known issue"
fi

if echo "$CMD" | grep -qiE 'git\s+branch\s+-[a-zA-Z]*D'; then
    block "git branch -D force-deletes local commits that may not be pushed"
fi

# git tag mutations (can destroy release markers)
if echo "$CMD" | grep -qiE 'git\s+tag\s+(-[a-zA-Z]*[df]|--delete|--force)\b'; then
    block "git tag -d/-f may destroy release markers — not easily recovered"
fi

# gh workflow dispatch and release publishing
if echo "$CMD" | grep -qiE 'gh\s+workflow\s+run\b'; then
    block "gh workflow run triggers external CI — not git-reversible"
fi
if echo "$CMD" | grep -qiE 'gh\s+release\s+create\b'; then
    block "gh release create publishes artifacts — not git-reversible"
fi

# pnpm/npm run dangerous lifecycle scripts
if echo "$CMD" | grep -qiE '(pnpm|npm|yarn|bun)\s+run\s+(deploy|release|publish|postinstall|prepublish)\b'; then
    block "Running deploy/release/publish scripts is not git-reversible"
fi

# ANTHROPIC_* env mutation (redirects API traffic / exfiltrates auth token)
if echo "$CMD" | grep -qiE '(export\s+)?ANTHROPIC_(BASE_URL|AUTH_TOKEN|API_KEY)\s*='; then
    block "Mutating ANTHROPIC_* environment variables may redirect API traffic or exfiltrate auth tokens"
fi

# chmod +x / executable bit on protected paths
PROTECTED='(\.zshrc|\.bashrc|\.bash_profile|\.zprofile|\.zshenv|/\.ssh/|/\.aws/|/\.kube/|/\.docker/config|\.gitconfig|\.git-credentials|\.github/workflows|\.claude/settings\.json|/etc/|Library/LaunchAgents)'
if echo "$CMD" | grep -qiE 'chmod\s+(\+x|[0-7]*[1357])\b' && echo "$CMD" | grep -qiE "$PROTECTED"; then
    block "chmod +x on protected/system paths is not allowed"
fi

# Persistence mechanisms
if echo "$CMD" | grep -qiE '(crontab\s+(-e|[^-\s])|\bat\s+[0-9]|\blaunchctl\s+load\b|\bsystemctl\s+(enable|start)\b)'; then
    block "Persistence mechanisms (cron, at, launchd, systemctl) are not allowed"
fi

# Command substitution embedded in path arguments (CVE-2026-35020 injection vector)
if echo "$CMD" | grep -qE '\$\([^)]*\)/' || echo "$CMD" | grep -qE '/[^[:space:]]*\$\('; then
    block "Command substitution inside path arguments is a code injection vector"
fi

# File-write primitives to protected paths (bypass route when Edit is blocked)
if echo "$CMD" | grep -qiE 'sed\s+(-[a-zA-Z]*i|-i\b)' && echo "$CMD" | grep -qiE "$PROTECTED"; then
    block "sed -i on protected paths is not allowed"
fi
if echo "$CMD" | grep -qiE '(tee\s|>>\s*~?\/?(\.|/))' && echo "$CMD" | grep -qiE "$PROTECTED"; then
    block "Shell redirection to protected paths is not allowed"
fi
if echo "$CMD" | grep -qiE '(python3?|node|perl)\b.*-(c|e)\b.*(write|open|writeFile|writeSync)' && echo "$CMD" | grep -qiE "$PROTECTED"; then
    block "Scripted file writes to protected paths are not allowed"
fi
