#!/usr/bin/env bash
# mechanical-check-gate.sh — PreToolUse(Agent). Blocks the orchestrator from
# DELEGATING a check that is specified as a mechanical script invocation.
#
# Why this exists, measured: `/code`'s vacuous-green pre-flight is written in
# code/SKILL.md as a bash call, with the reason stated inline ("A class that
# survives three oracles needs a check that cannot forget"). Across round-2
# arm 1 the orchestrator dispatched a haiku `Explore` agent named
# "Phase N vacuous-green preflight" instead — three times, ~32k output tokens
# total — and NONE of the three ever invoked the script. Each returned an
# LLM impression of the test files that read, downstream, as a clean pre-flight.
#
# That is the exact failure mode the checker exists to prevent, one level up in
# the dispatcher: a check whose "did not run" is indistinguishable from its
# "passed". Prose in the skill already tried to prevent it ("runs mechanically
# rather than as an instruction to a gate agent") and lost. Per the global
# maintenance rule — mechanize, move, or delete; never just add emphasis — this
# is the mechanization.
#
# Precision: matches on `.tool_input.description` ONLY, never the prompt.
# The description is the short task-naming field ("Phase 5 vacuous-green
# preflight"); handoff prose that merely MENTIONS a vacuous test lives in the
# prompt and must not trip the gate. Coder dispatches are exempt so the script
# itself remains editable by the normal loop.
#
# Contract (shared with the CB gates, consumed by omp's claude-security-bridge):
#   stdin  — PreToolUse hook JSON
#   stdout — {"hookSpecificOutput":{...,"permissionDecision":"deny",...}}, exit 0
#   silent exit 0 otherwise

set -euo pipefail

[[ -n "${CLAUDE_SKIP_HOOKS:-}" ]] && exit 0

input="$(cat)"

tool_name=$(printf '%s' "$input" | jq -r '.tool_name // ""')
[[ "$tool_name" == "Agent" ]] || exit 0

desc=$(printf '%s' "$input" | jq -r '.tool_input.description // ""')
subagent=$(printf '%s' "$input" | jq -r '.tool_input.subagent_type // ""')

# Coders may be dispatched to work ON the script; they are not the failure mode.
case "$subagent" in
*coder*) exit 0 ;;
esac

shopt -s nocasematch
blocked=""
if [[ "$desc" =~ vacu(ous|ity) ]]; then
  blocked="vacuous-green pre-flight"
elif [[ "$desc" =~ pre-?flight ]] && [[ "$desc" =~ (test|green|suite) ]]; then
  blocked="vacuous-green pre-flight"
fi
shopt -u nocasematch

[[ -n "$blocked" ]] || exit 0

{
  echo "[mechanical-check-gate] BLOCKED: Agent dispatch described as '${desc}'."
  echo "The ${blocked} is a MECHANICAL check. Run it yourself, in this session:"
  echo "    bash ~/.claude/scripts/vacuous-green-preflight.sh both '<test command>' <changed test files>"
  echo "An agent's reading of the test files is not this check. Measured: three such"
  echo "dispatches, ~32k tokens, zero invocations of the script — each reporting clean."
} >&2
reason="Dispatching an agent for the ${blocked} is blocked. It is specified in code/SKILL.md as a mechanical bash invocation precisely because a gate agent can forget it: run \`bash ~/.claude/scripts/vacuous-green-preflight.sh both '<test command>' <changed test files>\` yourself and read its exit code (1 = SUSPECTs to /fix, 2 = the check DID NOT RUN). An agent's impression of the test files is not this check."
jq -cn --arg r "$reason" '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":$r}}'
exit 0
