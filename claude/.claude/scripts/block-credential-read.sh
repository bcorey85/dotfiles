#!/usr/bin/env bash
# PreToolUse hook: block reading credential/secret files
INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
if [ -z "$FILE" ]; then exit 0; fi

if echo "$FILE" | grep -qiE '(\.aws/(credentials|config)|credentials\.json|service\.account\.json|\.kube/config|\.docker/config\.json|\.boto|\.s3cfg|\.netrc|\.git-credentials|\.npmrc|token\.json)'; then
    echo "BLOCKED: Reading cloud/service credential files is not allowed" >&2
    exit 2
fi
