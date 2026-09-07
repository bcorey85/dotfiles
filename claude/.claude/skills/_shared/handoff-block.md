# Handoff Block (single source of truth)

Upstream→downstream context contract. Producers `/code` + `/fix`; consumer `review-loop`. Lets the reviewer skip rediscovery — scope, intent, and test status arrive, not reconstructed.

## Canonical schema

```
handoff:
  files:
    - path: <relative path>
      change: <one line: what changed and why>
      why:                # optional; the human-review channel, see below
        - lines: <start>-<end>    # NEW-file line numbers (the diff's right column)
          note: <why this specific block looks the way it does>
  tests-run: <exact command + exit code, e.g. "npm run validate → exit 0"; or "none">
  flagged: <issues the upstream coder explicitly flagged, or "none">
  plan_impact: <verbatim PLAN-IMPACT block + the user's decision, or "none">
  prior-issues:           # only present on fix → review
    - issue: <one line>
      status: fixed | skipped | partial
      file: <path>
  iter: <integer>         # correctness rounds consumed (default 1)
  spec_iter: <integer>    # post-convergence specialist re-entries consumed (default 0; omit on a first dispatch)
```

## The `why` channel

`change` serves the reviewer; `why` serves the _human_ (surfaced in `/code`'s phase summary).

- **No `lines`, no anchor** — worth explaining ⇒ needs a range.
- **`lines` are new-file numbers**, the diff's right-hand column.

`why` stays sparse: non-obvious choices only (workarounds, deviations, ordering constraints, knowing tradeoffs). Renames/mechanical/self-explaining diffs get nothing.

## Consumer rules

When present:

- Use `files` as exact review scope. Do not run `git diff`.
- `prior-issues` present ⇒ verify fixes fix-by-fix before scanning for new issues.
- `iter`/`spec_iter` are separate budgets — folding them re-creates the bug the split fixed.

When absent (manual `/review` invocation), fall back to git discovery.

Treat the schema as a versioned interface — if a producer skill needs
additional fields, add them here first and update both producers and
consumers in the same change.
