#!/usr/bin/env bash
# claude-doctor: validate the ~/.claude configuration.
#
# Checks:
#   1. settings JSON files parse (jq)
#   2. every hook command path referenced in settings.json exists and is executable
#   3. every file in hooks/ is registered in settings.json (orphan detection)
#   4. agent frontmatter: name matches filename, model value is legal (sonnet|haiku|opus)
#   5. skill frontmatter: name matches directory, allowed-tools contains no unknown tool names
#   6. opencode sync: agent filename diff, CLAUDE.md vs AGENTS.md mtime drift
#   7. shellcheck over scripts/ and hooks/ (if installed)
#
# Exit 0 = clean (warnings allowed), exit 1 = at least one error.

CLAUDE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OPENCODE_DIR="$HOME/.config/opencode"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ERRORS=0
WARNINGS=0

print_success() { echo -e "${GREEN}✓${NC} $1"; }
print_error()   { echo -e "${RED}✗${NC} $1"; ERRORS=$((ERRORS + 1)); }
print_warn()    { echo -e "${YELLOW}!${NC} $1"; WARNINGS=$((WARNINGS + 1)); }
print_info()    { echo -e "${BLUE}==${NC} $1"; }

if ! command -v jq &>/dev/null; then
  echo "jq is required" >&2
  exit 1
fi

# --- 1. JSON validity -------------------------------------------------------
print_info "JSON files"
for f in "$CLAUDE_DIR"/settings.json "$CLAUDE_DIR"/settings.local.json "$CLAUDE_DIR"/keybindings.json; do
  [[ -f "$f" ]] || continue
  if jq empty "$f" 2>/dev/null; then
    print_success "valid JSON: ${f/#$HOME/~}"
  else
    print_error "invalid JSON: ${f/#$HOME/~}"
  fi
done

