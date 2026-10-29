---
type: "Change"
title: "The full check refuses a command whose scope cannot be read"
description: "full_check.py refuses a command check_scope reads as unresolved with the result not run (unresolved command), and review-loop.md routes that result."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-29T00:00:00-05:00"}
seq: 261
kind: "fix"
components: ["script/full-check", "agent/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_full_check.py::FullCheckTest::test_a_command_whose_scope_check_scope_cannot_read_is_not_run"
asked: ""
proof: []
unmeasured: ""
---

## Change

A command `check_scope` reads as unresolved (a make call with a NAME=value argument, a missing Makefile or target) ran and could print `passed`. `full_check.py` now refuses it with the new result `not run (unresolved command: ...)`. The CLAUDE.md `Quality check:` command and a `Full suite: CI` repo keep their exceptions.

`review-loop.md` gains the route for the unresolved result and lists it in the packet's `full_check` values.

## Evidence

Failing first: on master the new test failed (unresolved make calls ran).

## Result

The new test passes. Scoped modules pass; ruff is clean.

## Watch

—

## Back-out

Revert the commit.
