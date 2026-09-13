#!/usr/bin/env bash
# PostToolUse hook: warn when a rewritten agent/skill body ships banned rationale.
# CLAUDE.md bans rationale in agent/skill bodies (why-the-rule, measurement results,
# dispatch/finding counts, dates, "this was retired because", persuasion). This is a
# WARN, not a block: "because" is overloaded (instructional vs. defense), so a human
# triages each hit. The rationale check fires only on
# claude/.claude/{agents,skills}/*.md; the portability check also covers
# commands/.
INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
[ -z "$FILE" ] && exit 0
echo "$FILE" | grep -qE '\.claude/(agents|skills|commands)/.*\.md$' || exit 0
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

if [ -n "$HITS" ] && echo "$FILE" | grep -qE '\.claude/(agents|skills)/.*\.md$'; then
  echo "dead-prose-gate: possible banned rationale in $(basename "$FILE") — the rule ships every dispatch; keep the RULE, cut the defense:" >&2
  echo "$HITS" | sed 's/^/  /' >&2
fi

PORT=$(grep -nE '/Users/|/home/[a-z]|\bdotfiles\b' "$FILE" 2>/dev/null)
if [ -n "$PORT" ]; then
  echo "dead-prose-gate: hardcoded path or repo name in $(basename "$FILE") — agents, skills and commands must be portable across WSL/Ubuntu/macOS/Arch:" >&2
  echo "$PORT" | sed 's/^/  /' >&2
fi
exit 0
