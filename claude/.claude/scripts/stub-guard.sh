#!/usr/bin/env bash
# stub-guard.sh — PostToolUse (Write|Edit) warning hook for acceptance stubs.
#
# Invariant it watches: a todo-marked acceptance stub's behavior sentence never
# disappears from a spec file — it survives either as a todo or as a real test
# bearing the same sentence. Coders legitimately CREATE stubs (phase 1) and
# FLIP them to real tests (later phases), so this is a warning, not a block:
# after an edit to a test file, any todo sentence that was removed AND no
# longer appears anywhere in the file gets flagged into context. The drift
# gate and /verify remain the hard checks.
set -euo pipefail

command -v jq >/dev/null || exit 0
input=$(cat)

file=$(jq -r '.tool_input.file_path // ""' <<<"$input")
[[ -z "$file" || ! -f "$file" ]] && exit 0

# Only test/spec files.
case "$file" in
  *.spec.*|*.test.*|*_test.*|*/test_*.py|*/tests.py) ;;
  *) exit 0 ;;
esac

# Need a git repo to see what the edit removed.
repo_root=$(git -C "$(dirname "$file")" rev-parse --show-toplevel 2>/dev/null) || exit 0

# Todo-stub primitives across runners: it.todo(...) / test.todo(...) / xit(...) /
# pytest "todo" markers. Extract the quoted sentence from each REMOVED todo line.
removed_sentences=$(git -C "$repo_root" diff -U0 -- "$file" 2>/dev/null \
  | grep -E '^-' | grep -vE '^---' \
  | grep -E '\.(todo)\(|@pytest\.mark\.todo|(^|[^a-zA-Z])xit\(' \
  | sed -nE "s/.*[\(,][[:space:]]*['\"\`]([^'\"\`]+)['\"\`].*/\1/p" || true)

[[ -z "$removed_sentences" ]] && exit 0

missing=""
while IFS= read -r sentence; do
  [[ -z "$sentence" ]] && continue
  if ! grep -qF "$sentence" "$file"; then
    missing="${missing}  - \"${sentence}\"\n"
  fi
done <<<"$removed_sentences"

[[ -z "$missing" ]] && exit 0

warning=$(printf 'stub-guard WARNING: this edit removed todo stub(s) from %s whose behavior sentence no longer appears anywhere in the file:\n%b\nStubs are executable requirements — a flip must keep the sentence as the test name. If this was a legitimate flip with a renamed sentence, stop and restore the original wording; if the stub was wrong, report it instead of deleting it (coder-core: Acceptance Stubs Are Requirements).' "$file" "$missing")

jq -cn --arg ctx "$warning" \
  '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: $ctx}}'
exit 0
