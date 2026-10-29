---
type: "Change"
change_type: "changed"
title: "The 11 agents pinned to the `sonnet` alias moved to Sonnet 5.5 on 2026-09-28 through the CLI update"
description: "The 11 agents pinned to the `sonnet` alias moved to Sonnet 5.5 on 2026-09-28 through the CLI update, with no file edit."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-29T00:00:00-05:00"}
seq: 1
kind: "behavior"
components: ["agent/coder"]
evidence: ["judgment"]
watches: ["sonnet-5-5-move"]
---

## Change

The 11 agents pinned to the `sonnet` alias moved to Sonnet 5.5 on 2026-09-28 through the CLI update, with no file edit. The user kept the alias and did not pin the old model

## Evidence

judgment

## Result

Untested. Compare the review gates' findings and escape rates before and after 2026-09-28 in the work logs.

## Watch

Read 2026-10-24 on work logs through 2026-10-22: review escapes per code-reviewer run 0.18 after, against a median of 0.22 (range 0.09 to 0.56) before. No change. Kept: the move came with the CLI update and has no file to revert. Watch closed.

## Back-out

—
