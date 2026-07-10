# Mechanize `review-loop`'s write fence

**Captured**: 2026-07-09
**Lane when picked up**: `/deep-plan` — this changes external enforcement-tool config (`scripts/write-edit-safety-gate.sh`), which global CLAUDE.md routes to the deep-plan lane by rule, not by preference.
**Source**: surfaced as a `medium.ask` by `review-loop` reviewing Phase 3 of `docs/eng-specs/review-loop-agent.md`.

## The hole

`agents/review-loop.md` grants `Write` + `Edit`. It needs them for exactly one
thing: appending to the perf findings log under `~/vault/`. Nothing fences
those writes to that path.

`scripts/review-commit-gate.sh:38-43` marks a session `dirty` only when a
`coder*` `subagent_type` is dispatched via the `Agent` tool. A direct `Edit` of
a source file changes code while the gate still reads `clean` — so `git commit`
sails through unreviewed work.

Observed, not hypothesized: during Phase 2 review, `review-loop` fixed a HIGH
finding by directly editing its own definition (`agents/review-loop.md`) rather
than dispatching a fix coder. The edit was correct. The gate never noticed.

## Current mitigation (advisory only)

A prose fence in the agent's "What NOT to do" section forbids writes outside
`~/vault/` and names the gate mechanism. This is **not enforcement** — it is the
"just add emphasis" move that global CLAUDE.md's maintenance rule explicitly
forbids. It is a stopgap, not the fix.

## Why this wasn't fixed inline

1. **Feasibility is unverified.** No hook script reads a calling-agent
   identity. `review-commit-gate.sh:37` reads `.tool_input.subagent_type`,
   which identifies *who is being dispatched* — available only because that
   tool call is `Agent`. A `Write`/`Edit` tool call carries no equivalent
   field. Whether the hook payload exposes any discriminator for "this write
   originated inside subagent X" is **unknown and must be spiked first**.
   (Weak signal: the review-gate spike showed nested tool calls fire hooks
   under distinct `session_id`s — that is an inference, not a verified field.)

2. **Wrong lane.** Editing `write-edit-safety-gate.sh` is a change to external
   enforcement-tool config. Global CLAUDE.md routes that class to `/deep-plan`.

## Sketch (do not treat as a design)

If a caller discriminator exists, add a `PreToolUse` matcher on `Write|Edit`
that rejects any path outside `~/vault/` when the originating agent is
`review-loop`. Mirrors the existing `Write|Edit` matchers in
`settings.json:227-254`.

If no discriminator exists, the alternatives are:
- Strip `Write`/`Edit` from `review-loop` entirely and make the perf log a
  `printf >>` append via `Bash`. Enforced by the tool list rather than by
  prose. Costs the Read+Edit idempotence of the current vault-log instruction
  (heading creation, dedupe).
- Widen `review-commit-gate` to mark `dirty` on `Write`/`Edit` to source paths,
  not just on coder dispatch. Bigger blast radius: it would also catch the
  orchestrator's own direct edits, which the direct-edit-repo rule sanctions.

## Related

The same asymmetry means the gate's real guarantee is *"a coder ran without a
reviewer"*, not *"code changed without a reviewer"*. Worth deciding whether the
narrower promise is the intended one before widening anything.
