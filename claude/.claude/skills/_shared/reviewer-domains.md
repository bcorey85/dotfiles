# Cross-Cutting Reviewer Domains (deterministic trigger)

Canonical trigger definitions for the single-domain specialist reviewers
(`security-reviewer`, `perf-reviewer`, `smell-reviewer`). `review-loop` reads this file to decide,
**deterministically — no judgment call**, whether a converged diff touches a
domain's surface and therefore warrants a specialist pass. Keeping the patterns
here (not inline in `review-loop`) makes them one editable, portable source.

## The signal

A domain is **eligible** for a converged diff when EITHER holds:

1. **Path match** — a changed file path matches one of the domain's path globs.
2. **Content match** — an added/removed diff line matches one of the domain's
   content regexes (case-insensitive).

Compute it from the settled diff, e.g.:

```bash
# paths
git diff --name-only HEAD | rg -i '<domain path glob, alternated>'
# content (added/removed lines only)
git diff HEAD -U0 | rg '^[+-]' | rg -iE '<domain content regex>'
```

Either non-empty → the domain is eligible. Eligibility is a floor, never a
ceiling: a caller-supplied force flag (`+sec` / `+perf` / `+smell`) makes a domain
eligible even with no match; `no-specialist` suppresses the pass entirely.

**Exception — the `smell` domain triggers on diff SIZE, not paths/content**
(structure smells have no path or keyword signature; volume is the risk proxy).
See its section below.

## Default patterns (generic, portable — no repo names, no single stack)

Defaults cover the endpoint/data surfaces of TS/Node, Django, C#/.NET, and Go.
The endpoint-layer globs (`routes`, `controllers`, `handlers`, `views`, `api`)
are deliberately part of the **security** set: the highest-value security
findings are by _omission_ (a missing auth/authz check adds no security-flavored
line for the content regex to catch), so the path side must cover where
endpoints live, not just where auth code lives.

### security

- **Path globs**: `**/auth/**`, `**/*auth*`, `**/session*`, `**/middleware/**`,
  `**/routes/**`, `**/controllers/**`, `**/*controller*`, `**/handlers/**`,
  `**/*handler*`, `**/api/**`, `**/views*`, `**/*viewset*`, `**/serializers*`,
  `**/migrations/**`, `**/*.sql`, `**/*polic*`, `**/*permission*`, `**/*rbac*`,
  `**/*crypto*`, `**/*security*`, `**/*.env*`, `**/secrets*`
- **Content regex**:
  `password|secret|token|jwt|api[_-]?key|crypto|hash|encrypt|decrypt|authoriz|authenticat|permission|\brole\b|tenant|\brls\b|policy|grant\b|cors|csrf|sanitiz|escap|\beval\(|\bexec\(|deserializ|redirect|SELECT\s.*WHERE|INSERT\s+INTO|is[_-]?admin|csrf_exempt|AllowAny|permission_classes|login_required|\[Authorize|AllowAnonymous|HandleFunc|\bmux\b|gin\.|echo\.`

### perf

- **Path globs**: `**/*.sql`, `**/migrations/**`, `**/models/**`, `**/models*`,
  `**/managers*`, `**/repositor*/**`, `**/*repository*`, `**/*.query.*`,
  `**/*dao*`, `**/entities/**`, `**/schema*`
- **Content regex**:
  `SELECT\s|\.find\(|\.findAll\(|\.query\(|\.aggregate\(|createQueryBuilder|await .*\bfor\b|for .*await|forEach\(.*await|\.map\(.*await|Promise\.all|LIMIT|OFFSET|JOIN\s|include:|eager|lazy|\.count\(|objects\.|select_related|prefetch_related|values_list|annotate\(|bulk_create|\.Include\(|\.ThenInclude\(|ToListAsync|IQueryable|FromSql|SaveChanges|Task\.WhenAll|\.Query\(|\.QueryRow\(|\.Exec\(|rows\.Next|Preload\(|gorm\.`

### smell

Size trigger, not path/content — eligible when EITHER holds on the converged diff:

1. **≥ 40 added lines** across source files (sum of column 1 from
   `git diff HEAD --numstat`, excluding lockfiles and generated files).
2. **≥ 1 new source file** (`git ls-files --others --exclude-standard` plus
   `git diff --name-only --diff-filter=A HEAD`) — a new file is where
   re-implementing an existing helper is most likely.

```bash
git diff HEAD --numstat | rg -v 'lock|generated|snapshot' | awk '{s+=$1} END {print s}'
```

Test-only diffs (every changed file a test file) are NOT eligible — test
structure is `code-reviewer`'s `[test-fluff]` channel and the test-intent
gates, not this domain. Force with `+smell`; suppressed by `no-specialist`
like the others.

## Per-repo extension

A repo may add to (never replace) the defaults with `.claude/reviewer-triggers.json`
at its root:

```json
{
  "security": {
    "paths": ["**/driver_factory*", "cube.py"],
    "content": [
      "get_object_schema|current_tenant|public:\\s*true|effective_tenant"
    ]
  },
  "perf": {
    "paths": ["model/cubes/**", "model/views/**"],
    "content": ["sub_query|::text|many_to_one|one_to_many"]
  }
}
```

`review-loop` merges these additively with the defaults above. Absent the file,
defaults alone apply. This is how a codebase teaches the trigger its own
security surface (e.g. an RLS/tenant-isolation mechanism) or query-shape surface
without editing any global file.
