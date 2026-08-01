# Handoff Block (single source of truth)

The upstream→downstream context contract. Producers: `/code` (after coders
complete), `/fix` (after fix coders complete). Consumer: the `review-loop`
agent (via `/review`, `/fix`, or `/code`).

The handoff lets the reviewer skip rediscovery — file scope, change intent,
and test status are upstream context the reviewer no longer has to
reconstruct via `git diff` and full re-reads. Coders already know all of
this; pass it forward instead of forcing re-discovery.

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

`change` serves the reviewer agent: one line, whole file, what and why. `why`
serves the _human_ reading the diff. `/code` surfaces it in the phase summary,
grouped by file.

- **A note without `lines` cannot be anchored.** If a change is worth
  explaining, it needs a range.
- **`lines` are new-file numbers**, the diff's right-hand column.

`why` is optional and should stay sparse. It earns its place on non-obvious
choices — a workaround, a deliberate deviation, an ordering constraint, a
tradeoff taken knowingly. Renames, mechanical edits, and anything the diff
already explains get nothing. A note per hunk trains the reader to skip them
all, which costs more than writing none.

## Consumer rules

When present:

- Use `files` as exact review scope. Do not run `git diff`.
- If `prior-issues` is present, the reviewer's primary job is verifying those
  fixes — pass them to the reviewer subagent so it can confirm fix-by-fix
  before scanning for new issues.
- Use `iter` and `spec_iter` for the iteration counter checks. They are separate
  budgets — correctness rounds and post-convergence specialist re-entries — and
  a consumer that folds them into one number re-creates the bug the split fixed.

When absent (manual `/review` invocation), fall back to git discovery.

Treat the schema as a versioned interface — if a producer skill needs
additional fields, add them here first and update both producers and
consumers in the same change.
