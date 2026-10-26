# Per-Finding Gate Log

Canonical instruction for every finding-emitting gate.

## Emit

Run after dispositions are known (`actioned` real, not predicted). Telemetry never blocks.

```bash
# Each row is its own plain Bash call by this path: no $HOME, variable, array or $(...).
# Repeat lane/scope/phase/iter on every call; omit phase when there is none. The script adds repo and branch itself.

# ONE run row per gate dispatched — INCLUDING gates that returned nothing.
~/.claude/skills/review/log-review-finding kind=run lane=<lane> scope=<phase|branch-exit|standalone> [phase=<index>] iter=<N> \
  gate=<agent name> n_findings=<n> diff_loc=<n> result=<PASS|PASS WITH WARNINGS|NEEDS CHANGES|NOT DISPATCHED>

# ONE finding row per finding that gate emitted.
~/.claude/skills/review/log-review-finding kind=finding lane=<lane> scope=<phase|branch-exit|standalone> [phase=<index>] iter=<N> \
  gate=<agent name> disposition=<fix|ask|nit> [blocker=yes] \
  class=<bug|smell|duplication|complexity|plan-drift|test-gap|weak-assertion|security|perf|correctness|docs|other> \
  file=<path> line=<n> actioned=<fixed|skipped_fp|deferred|ask|none> [source=<round|class|gate>]
# Prints finding_id=<id>.
```

## Rules that make the data usable

- **Log silent runs:** `kind=run` with `n_findings=0`.
- **`gate=` is the literal agent name dispatched.** Never collapse a `-deep`
  tier into its base name.
- **`diff_loc` is measured, not estimated.** `git diff --shortstat` over that
  gate's scope, insertions + deletions.
- **`file`/`line` is the join key.** A finding naming no line logs `line=0`.
- **`fix_induced=yes`** for code an earlier fix in this loop introduced.
- **`fix_induced=bug`** — the tool sets `blocker=yes`; a loop-introduced bug cannot defer. Set `actioned=fixed`.
- **`source=`** — review-loop only, on every `fix` row: `round` (a full review), `class` (an open class member at
  the cap), `gate` (the execution gate). A `code-reviewer` `fix` row with `actioned=deferred` needs `source=class`.
  The tool refuses any other: that finding gets a coder.
- `class=` uses the escape vocabulary so the caught and escaped sides
  cross-tabulate. Do not invent values — unknown ones store as `other` and are counted in the yield header.
- **`other` is a last resort.** Reach for `docs` when the prose is wrong about the code (stale comment, wrong quantity, contradicting doc, over-cap volume).
- **`result=` is the gate's verdict.** Gates with no pass/fail vocabulary still owe one (`PASS` clean/intent-aligned, `NEEDS CHANGES` gaps/residue, `NOT DISPATCHED` surface-unmatched). Omit only with genuinely no verdict.

- **`desc=` is accepted and never stored.** The ledger keeps no free text. Leave it off new calls.
- **Asks:** the call that logs an `actioned=ask` finding row prints `finding_id=<id>`. Capture it and put it on that ask's `ask[]` item. The outcome call passes `finding_id=<id>` and `ask_outcome=`, and it supersedes the ask row. An ask outcome with no `finding_id` writes nothing.

Full field reference lives in the script's header.