# --- 2. hook command paths --------------------------------------------------
print_info "Hook command paths in settings.json"
SETTINGS="$CLAUDE_DIR/settings.json"
if [[ -f "$SETTINGS" ]]; then
  while IFS= read -r cmd; do
    expanded="${cmd//\$HOME/$HOME}"
    expanded="${expanded//\$\{HOME\}/$HOME}"
    expanded="${expanded/#\~/$HOME}"
    # Check every absolute-path-looking token in the command string
    found_path=0
    while IFS= read -r token; do
      token="${token%\"}"; token="${token#\"}"
      [[ "$token" == /* ]] || continue
      found_path=1
      if [[ ! -e "$token" ]]; then
        print_error "hook path missing: $token  (from: $cmd)"
      elif [[ "$token" == *.sh || "$token" == *.mjs ]] && [[ ! -x "$token" && "$token" == *.sh ]]; then
        print_warn "hook script not executable: $token"
      fi
    done < <(echo "$expanded" | tr ' ' '\n' | grep -E '^"?(/|~)' || true)
    if [[ $found_path -eq 0 ]]; then
      # Bare command (e.g. "jq ...", inline shell) — check the first word is on PATH
      first_word=$(echo "$expanded" | awk '{print $1}')
      if ! command -v "$first_word" &>/dev/null && ! type "$first_word" &>/dev/null 2>&1; then
        print_warn "hook command not on PATH: $first_word  (from: $cmd)"
      fi
    fi
  done < <(jq -r '[.hooks // {} | .. | objects | select(has("command")) | .command] | unique[]' "$SETTINGS")
  print_success "hook path scan complete"
else
  print_warn "no settings.json at ${SETTINGS/#$HOME/~}"
fi

# --- 2b. expected hook registrations -----------------------------------------
print_info "Expected hook registrations"
reg_blob=$(cat "$SETTINGS" "$CLAUDE_DIR/settings.local.json" 2>/dev/null)
for pair in "log-skill-use.sh:skill-usage telemetry" "stub-guard.sh:acceptance-stub guard"; do
  script="${pair%%:*}"; label="${pair#*:}"
  [[ -f "$CLAUDE_DIR/scripts/$script" ]] || continue
  if grep -q "$script" <<<"$reg_blob"; then
    print_success "registered: scripts/$script"
  else
    print_warn "scripts/$script exists but is not registered in settings.json — $label inactive"
  fi
done
if [[ -f "$CLAUDE_DIR/scripts/log-skill-use.sh" ]] && grep -q "log-skill-use.sh" <<<"$reg_blob"; then
  if ! jq -r '.hooks.UserPromptSubmit // [] | tostring' "$SETTINGS" 2>/dev/null | grep -q "log-skill-use"; then
    print_warn "log-skill-use.sh not wired to UserPromptSubmit — user-typed /commands won't be counted"
  fi
fi

# --- 3. orphaned hook files -------------------------------------------------
print_info "Orphaned files in hooks/"
if [[ -d "$CLAUDE_DIR/hooks" ]]; then
  settings_blob=$(cat "$SETTINGS" "$CLAUDE_DIR/settings.local.json" 2>/dev/null)
  for f in "$CLAUDE_DIR"/hooks/*; do
    [[ -f "$f" ]] || continue
    base=$(basename "$f")
    [[ "$base" == .* ]] && continue
    if grep -q "$base" <<<"$settings_blob"; then
      print_success "registered: hooks/$base"
    else
      print_warn "hooks/$base is not referenced in settings.json — dead hook?"
    fi
  done
fi

# --- 4. agent frontmatter ---------------------------------------------------
print_info "Agent frontmatter"
LEGAL_MODELS="sonnet haiku opus"
for f in "$CLAUDE_DIR"/agents/*.md; do
  [[ -f "$f" ]] || continue
  base=$(basename "$f" .md)
  fm=$(awk '/^---$/{n++; next} n==1{print} n>=2{exit}' "$f")
  name=$(echo "$fm" | awk -F': *' '$1=="name"{print $2; exit}' | tr -d '"')
  model=$(echo "$fm" | awk -F': *' '$1=="model"{print $2; exit}' | tr -d '"')
  if [[ -z "$name" ]]; then
    print_error "agents/$base.md: missing 'name' in frontmatter"
  elif [[ "$name" != "$base" ]]; then
    print_error "agents/$base.md: name '$name' does not match filename"
  fi
  if [[ -n "$model" ]]; then
    legal=0
    for m in $LEGAL_MODELS; do [[ "$model" == "$m" ]] && legal=1; done
    if [[ $legal -eq 0 ]]; then
      print_error "agents/$base.md: illegal model '$model' (expected: $LEGAL_MODELS, or omit)"
    fi
  fi
  # skills: preload entries must resolve to real skills
  while IFS= read -r s; do
    [[ -z "$s" ]] && continue
    if [[ ! -f "$CLAUDE_DIR/skills/$s/SKILL.md" ]]; then
      print_error "agents/$base.md: preloaded skill '$s' not found at skills/$s/SKILL.md"
    fi
  done < <(echo "$fm" | awk '/^skills:/{f=1;next} f&&/^[[:space:]]*-[[:space:]]*/{sub(/^[[:space:]]*-[[:space:]]*/,""); gsub(/["'"'"']/,""); print; next} f{f=0}')
  # memory: legal scopes
  memval=$(echo "$fm" | awk -F': *' '$1=="memory"{print $2; exit}' | tr -d '"')
  if [[ -n "$memval" && "$memval" != "user" && "$memval" != "project" && "$memval" != "local" ]]; then
    print_error "agents/$base.md: illegal memory scope '$memval' (expected: user|project|local)"
  fi
  # maxTurns must be numeric
  mt=$(echo "$fm" | awk -F': *' '$1=="maxTurns"{print $2; exit}' | tr -d '"')
  if [[ -n "$mt" && ! "$mt" =~ ^[0-9]+$ ]]; then
    print_error "agents/$base.md: maxTurns '$mt' is not a number"
  fi
done
print_success "agent frontmatter scan complete ($(ls "$CLAUDE_DIR"/agents/*.md 2>/dev/null | wc -l) files)"

# --- 5. skill frontmatter ---------------------------------------------------
print_info "Skill frontmatter"
KNOWN_TOOLS="Agent Bash Read Write Edit Glob Grep LSP Skill WebFetch WebSearch NotebookEdit AskUserQuestion TaskCreate TaskUpdate TaskList TaskGet TaskOutput TaskStop Artifact Monitor SendMessage"
for f in "$CLAUDE_DIR"/skills/*/SKILL.md; do
  [[ -f "$f" ]] || continue
  dir=$(basename "$(dirname "$f")")
  fm=$(awk '/^---$/{n++; next} n==1{print} n>=2{exit}' "$f")
  name=$(echo "$fm" | awk -F': *' '$1=="name"{print $2; exit}' | tr -d '"')
  if [[ -z "$name" ]]; then
    print_error "skills/$dir: missing 'name' in frontmatter"
  elif [[ "$name" != "$dir" ]]; then
    print_error "skills/$dir: name '$name' does not match directory"
  fi
  tools=$(echo "$fm" | awk -F': *' '$1=="allowed-tools"{print $2; exit}' | tr -d '[]"' | tr ',' ' ')
  for t in $tools; do
    t=$(echo "$t" | xargs)
    t="${t%%(*}"                              # Bash(cmd:*) grants → base tool name
    [[ -z "$t" ]] && continue
    [[ "$t" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue   # leftover fragment from a parenthesized grant
    [[ "$t" == mcp__* ]] && continue          # MCP tools are server-defined, not lintable here
    known=0
    for k in $KNOWN_TOOLS; do [[ "$t" == "$k" ]] && known=1; done
    if [[ $known -eq 0 ]]; then
      print_error "skills/$dir: unknown tool '$t' in allowed-tools (stale name? 'Task' was renamed to 'Agent')"
    fi
  done
done
print_success "skill frontmatter scan complete ($(ls "$CLAUDE_DIR"/skills/*/SKILL.md 2>/dev/null | wc -l) files)"

