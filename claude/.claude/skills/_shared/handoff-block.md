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
  tests-run: <exact command + exit code, e.g. "npm run validate → exit 0"; or "none">
  flagged: <issues the upstream coder explicitly flagged, or "none">
  plan_impact: <verbatim PLAN-IMPACT block + the user's decision, or "none">
  prior-issues:           # only present on fix → review
    - issue: <one line>
      status: fixed | skipped | partial
      file: <path>
  iter: <integer>
```

## Consumer rules

When present:

- Use `files` as exact review scope. Do not run `git diff`.
- If `prior-issues` is present, the reviewer's primary job is verifying those
  fixes — pass them to the reviewer subagent so it can confirm fix-by-fix
  before scanning for new issues.
- Use `iter` for the iteration counter check.

When absent (manual `/review` invocation), fall back to git discovery.

Treat the schema as a versioned interface — if a producer skill needs
additional fields, add them here first and update both producers and
consumers in the same change.
