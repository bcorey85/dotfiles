# Acceptance criteria

Source: queue item `review-loop-full-check-ignores-a-caller-s-no-local` (session-written), `## Done when`.

- **AC1** — /review (and /code's gate) accept a caller flag or arg naming CI as the test gate, and then skip the local full check. (Phase 1)
- **AC2** — The packet reports the CI run it relied on instead of a local result. (Phase 1)
