---
type: "Change"
title: "The rule for messages to other sessions no longer tells the sender to write a file"
description: "The rule for messages to other sessions no longer tells the sender to write a file."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-29T00:00:00-05:00"}
seq: 12
components: ["rule/global-claude-md"]
evidence: ["judgment"]
watches: []
---

## Change

The rule for messages to other sessions no longer tells the sender to write a file. It sends the path only when the detail already lives in a file, and makes no file only to hold a message

## Evidence

judgment

## Result

A new file costs the same output tokens as the message, and a receiver that reads it pays the full growth plus the summary. The files also add up on disk

## Watch

—

## Back-out

—
