---
type: "Change"
change_type: "fixed"
title: "Rule anchors fail CI when a prompt block drifts"
description: "A prompt block that changes without its row in the rule-anchors page now fails the script suite, instead of piling up unseen: the page had drifted to 69 stale and 69 unanchored rows before anything reported it."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-02T08:31:37-06:00"}
seq: 5
kind: "fix"
components: ["script/rule-anchors"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_rule_anchors.py::RuleAnchorsTest.test_every_prompt_block_has_a_current_row"
asked: ""
proof: []
unmeasured: ""
---

## Change

`tests/scripts/test_rule_anchors.py` runs `rule-anchors.sh check` against the checkout and fails on any unanchored block, stale row or missing file, with a message that says to run `rule-anchors.sh list <file>` and update the row in `docs/rule-anchors.md`. `bash tests/run.sh` (and so the script-tests workflow) now catches drift. The test skips on an awk with no regex interval support, which the block finder needs.

`docs/rule-anchors.md` is refreshed so the check passes: 63 hashes replaced with their reasons and change links updated, 6 rows for removed blocks dropped, 6 rows added for new blocks, and `rule meter` added to the evidence kinds.

## Evidence

Before the refresh, `rule-anchors.sh check` reported 69 stale rows and 69 unanchored blocks, because nothing ran it outside `claude-doctor`.

## Result

The check exits 0 and the new test passes. Reasons for the spec agents, mutation tester, goal-blind researcher, refactor skill, orchestration and reviewer-calibration rows were not re-derived; their hashes moved with trims and small edits and their reasons are left as written.

## Watch

None: the suite itself fails on drift.

## Back-out

Delete `tests/scripts/test_rule_anchors.py`.
