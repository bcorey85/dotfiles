# Handoff Block (single source of truth)

Upstream→downstream context contract. Producers `/code` + `/fix`; consumer `review-loop`.

## Canonical schema

```
handoff:
  files:
    - path: <relative path>
      change: <one line: what changed and why>
      why:                # optional; the human-review channel, see below
        - lines: <start>-<end>    # NEW-file line numbers (the diff's right column)
          note: <why this specific block looks the way it does>
  tests-run: <exact command + exit code, e.g. "npx jest src/orders.test.ts → exit 0"; scoped to the changed files; or "none">
  flagged: <issues the upstream coder explicitly flagged, or "none">
  plan_impact: <"none", or a block that starts RESOLVED: the ruling, who ruled (the user, the session or the pre-set decision) and when, the ruling's words, then the PLAN-IMPACT block it settles>
  prior-issues:           # only present on fix → review
    - issue: <one line>
      status: fixed | skipped | partial
      file: <path>
  iter: <integer>         # correctness rounds run (default 0)
  spec_iter: <integer>    # post-convergence specialist re-entries consumed (default 0; omit on a first dispatch)
```

## Who writes `files` for `/code`

`/code` writes only the `why` entries; `code_review_start.py` replaces `files` with the paths git shows changed since the phase base (tracked changes plus untracked files), keeping each entry's `why`. Never list a changed file, an export or a line number from memory.

## The `why` channel

`change` serves the reviewer; `why` serves the human.

- **No `lines`, no anchor.**
- **`lines` are new-file numbers**, the diff's right-hand column.
- Non-obvious choices only: workarounds, deviations, ordering constraints, knowing tradeoffs. Renames and mechanical diffs get nothing.

## Consumer rules

When present:

- Use `files` as exact review scope. Do not run `git diff`.
- `prior-issues` present ⇒ verify fixes fix-by-fix before scanning for new issues.
- `plan_impact` starting `RESOLVED` ⇒ settled by a ruling, and the block names who ruled: review against the ruling, never record it in `plan_impacts[]`.
- `iter`/`spec_iter` are separate budgets. Never fold them.

When absent (manual `/review` invocation), fall back to git discovery.

A producer needing a new field adds it here first, and updates both sides in
the same change.
