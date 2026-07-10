#!/usr/bin/env bash
# log_route.sh <ticket> <recommended> <rule> <chosen> <agreed>
# Appends one JSONL routing record for /plan. Joinable with /escape lane=
# tags via /audit review to measure routing quality over time.
set -euo pipefail

TICKET="${1:?ticket}"
RECOMMENDED="${2:?recommended lane}"
RULE="${3:?matched rule}"
CHOSEN="${4:?chosen lane}"
AGREED="${5:?agreed true|false}"

LOG_DIR="${HOME}/.claude/data"
LOG_FILE="${LOG_DIR}/plan-routing.jsonl"
mkdir -p "${LOG_DIR}"

if command -v jq >/dev/null 2>&1; then
  jq -cn \
    --arg ts "$(date -Iseconds)" \
    --arg project "$(pwd)" \
    --arg ticket "$TICKET" \
    --arg recommended "$RECOMMENDED" \
    --arg rule "$RULE" \
    --arg chosen "$CHOSEN" \
    --argjson agreed "$AGREED" \
    '{ts:$ts, project:$project, ticket:$ticket, recommended:$recommended,
      rule:$rule, chosen:$chosen, agreed:$agreed}' >> "${LOG_FILE}"
else
  # Minimal fallback; assumes args contain no double quotes.
  printf '{"ts":"%s","project":"%s","ticket":"%s","recommended":"%s","rule":"%s","chosen":"%s","agreed":%s}\n' \
    "$(date -Iseconds)" "$(pwd)" "$TICKET" "$RECOMMENDED" "$RULE" "$CHOSEN" "$AGREED" \
    >> "${LOG_FILE}"
fi
