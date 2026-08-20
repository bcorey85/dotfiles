#!/usr/bin/env bash
# PostToolUse hook: warn when a rewritten agent/skill body ships banned rationale.
# CLAUDE.md bans rationale in agent/skill bodies (why-the-rule, measurement results,
# dispatch/finding counts, dates, "this was retired because", persuasion). This is a
# WARN, not a block: "because" is overloaded (instructional vs. defense), so a human
# triages each hit. Fires only on writes to claude/.claude/{agents,skills}/*.md.
INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
[ -z "$FILE" ] && exit 0
echo "$FILE" | grep -qE '\.claude/(agents|skills)/.*\.md$' || exit 0
[ -f "$FILE" ] || exit 0

# High-signal rationale patterns. Kept tight to avoid crying wolf — instructional
# "because" ("read these in order, because X happens") is deliberately NOT matched.
HITS=$(grep -nEi \
  -e '(you|this|it) exists?( only)? because' \
  -e 'the reason (you|this|it) exists?' \
  -e '(chosen|not a) measured (one|budget|default)' \
  -e 'chosen (budget|default)s?, not' \
  -e '(this |it )?was retired|retired because' \
  -e 'measured basis|as measured|we measured' \
  -e '[^0-9]20[0-9]{2}-[0-9]{2}-[0-9]{2}' \
  "$FILE" 2>/dev/null)

if [ -n "$HITS" ]; then
  echo "dead-prose-gate: possible banned rationale in $(basename "$FILE") — the rule ships every dispatch; keep the RULE, cut the defense:" >&2
  echo "$HITS" | sed 's/^/  /' >&2
fi
exit 0
