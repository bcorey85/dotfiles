---
type: "Change"
change_type: "added"
title: "lane-status names a diff viewer over its memory cap"
description: "lane-status prints one viewer line per live hunk viewer over its cap, naming the lane, and one cannot-read line when the viewer list fails."
generated: {"by": "claude-opus-5-5/main", "at": "2026-11-24T09:58:11-06:00"}
seq: 3
kind: "fix"
components: ["script/lane-status"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_lane_status.py::LaneStatusTest::test_a_viewer_over_the_cap_is_named_with_its_lane"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`lane_status.py` reads `hunk-review-pane --viewers`, skips rows whose process is gone, is not `hunk`, or is at or under
the cap, and prints `viewer <lane, folder or pane>: <size>, over <cap> cap (pane <pane>, pid <pid>)` for the rest. A viewer
list or a viewer process that could not be read prints one `viewers: cannot read (<reason>)` line and the other lines still print. Each oversized
viewer is one `viewer:<pane>` report key, so `--changes` prints it once, and it works with no open lanes.
`process_group` gains `resident_bytes` and `program_name`, sharing one `ps` call with `command_line`.

## Evidence

Judgment: the tests stub only `hunk-review-pane` and measure real processes.

## Result

A viewer that outgrows its cap is named with its lane instead of going unseen.

## Watch

None: a live viewer over a small `HUNK_REVIEW_MEMORY_MAX` shows in a plain run.

## Back-out

Revert the commit: lane-status stops reading viewers.

