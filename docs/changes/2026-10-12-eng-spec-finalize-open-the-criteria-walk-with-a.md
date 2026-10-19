---
type: "Change"
title: "eng-spec finalize: open the criteria walk with a read-back of at most 15 lines"
description: "eng-spec finalize: open the criteria walk with a read-back of at most 15 lines."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-12T00:00:00-05:00"}
seq: 8
components: ["skill/eng-spec"]
evidence: ["census", "judgment"]
watches: []
---

## Change

eng-spec finalize: open the criteria walk with a read-back of at most 15 lines. It says what the system will do after the ticket, in the ticket owner's words, with no files or code terms, for the user to correct

## Evidence

census, judgment

## Result

At work, 15 escaped plan defects were wrong domain behavior, and plan review caught 0 of them. Only the ticket owner knows the domain rules, and the plan reaches them today as criteria and code terms. Gain: quality, through domain errors caught before any code. The read-back shares the walk turn, so it adds no interruption.

## Watch

wrong-domain plan escapes past plan review, 15 now.

## Back-out

delete the paragraph
