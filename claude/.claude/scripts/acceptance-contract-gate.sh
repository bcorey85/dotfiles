#!/usr/bin/env bash
# PreToolUse hook: acceptance-contract-gate — the acceptance contract is immutable
# to every agent, including me.
#
# Why this exists: an acceptance test written from the ticket's criteria is the
# only oracle in the loop that was authored before the implementation existed and
# therefore cannot have been shaped by it. That property is worth exactly as much
# as it is enforceable: for any agent chasing green, the cheapest path is always
# weakening the assertion — skip it, loosen it, delete it — so an oracle an agent
# may edit is not an oracle at all. The prior art (ATDD / Specification by
# Example, and TCK suites like the Java TCK or Web Platform Tests) is unanimous on
# the same point: the conformance suite is owned by the specifier, never by the
# implementer. review-loop.md already refuses to auto-fix acceptance-spec
# failures; this makes that refusal deterministic instead of instructional.
#
# Contract: a file is an acceptance contract if ACCEPTANCE-CONTRACT appears in its
# first 10 lines. Marker, not path convention — it survives the rename that
# activates the file, needs no spec lookup, and is visible to a human opening it.
#
# Scope, stated honestly:
#   - This blocks WRITES, not reads. Read-invisibility is what the paper actually
#     recommends, and it is not mechanizable here: PreToolUse input carries no
#     agent identity on 2.1.220 (agent_id/agent_type exist only in
#     Subagent{Start,Stop}; anthropics/claude-code#40140), so a read-deny could
#     not distinguish an implementing coder from the main thread authoring the
#     file. A blanket read-deny would break authoring. The prohibition therefore
#     lives in coder-core as a prompt rule, which is weaker — say so out loud
#     rather than assuming the coder never looked.
#   - It blocks the main thread too, deliberately. Hooks bind agents, not the
#     human, which makes the user the only actor who can change an acceptance
#     contract — in their editor, by hand. That asymmetry IS the guardrail; do not
#     add an agent-side escape hatch to it.
#   - Creating a new contract file is allowed (no marker on disk yet to protect).
#     Shell-level clobbering (`mv`, `>`) is bash-safety-gate's surface, not this
#     hook's; a rename is how activation works, so it must stay legal.
#
# When this blocks you: report it and stop. Either the code is wrong or the
# intended behavior changed, and only the user decides which.

[ -n "${CLAUDE_SKIP_HOOKS:-}" ] && exit 0

INPUT=$(cat)
[ -z "$INPUT" ] && exit 0

command -v jq >/dev/null 2>&1 || exit 0
FILE=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[ -z "$FILE" ] && exit 0
[ -f "$FILE" ] || exit 0

head -n 10 "$FILE" 2>/dev/null | grep -q 'ACCEPTANCE-CONTRACT' || exit 0

# Sole permitted agent edit (user ruling, 2026-08-02, LOOP-COST round 6):
# ACTIVATION. An Edit whose old/new strings are byte-identical except for the
# transformation `func contract_` -> `func Test` flips a stub into the
# runner-collected form without touching a single assertion. That is the edit
# the contract file's own header names as the only legal one; everything else
# — weakening, deleting, rewriting, or a rename bundled with any other change
# — still lands on the deny below.
TOOL=$(printf '%s' "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
if [ "$TOOL" = "Edit" ]; then
  OLD=$(printf '%s' "$INPUT" | jq -r '.tool_input.old_string // empty' 2>/dev/null)
  NEW=$(printf '%s' "$INPUT" | jq -r '.tool_input.new_string // empty' 2>/dev/null)
  if [ -n "$OLD" ] && [ -n "$NEW" ] && [ "$NEW" != "$OLD" ] \
     && [ "${OLD//func contract_/func Test}" = "$NEW" ]; then
    exit 0
  fi
fi

REASON="acceptance-contract-gate: $FILE is an acceptance contract (ACCEPTANCE-CONTRACT marker) and is immutable to agents. It encodes the ticket's acceptance criteria, was written before the implementation existed, and is the only oracle here that the implementation cannot have shaped. Fix the code so the contract passes. If the contract itself is wrong — the intended behavior changed, or the assertion misreads the criterion — that is the user's call, not yours: report which assertion you believe is wrong and why, and stop. Do not weaken, skip, delete, or rewrite it. To ACTIVATE a stub, use an Edit whose ONLY change is renaming func contract_* to func Test* — that exact transformation passes this gate; bundling any other change with the rename re-blocks it. Do not route around this via shell writes."
printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}\n' "$REASON"
exit 0
