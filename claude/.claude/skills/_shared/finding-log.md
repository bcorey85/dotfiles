# Per-Finding Gate Log

Canonical instruction for every finding-emitting gate.

## Emit

Run after dispositions are known (`actioned` real, not predicted). Telemetry never blocks.

```bash
L="$HOME/.claude/skills/review/log-review-finding"

# An ARRAY, not a string — a quoted string collapses every join key into repo=. Always expand as "${C[@]}".
C=(
  "repo=$(basename "$(git rev-parse --show-toplevel)")"
  "branch=$(git branch --show-current)"
  lane=<lane> scope=<phase|branch-exit|standalone> phase=<index|-> iter=<N>
)

# ONE run row per gate dispatched — INCLUDING gates that returned nothing.
bash "$L" kind=run "${C[@]}" gate=<agent name> n_findings=<n> diff_loc=<n> \
  result=<PASS|PASS WITH WARNINGS|NEEDS CHANGES|NOT DISPATCHED>

# ONE finding row per finding that gate emitted.
bash "$L" kind=finding "${C[@]}" gate=<agent name> disposition=<fix|ask|nit> [blocker=yes] \
  class=<bug|smell|duplication|complexity|plan-drift|test-gap|weak-assertion|security|perf|correctness|docs|other> \
  file=<path> line=<n> actioned=<fixed|skipped_fp|deferred|ask|none> desc="<one line>"
```

## Rules that make the data usable

- **Log silent runs:** `kind=run` with `n_findings=0` — those rows are the denominator.
- **`gate=` is the literal agent name dispatched.** Never collapse a `-deep`
  tier into its base name — the two tiers are different instruments.
- **`diff_loc` is measured, not estimated.** `git diff --shortstat` over that
  gate's scope, insertions + deletions.
- **`file`/`line` is the join key** — across gates, and against
  `review-escapes.jsonl`. A finding naming no line logs `line=0`; it counts,
  it just cannot participate in overlap analysis.
- **`fix_induced=yes`** for code an earlier fix in this loop introduced.
- **`fix_induced=bug` auto-promotes to `blocker`.** A loop-introduced bug cannot defer — set `blocker=yes`, `actioned=fixed`.
- `class=` uses the escape vocabulary so the caught and escaped sides
  cross-tabulate. Do not invent values — unknown ones are refused.
- **`other` is a last resort, read as one.** Reach for `docs` when the prose is wrong about the code (stale comment, wrong quantity, contradicting doc, over-cap volume). Mostly-`other` findings say nothing about what the gate catches.
- **`result=` is the gate's verdict.** Gates with no pass/fail vocabulary still owe one (`PASS` clean/intent-aligned, `NEEDS CHANGES` gaps/residue, `NOT DISPATCHED` surface-unmatched). Omit only with genuinely no verdict.

Full field reference lives in the script's header.
