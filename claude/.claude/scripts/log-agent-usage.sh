#!/usr/bin/env bash
# log-agent-usage.sh — per-dispatch token telemetry for /audit review.
#
# Registered in settings.json: PostToolUse (matcher: Agent). Appends one line
# per completed subagent dispatch to ~/.claude/agent-usage.jsonl:
#   {ts, repo, agent, model, desc, tokens, toolUses, durationMs,
#    reportChars, noResult, respKeys}
#
# The token fields probe several candidate paths because the Agent
# tool_response schema is not contractual across CLI versions; respKeys is the
# self-diagnostic — if tokens comes back null, look there for the real field
# name and add it to the fallback chain. Never blocks: always exits 0.
#
# reportChars / noResult are the YIELD proxy for agents that do not self-report
# findings (general-purpose, Explore) the way reviewers do via
# log-review-finding. Captured mechanically from the returned report so nothing
# depends on the orchestrator remembering to log:
#   reportChars = length of the agent's final report text.
#   noResult    = the report matches a "found nothing" signature.
# Both are null on the async schema (a background dispatch returns an
# `outputFile` path, not inline `content`, and carries no inline token cost
# either, so it is outside the cost question). This is a PROXY, not ground
# truth: a terse-but-correct answer scores low reportChars, so the pair only
# flags the clear-waste tail — real token cost spent on a trivial or
# empty-handed report. Read it (self-join on this file):
#   jq -r 'select(.agent=="general-purpose" and .tokens!=null)
#          | [.tokens, .reportChars, .noResult, .desc] | @tsv' agent-usage.jsonl
# High tokens with noResult=true or tiny reportChars is the tail to inspect;
# the ambiguous middle needs the transcript, never this number alone.
set -euo pipefail

command -v jq >/dev/null || exit 0
input=$(cat)

evt=$(jq -r '.hook_event_name // ""' <<<"$input")
[[ "$evt" == "PostToolUse" ]] || exit 0

repo=$(basename "${CLAUDE_PROJECT_DIR:-$PWD}")
out="${AGENT_USAGE_FILE:-$HOME/.claude/agent-usage.jsonl}"

jq -c --arg repo "$repo" '
(.tool_response | if type == "object" then . else {} end) as $r |
($r.content
 | if type == "string" then .
   elif type == "array" then (map(.text? // "") | join(" "))
   else null end) as $txt |
{
  ts: (now | todate),
  repo: $repo,
  agent: (.tool_input.subagent_type // "general-purpose"),
  model: (.tool_input.model // "inherit"),
  desc: ((.tool_input.description // "") | .[0:80]),
  tokens: ($r.totalTokens // $r.usage.total_tokens
           // $r.total_tokens // $r.usage.output_tokens // null),
  toolUses: ($r.totalToolUseCount // $r.tool_uses // null),
  durationMs: ($r.totalDurationMs // $r.duration_ms // null),
  reportChars: (if ($txt | type) == "string" then ($txt | length) else null end),
  noResult: (if ($txt | type) == "string"
             then ($txt | ascii_downcase
                   | test("no results|not found|no matches|could not find|couldn.t find|nothing (found|to report)|no relevant|no such|unable to find|found no |no occurrences|does not (exist|appear)"))
             else null end),
  respKeys: ((.tool_response | keys?) // (.tool_response | type))
}' <<<"$input" >> "$out" 2>/dev/null || true

exit 0
