---
type: "Change"
change_type: "added"
title: "The changes index lists what we tried and rejected"
description: "docs/changes/index.md ends with a generated Tried and rejected section, one line per current HOLD or REMOVE finding, so a null result stays visible and is not rerun."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T13:39:54-05:00"}
seq: 322
kind: "user-rule"
components: []
evidence: ["judgment"]
watches: []
test: ""
asked: "2026-10-30: tests that were tried and did not ship: \"those are sometimes just as valuable\""
proof: []
unmeasured: ""
---

## Change

`build_changes.py` in agent-evals now reads the findings bundle on every build and adds a `# Tried and rejected` section after the unmeasured changes. It holds one line per HOLD or REMOVE finding, newest first: the linked title, the disposition and the finding's description. A superseded finding stays out, because its superseder holds the verdict. The section has no hand-kept list, so `--check` fails when a new finding is missing from the index, and a finding that fails validation blocks the build.

## Evidence

Change files record only what shipped. Null and worse results live in agent-evals `findings/`, so the changelog never showed them. The user asked how docs/changes calls those tests out, and it did not.

## Result

The first build lists 189 of the 200 HOLD or REMOVE findings; the other 11 are superseded. Four descriptions state their result in words with no digit. The builder tests cover a HOLD and a REMOVE finding listed, an EDIT finding left out, a superseded finding left out, a stale index and a bad finding.

## Watch

None: this is a user rule on what the page shows.

## Back-out

Remove `rejected_findings`, `rejected_line` and the `rejected` argument of `render_index` from `build_changes.py`, then rebuild the index.
