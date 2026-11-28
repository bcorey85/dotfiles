# Acceptance Criteria — stop-hook-gate-1127

> Written before implementation. The closing Verify phase reconciles these
> against the test suite.

- **AC1** — A reply whose future step is gated on a named other party or a date (for example 'once X confirms', 'after Nov 29', 'when the lane reports') passes the gate; a test in tests/scripts covers each form.
- **AC2** — A bare first-person promise with no gate ('I'll run the suite next') still blocks.
- **AC3** — A step gated by a date or clock written with "on" or "at" (for example "on Nov 29", "on Monday", "at :47", "tomorrow") passes the gate instead of being sent back.
- **AC4** — A step that waits on later events or on another party's notice (for example "later merges", "act on their completion notices") passes the gate.
- **AC5** — A "Then ..." or "Next ..." step that follows a gated step passes, but the same words after an ungated sentence still block.
- **AC6** — Own-step ordering ("at the end", "before starting", "in my final report") and loose promises ("I'll work on it", "I'll look at the diff", "I'll fix that later") still block.
- **AC7** — When the stop hook sends a main-session reply back, the user sees the full text of that reply in the hook's warning, under a short line saying a Stop hook sent it back.
- **AC8** — A blocked reply longer than the hook message limit still shows, cut so the whole warning fits within 10,000 characters and ending with a line that says it was cut.
- **AC9** — A subagent's blocked reply is not copied into the user's pane.
- **AC10** — The hook still sends the turn back with its reason to the model exactly once, and a hook error or crash still lets the turn end instead of blocking it.
- **AC11** — A block that has no reply text to show sends the turn back with no warning text rather than an empty one.

## Manual only

- **AC12** — In a live Claude Code session, ending a turn on "I'll run the suite next." with nothing started shows the label line and the full reply in the user's pane, and the turn is sent back once. No automated test can confirm what the real tool displays or accepts for a Stop block.
