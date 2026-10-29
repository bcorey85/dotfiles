---
type: "Change"
change_type: "changed"
title: "Every plan phase line must now carry a reviewers tag, with `none` as a legal value that declares no domain"
description: "Every plan phase line must now carry a reviewers tag, with `none` as a legal value that declares no domain."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-20T00:00:00-05:00"}
seq: 7
kind: "behavior"
components: ["agent/review-loop"]
evidence: ["census"]
watches: []
---

## Change

Every plan phase line must now carry a reviewers tag, with `none` as a legal value that declares no domain. Both plan templates show the tag on each phase line as a choice among the legal values, and the four copy-verbatim closing phase lines carry a fixed `none`. The legal values now name the structure domain, which the earlier text left out, and the stale words that the security review never infers from paths are gone. The implement skill omits the reviewers argument when the tag reads `none`. The review loop agent did not change: its input rule already says that the argument is additive only and can never suppress a domain.

## Evidence

census

## Result

The tag is the only broad signal for a security specialist, and it was optional. In live use the planner wrote the required risk tag on every phase line and the optional reviewers tag on none, no review dispatch carried the argument, and no security specialist ever ran. The template of the planning lane showed the risk tag on every phase line and the reviewers tag on no line, so the planner copied it exactly. The carrier and the consumer both work. The gain sought is review quality. The costs are a few words per phase line and one specialist dispatch for each declared domain. Effect unmeasured. The sample is one live planning session. No test round was run, because the planner agents are pinned to the largest model and the live check is free. The live checks are the share of phase lines with the tag, the share with a value other than `none`, and the count of security specialist runs. The failure to watch for is a tag of `none` on a phase that changes authorization, tenancy, guards, or secrets.

## Watch

—

## Back-out

—
