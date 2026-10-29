---
type: "Change"
change_type: "changed"
title: "The deep modifier dispatches the Opus-pinned deep coder again"
description: "On the deep modifier, the code skill, the review loop and the shared modifier rules dispatch the Opus-pinned deep coder in place of the plain coder."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-29T00:00:00-05:00"}
seq: 4
kind: "behavior"
reverts: "2026-09-29-the-opus-pinned-deep-coder-is-removed"
components: ["agent/review-loop"]
evidence: ["judgment"]
watches: []
---

## Change

The deep modifier dispatches the Opus-pinned deep coder again. On the deep modifier, the code skill, the review loop and the shared modifier rules dispatch it in place of the plain coder

## Evidence

judgment

## Result

The plain coder now runs on Sonnet, and a hook blocks an Opus model at the call site, so an agent file is the only way to run an Opus coder. Quality gain unmeasured: on the bench, the Opus coder failed 0.23 hidden tests per run against 0.27 for Sonnet 5.5, inside the noise. Deep runs cost Opus tokens again.

## Watch

—

## Back-out

—
