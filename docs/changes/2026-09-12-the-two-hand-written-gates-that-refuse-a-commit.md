---
type: "Change"
title: "The two hand-written gates that refuse a commit — the one requiring a review first"
description: "The two hand-written gates that refuse a commit — the one requiring a review first, and the one enforcing branch and history rules — now refuse by emitting an explicit decision the harness understands rather than by exiting with an error code."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-12T00:00:00-05:00"}
seq: 4
components: ["script/review-commit-gate", "script/git-discipline-gate"]
evidence: ["judgment"]
watches: []
---

## Change

The two hand-written gates that refuse a commit — the one requiring a review first, and the one enforcing branch and history rules — now refuse by emitting an explicit decision the harness understands rather than by exiting with an error code, and any failure inside either script's own body refuses the command instead of letting it through.

## Evidence

judgment

## Result

Both scripts failed open in the two ways a maintainer is most likely to introduce: an unset variable, and a failure inside a helper function or command substitution. Either exits the script with an error status and nothing on standard output, which the harness reads as a non-blocking error and runs the command anyway — so an unreviewed or rule-breaking commit would have landed silently. The trap fires on process exit rather than on error, because the unset-variable path never runs an error trap at all. Only an unhealthy script changes behaviour; a healthy one is unaffected.

## Watch

—

## Back-out

—
