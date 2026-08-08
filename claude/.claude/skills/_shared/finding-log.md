# Per-Finding Gate Log

Canonical instruction for every gate that emits findings. Skills and agents
point here instead of restating it, so the schema has one owner.

`review-metrics.jsonl` records one aggregate row per run. It cannot say which
gate caught what, and it cannot say how a gate does on diffs where it finds
nothing. This log carries both.

## Emit

Run this after dispositions are known, so `actioned` is real rather than
predicted. Telemetry never blocks: if the script fails, mention it and continue.

```bash
L="$HOME/.claude/skills/review/log-review-finding"
C="repo=$(basename "$(git rev-parse --show-toplevel)") branch=$(git branch --show-current) lane=<lane> scope=<phase|branch-exit|standalone> phase=<index|-> iter=<N>"

# ONE run row per gate dispatched — INCLUDING gates that returned nothing.
bash "$L" kind=run $C gate=<agent name> n_findings=<n> diff_loc=<n> result=<...>

# ONE finding row per finding that gate emitted.
bash "$L" kind=finding $C gate=<agent name> disposition=<fix|ask|nit> [blocker=yes] \
  class=<bug|smell|duplication|complexity|plan-drift|test-gap|weak-assertion|security|correctness|other> \
  file=<path> line=<n> actioned=<fixed|skipped_fp|deferred|ask|none> desc="<one line>"
```

## Rules that make the data usable

- **Log the silent runs.** A gate that found nothing still gets its `kind=run`
  row with `n_findings=0`. Those rows are the denominator; a log holding only
  findings makes every gate look perfect and answers no question worth asking.
- **`gate=` is the literal agent name dispatched.** Never collapse a `-deep`
  tier into its base name — the two tiers are different instruments.
- **`diff_loc` is measured, not estimated.** `git diff --shortstat` over that
  gate's scope, insertions + deletions. Detection degrades as the reviewed
  change grows, so yield without size is uninterpretable.
- **`file`/`line` is the join key** — across gates, and against
  `review-escapes.jsonl`. A finding naming no line logs `line=0`; it counts,
  it just cannot participate in overlap analysis.
- **`fix_induced=yes`** when the finding names code an earlier fix in this loop
  introduced rather than code the author originally wrote.
- `class=` uses the escape vocabulary so the caught and escaped sides
  cross-tabulate. Do not invent values.

Full field reference lives in the script's header.
