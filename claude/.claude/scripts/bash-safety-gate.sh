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

if echo "$CMD" | grep -qiE 'rm\s+-[a-z]*r[a-z]*f' && echo "$CMD" | grep -qiE '(\s/(\s|$)|\s/(home|mnt|etc|usr|var)(\s|/)|\s~/|\s\$HOME/)'; then
    block "rm -rf on broad system paths is not allowed"
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
