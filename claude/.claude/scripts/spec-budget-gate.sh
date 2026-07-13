#!/usr/bin/env bash
# PreToolUse hook: spec-budget-gate — hard word budget on the planning tree.
#
# Why: the 2026-07 eval program (~/agent-evals/PROGRAM-LEDGER.md) showed the
# planning config grew 21,000 words in 5 days, model edits run 12:1
# add-to-remove, and "a budget on a file is not a budget on a system" — a cap
# on SKILL.md alone just routes growth into the uncapped satellite files. So
# the budget covers the SYSTEM: /eng-spec, its three spec-* agents, and the
# _shared files it consumes. Growth only by displacement: to add words past
# the ceiling, delete words elsewhere in the same set first.
#
# CEILING changes require the user's explicit sign-off — never raise it to
# make an edit fit. Baseline at install (2026-07-13): 6,465 words.
CEILING=7500

[ -n "${CLAUDE_SKIP_HOOKS:-}" ] && exit 0
INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
[ -z "$FILE" ] && exit 0

case "$FILE" in
    */skills/eng-spec/*) ;;
    */agents/spec-questions.md|*/agents/spec-leak-check.md|*/agents/spec-research.md) ;;
    */skills/_shared/invariant-survey.md|*/skills/_shared/design-decision-format.md) ;;
    */skills/_shared/plan-format.md|*/skills/_shared/closing-phases.md) ;;
    *) exit 0 ;;
esac

# Both the stowed repo tree and the live ~/.claude tree share the layout
# <base>/skills/... and <base>/agents/... — derive <base> from the target path.
BASE="${FILE%/skills/*}"
[ "$BASE" = "$FILE" ] && BASE="${FILE%/agents/*}"
[ "$BASE" = "$FILE" ] && exit 0

GUARDED=$(find "$BASE/skills/eng-spec" -type f 2>/dev/null)
for f in "$BASE/agents/spec-questions.md" "$BASE/agents/spec-leak-check.md" \
         "$BASE/agents/spec-research.md" "$BASE/skills/_shared/invariant-survey.md" \
         "$BASE/skills/_shared/design-decision-format.md" \
         "$BASE/skills/_shared/plan-format.md" "$BASE/skills/_shared/closing-phases.md"; do
    [ -e "$f" ] && GUARDED="$GUARDED
$f"
done
TOTAL=$(cat $GUARDED 2>/dev/null | wc -w)

TOOL=$(echo "$INPUT" | jq -r '.tool_name // empty')
case "$TOOL" in
    Write)
        NEW=$(echo "$INPUT" | jq -r '.tool_input.content // ""' | wc -w)
        OLD=0; [ -f "$FILE" ] && OLD=$(wc -w < "$FILE")
        PROSPECTIVE=$((TOTAL - OLD + NEW))
        ;;
    Edit|MultiEdit)
        ADD=$(jq -r '[.tool_input.edits // [.tool_input] | .[].new_string // ""] | join(" ")' <<<"$INPUT" 2>/dev/null | wc -w)
        DEL=$(jq -r '[.tool_input.edits // [.tool_input] | .[].old_string // ""] | join(" ")' <<<"$INPUT" 2>/dev/null | wc -w)
        PROSPECTIVE=$((TOTAL + ADD - DEL))
        ;;
    *) exit 0 ;;
esac

if [ "$PROSPECTIVE" -gt "$CEILING" ] && [ "$PROSPECTIVE" -gt "$TOTAL" ]; then
    REASON="spec-budget-gate: this edit grows the planning tree to ~$PROSPECTIVE words (ceiling $CEILING, currently $TOTAL). The planning system grows only by displacement — delete words elsewhere in the guarded set (eng-spec, spec-* agents, its _shared files) in the same change, or ask the user to raise CEILING in spec-budget-gate.sh. Never raise it yourself."
    printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}\n' "$REASON"
fi
exit 0
