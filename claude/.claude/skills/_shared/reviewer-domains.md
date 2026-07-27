# Cross-Cutting Reviewer Domains (dispatch triggers)

Canonical trigger definitions for the single-domain specialist reviewers
(`security-reviewer`, `perf-reviewer`, `smell-reviewer`). `review-loop` reads this
file to decide whether a converged diff warrants a specialist pass.

## Eligibility = union of three signals

A domain is eligible when ANY holds. Each is a floor, none is a ceiling.

1. **Plan-declared** — the phase carries the domain in its `reviewers:` field
   (`plan-format.md`). PRIMARY signal for `security`.
2. **Force flag** — `+sec` / `+perf` / `+smell`.
3. **Diff trigger** — the rules below match the converged diff.

`no-specialist` suppresses the whole pass. Compute matches from the settled diff:

```bash
git diff --name-only HEAD | rg -i '<domain path glob, alternated>'
git diff HEAD -U0 | rg '^\+' | rg -E '<domain content regex>'   # -i only where stated
```

## security

The diff trigger is narrow by design: endpoints inherit auth from a global
subsystem in every mainstream framework, so "forgot the auth check on a new
endpoint" is not the live failure mode — **disabling the inherited protection
is.** Declare `reviewers: security` in the plan for anything else.

- **Auth opt-out markers** (content, case-SENSITIVE — framework tokens, not prose):
  `@Public\(|AllowAny\b|permission_classes\s*=\s*\[\s*\]|@csrf_exempt|csrf_exempt\b|skip_before_action|permitAll\(|\[AllowAnonymous\]|@SkipAuth|@NoAuth|authenticate:\s*false|requiresAuth:\s*false|auth:\s*false`
- **The auth subsystem itself** (paths): `**/auth/**`, `**/*auth*`, `**/session*`,
  `**/middleware/**`, `**/guards/**`, `**/*polic*`, `**/*permission*`,
  `**/*rbac*`, `**/*crypto*`, `**/*.env*`, `**/secrets*`

Endpoint/route/controller/handler/api/serializer/migration paths are NOT triggers.
A codebase with a hand-rolled authz layer reinstates pattern dispatch for itself
via the per-repo extension below.

## perf

Two conditions, **BOTH** required.

### 1. Repo capability — does a query surface exist at all?

Compute once per repo. None present → `perf` is not diff-eligible; skip it. A plan
declaration or `+perf` still forces the pass.

```bash
rg -l -m1 -i 'prisma|typeorm|sequelize|drizzle|mongoose|knex|sqlalchemy|django|psycopg|mysql|sqlite3|gorm|sqlx|pgx|entity-?framework|hibernate|activerecord' \
  package.json go.mod requirements*.txt pyproject.toml *.csproj Gemfile pom.xml 2>/dev/null
ls -d migrations db/migrate prisma alembic 2>/dev/null
```

### 2. Diff match — path or content

- **Paths**: `**/*.sql`, `**/migrations/**`, `**/models/**`, `**/models*`,
  `**/managers*`, `**/repositor*/**`, `**/*repository*`, `**/*.query.*`,
  `**/*dao*`, `**/entities/**`, `**/schema*`
- **Content, case-SENSITIVE** — SQL keywords. Matching these case-insensitively is
  what made ordinary English fire the gate:
  `\bSELECT\s|\bINSERT\s+INTO\b|\bUPDATE\s+\w+\s+SET\b|\bDELETE\s+FROM\b|\bJOIN\s+\w|\bGROUP\s+BY\b|\bORDER\s+BY\b|\bLIMIT\s+\d|\bOFFSET\s+\d`
- **Content, case-insensitive** — ORM/driver constructs, each anchored to a real
  call site rather than a bare English word:
  `\.findMany\(|\.findAll\(|\.findOne\(|createQueryBuilder|select_related|prefetch_related|values_list\(|\.annotate\(|bulk_create|\.objects\.(all|filter|get|exclude)\(|\.Include\(|\.ThenInclude\(|ToListAsync|IQueryable|FromSql|SaveChanges|\.Preload\(|gorm\.|db\.(Query|QueryRow|Exec)\(|sqlx\.|pgx\.|forEach\([^)]*await|\.map\([^)]*await`

Deliberately NOT triggers (each matched prose or non-DB code): bare `LIMIT`,
`OFFSET`, `JOIN\s`, `eager`, `lazy`, `include:`, `\.count\(`, `\.find\(`,
`\.query\(`, `objects\.`, `Promise\.all`, `await .*\bfor\b`, `rows\.Next`,
unqualified `\.Exec\(`.

## smell

Size trigger, not path/content — structure smells have no keyword signature, and
volume is the risk proxy. Eligible when EITHER holds on the converged diff:

1. **≥ 40 added lines** across source files (sum of column 1 from
   `git diff HEAD --numstat`, excluding lockfiles and generated files).
2. **≥ 1 new source file** (`git ls-files --others --exclude-standard` plus
   `git diff --name-only --diff-filter=A HEAD`) — a new file is where
   re-implementing an existing helper is most likely.

```bash
git diff HEAD --numstat | rg -v 'lock|generated|snapshot' | awk '{s+=$1} END {print s}'
```

Test-only diffs (every changed file a test file) are NOT eligible — test structure
belongs to the test-intent gates. Force with `+smell`; suppressed by
`no-specialist`.

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

`review-loop` merges these additively.
