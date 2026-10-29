---
type: "Change"
change_type: "changed"
title: "The reviewer's rule for a prior issue the fixer skipped now names the failure on both sides"
description: "The reviewer's rule for a prior issue the fixer skipped now names the failure on both sides, and one duplicated scope instruction was cut."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-08-08T00:00:00-05:00"}
seq: 11
kind: "behavior"
components: ["agent/code-reviewer"]
evidence: ["census"]
watches: []
---

## Change

The reviewer's rule for a prior issue the fixer skipped now names the failure on both sides, and one duplicated scope instruction was cut

## Evidence

census

## Result

A second, independently dispatched reading of the same reviewer file found the skip rule stated only half its job — do not re-flag — with nothing said about a rationale that does not hold. It now covers both, and the scope instruction that was stated twice in the same file is stated once

## Watch

—

## Back-out

—
