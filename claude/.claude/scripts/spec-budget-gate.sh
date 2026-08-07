#!/usr/bin/env bash
# PreToolUse hook: spec-budget-gate — hard word budget on the planning tree.
#
# Why: the 2026-07 eval program (~/agent-evals/PROGRAM-LEDGER.md) showed the
# planning config grew 21,000 words in 5 days, model edits run 12:1
# add-to-remove, and "a budget on a file is not a budget on a system" — a cap
# on SKILL.md alone just routes growth into the uncapped satellite files.
#
# Two ceilings, because there are two different costs:
#
#   RESIDENT — SKILL.md plus the single largest file in phases/. eng-spec reads
#   one phase file at a time, so this is what is actually in context during a
#   run. It is also what survives compaction: Claude Code re-attaches only the
#   first 5,000 tokens (~3,750 words) of an invoked skill after a summary, so a
#   spine that outgrows that is silently truncated from the end. Phase files
#   arrive as tool results and are NOT re-attached at all — the spine's
#   re-read instruction is the only recovery path, which is why the spine has
#   to stay small enough to survive whole.
#
#   TOTAL — every guarded file at once: /eng-spec, its spec-* agents, and the
#   _shared files it consumes. A sprawl backstop with no external basis; it
#   exists to force displacement. Splitting a phase file in two lowers RESIDENT
#   but not TOTAL, so a split has to be a real phase boundary rather than a way
#   to buy budget.
#
# Growth only by displacement: to add words past a ceiling, delete words
# elsewhere in the same set first.
#
# CEILING changes require the user's explicit sign-off — never raise one to
# make an edit fit. TOTAL has held at 7,500 since install (baseline 6,465 on
# 2026-07-13) and the 2026-08 skill-sizing research found nothing that
# contradicts it. Baseline at the phase-file split (2026-08-07): 850 resident.
RESIDENT_CEILING=1200
TOTAL_CEILING=7500

[ -n "${CLAUDE_SKIP_HOOKS:-}" ] && exit 0
INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
[ -z "$FILE" ] && exit 0

# templates/ holds artifacts copied verbatim into a task directory, never read as
# instruction — they cost a task's context once, not every invocation's.
case "$FILE" in
    */skills/eng-spec/templates/*) exit 0 ;;
    */skills/eng-spec/*) ;;
    */agents/spec-questions.md|*/agents/spec-leak-check.md|*/agents/spec-research.md) ;;
    */agents/spec-criteria.md|*/agents/goal-blind-researcher.md) ;;
    */skills/_shared/invariant-survey.md|*/skills/_shared/design-decision-format.md) ;;
    */skills/_shared/plan-format.md|*/skills/_shared/closing-phases.md) ;;
    *) exit 0 ;;
esac

# Both the stowed repo tree and the live ~/.claude tree share the layout
# <base>/skills/... and <base>/agents/... — derive <base> from the target path.
BASE="${FILE%/skills/*}"
[ "$BASE" = "$FILE" ] && BASE="${FILE%/agents/*}"
[ "$BASE" = "$FILE" ] && exit 0

TOOL=$(echo "$INPUT" | jq -r '.tool_name // empty')
OLD=0; [ -f "$FILE" ] && OLD=$(wc -w < "$FILE")
case "$TOOL" in
    Write)
        NEW=$(echo "$INPUT" | jq -r '.tool_input.content // ""' | wc -w)
        ;;
    Edit|MultiEdit)
        ADD=$(jq -r '[.tool_input.edits // [.tool_input] | .[].new_string // ""] | join(" ")' <<<"$INPUT" 2>/dev/null | wc -w)
        DEL=$(jq -r '[.tool_input.edits // [.tool_input] | .[].old_string // ""] | join(" ")' <<<"$INPUT" 2>/dev/null | wc -w)
        NEW=$((OLD + ADD - DEL))
        ;;
    *) exit 0 ;;
esac

# Word count a guarded file will have once this edit lands.
prospective() {
    if [ "$1" = "$FILE" ]; then echo "$NEW"
    elif [ -f "$1" ]; then wc -w < "$1"
    else echo 0
    fi
}

GUARDED=$(find "$BASE/skills/eng-spec" -type f -not -path '*/templates/*' 2>/dev/null)
for f in "$BASE/agents/spec-questions.md" "$BASE/agents/spec-leak-check.md" \
         "$BASE/agents/spec-research.md" "$BASE/agents/spec-criteria.md" \
         "$BASE/agents/goal-blind-researcher.md" \
         "$BASE/skills/_shared/invariant-survey.md" \
         "$BASE/skills/_shared/design-decision-format.md" \
         "$BASE/skills/_shared/plan-format.md" "$BASE/skills/_shared/closing-phases.md"; do
    [ -e "$f" ] && GUARDED="$GUARDED
$f"
done
TOTAL=$(cat $GUARDED 2>/dev/null | wc -w)
NEW_TOTAL=$((TOTAL - OLD + NEW))

SPINE=$(prospective "$BASE/skills/eng-spec/SKILL.md")
PHASES=$(find "$BASE/skills/eng-spec/phases" -name '*.md' 2>/dev/null)
case "$FILE" in */skills/eng-spec/phases/*.md) PHASES="$PHASES
$FILE" ;; esac
MAX_PHASE=0
for p in $PHASES; do
    n=$(prospective "$p")
    [ "$n" -gt "$MAX_PHASE" ] && MAX_PHASE=$n
done
RESIDENT=$((SPINE + MAX_PHASE))

deny() {
    printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}\n' "$1"
    exit 0
}

if [ "$RESIDENT" -gt "$RESIDENT_CEILING" ] && [ "$NEW" -gt "$OLD" ]; then
    deny "spec-budget-gate: this edit puts eng-spec's resident load at ~$RESIDENT words (ceiling $RESIDENT_CEILING) — SKILL.md ($SPINE) plus its largest phase file ($MAX_PHASE). That is what is actually in context during a run and what has to survive compaction. Cut words from the spine or from that phase file in the same change, or move a rule into the agent that is the only one who applies it. Splitting a phase file only helps if it is a real phase boundary. Ask the user to raise RESIDENT_CEILING; never raise it yourself."
fi

if [ "$NEW_TOTAL" -gt "$TOTAL_CEILING" ] && [ "$NEW_TOTAL" -gt "$TOTAL" ]; then
    deny "spec-budget-gate: this edit grows the planning tree to ~$NEW_TOTAL words (ceiling $TOTAL_CEILING, currently $TOTAL). The planning system grows only by displacement — delete words elsewhere in the guarded set (eng-spec, spec-* agents, its _shared files) in the same change, or ask the user to raise TOTAL_CEILING in spec-budget-gate.sh. Never raise it yourself."
fi
exit 0
