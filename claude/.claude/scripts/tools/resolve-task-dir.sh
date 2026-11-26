#!/usr/bin/env bash
# resolve-task-dir.sh — resolve the /eng-spec task directory under docs/plans/ or the git-dir plan root
# Shared by /verify-branch, /branch-recap, /code, and /adr. Do NOT reimplement inline.
#
# docs/eng-specs/ is the pre-rename root; both are searched so repos that have
# not migrated keep resolving. Drop the legacy root once none remain.
#
# A repo with no docs/plans keeps its plan folders in the git-dir root,
# <git dir>/claude-plans/, where <git dir> is `git rev-parse --path-format=absolute --git-dir`
# of the current folder (a linked worktree has its own). The root survives a reboot and adds
# no file to the tracked tree. Paths under it print ABSOLUTE; docs/plans paths print relative.
#
# usage: resolve-task-dir.sh [<path-or-ticket>]
#        resolve-task-dir.sh --home <slug>
#   <path>    existing directory -> used directly
#   <ticket>  e.g. ABC-400 (case-insensitive) -> glob docs/plans/ABC-400-*/
#             (task dir), then the same under docs/eng-specs and the git-dir root,
#             else docs/plans/ABC-400*.md (legacy flat plan)
#   (empty)   infer ticket from the current branch name (TICKET-NUM-prefix); with no
#             ticket, the single folder in the git-dir root (exit 3 when it holds several)
#   --home    <slug> is non-empty, not '.' or '..', no '/'.
#             Prints where a new plan folder for <slug> goes: docs/plans/<slug> when the
#             current folder has a docs/plans directory, else <git dir>/claude-plans/<slug>
#
# exit 0: exactly one task DIRECTORY match, printed on stdout. The plan inside
#         it is plan.md (spec.md in older folders); the ticket is 00-ticket.md. (--home: the path.)
# exit 5: no task dir, exactly one legacy flat plan FILE, printed
# exit 3: multiple matches, all printed on stdout (caller asks the user)
# exit 4: nothing resolvable (caller asks the user for a path)
# exit 2: --home with a bad slug, or with no docs/plans and no git repo
set -euo pipefail

# Print the directories the globs match: one exits 0, several exit 3. None returns.
print_dir_matches() {
  local count=0 found="" d
  for d in "$@"; do
    [ -d "$d" ] || continue
    count=$((count + 1))
    found="${found}${d%/}
"
  done
  case "$count" in
    0) return 0 ;;
    1) printf '%s' "$found"; exit 0 ;;
    *) printf '%s' "$found"; exit 3 ;;
  esac
}

specs="docs/plans"
legacy="docs/eng-specs"

git_dir=$(git rev-parse --path-format=absolute --git-dir 2>/dev/null || true)
plans_root=""
if [ -n "$git_dir" ]; then
  plans_root="$git_dir/claude-plans"
fi

if [ "${1:-}" = "--home" ]; then
  slug="${2:-}"
  case "$slug" in
    ""|.|..|*/*) echo "usage: resolve-task-dir.sh --home <slug>  (slug: non-empty, not '.' or '..', no '/')" >&2; exit 2 ;;
  esac
  if [ -d "$specs" ]; then
    printf '%s\n' "$specs/$slug"
    exit 0
  fi
  if [ -z "$plans_root" ]; then
    echo "no $specs directory and not in a git repo: no place for a plan folder" >&2
    exit 2
  fi
  printf '%s\n' "$plans_root/$slug"
  exit 0
fi

arg="${1:-}"

if [ -n "$arg" ] && [ -d "$arg" ]; then
  printf '%s\n' "${arg%/}"
  exit 0
fi

ticket=""
if printf '%s' "$arg" | grep -qE '^[A-Za-z]+-[0-9]+$'; then
  ticket=$(printf '%s' "$arg" | tr '[:lower:]' '[:upper:]')
else
  ticket=$(git rev-parse --abbrev-ref HEAD 2>/dev/null | grep -oE '^[a-zA-Z]+-[0-9]+' | tr '[:lower:]' '[:upper:]' || true)
fi

if [ -z "$ticket" ]; then
  # No ticket and no argument: the git-dir root's only folder is the plan.
  if [ -z "$arg" ] && [ -n "$plans_root" ]; then
    print_dir_matches "$plans_root"/*/
  fi
  echo "no ticket in arguments or branch name" >&2
  exit 4
fi

task_globs=("$specs/$ticket/" "$specs/$ticket"-*/ "$legacy/$ticket/" "$legacy/$ticket"-*/)
if [ -n "$plans_root" ]; then
  task_globs+=("$plans_root/$ticket/" "$plans_root/$ticket"-*/)
fi

# No task dir: fall through to the eng-spec file lookup.
print_dir_matches "${task_globs[@]}"

fcount=0
ffound=""
for f in "$specs/$ticket"*.md "$legacy/$ticket"*.md; do
  [ -f "$f" ] || continue
  fcount=$((fcount + 1))
  ffound="${ffound}${f}
"
done

case "$fcount" in
  0) echo "no task directory or plan matching $specs/$ticket* (or $legacy/$ticket*)" >&2; exit 4 ;;
  1) printf '%s' "$ffound"; exit 5 ;;
  *) printf '%s' "$ffound"; exit 3 ;;
esac