# --- 6. opencode sync -------------------------------------------------------
print_info "opencode sync"
if [[ -d "$OPENCODE_DIR/agents" ]]; then
  claude_agents=$(ls "$CLAUDE_DIR"/agents/*.md 2>/dev/null | xargs -n1 basename | sort)
  oc_agents=$(ls "$OPENCODE_DIR"/agents/*.md 2>/dev/null | xargs -n1 basename | sort)
  missing_in_oc=$(comm -23 <(echo "$claude_agents") <(echo "$oc_agents"))
  extra_in_oc=$(comm -13 <(echo "$claude_agents") <(echo "$oc_agents"))
  if [[ -n "$missing_in_oc" ]]; then
    print_warn "agents in claude but not opencode: $(echo "$missing_in_oc" | tr '\n' ' ')"
  fi
  if [[ -n "$extra_in_oc" ]]; then
    print_warn "agents in opencode but not claude: $(echo "$extra_in_oc" | tr '\n' ' ')"
  fi
  [[ -z "$missing_in_oc" && -z "$extra_in_oc" ]] && print_success "agent sets match"
  if [[ -f "$CLAUDE_DIR/CLAUDE.md" && -f "$OPENCODE_DIR/AGENTS.md" ]]; then
    if [[ "$CLAUDE_DIR/CLAUDE.md" -nt "$OPENCODE_DIR/AGENTS.md" ]]; then
      print_warn "~/.claude/CLAUDE.md is newer than opencode AGENTS.md — global rules may have drifted"
    else
      print_success "AGENTS.md is not older than CLAUDE.md"
    fi
  fi
else
  print_warn "opencode not found at ${OPENCODE_DIR/#$HOME/~} — skipping sync check"
fi

# --- 7. shellcheck (optional) -----------------------------------------------
print_info "shellcheck"
if command -v shellcheck &>/dev/null; then
  sc_out=$(shellcheck -S warning "$CLAUDE_DIR"/scripts/*.sh "$CLAUDE_DIR"/hooks/*.sh 2>/dev/null)
  if [[ -z "$sc_out" ]]; then
    print_success "shellcheck clean (warning level)"
  else
    count=$(grep -c '^In ' <<<"$sc_out")
    print_warn "shellcheck reported issues in $count location(s) — run: shellcheck -S warning ~/.claude/scripts/*.sh ~/.claude/hooks/*.sh"
  fi
else
  print_info "shellcheck not installed — skipping"
fi

# --- summary ------------------------------------------------------------------
echo
if [[ $ERRORS -gt 0 ]]; then
  echo -e "${RED}$ERRORS error(s)${NC}, ${YELLOW}$WARNINGS warning(s)${NC}"
  exit 1
fi
echo -e "${GREEN}clean${NC} — $WARNINGS warning(s)"
